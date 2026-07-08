# backend/routers/stream.py
import re
import requests
import yt_dlp
from fastapi import APIRouter, Query, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db import models
from backend.plugins.soundcloud import SoundCloudPlugin
from backend.soundcloud_auth import fetch_soundcloud_access_token

router = APIRouter(prefix="/stream", tags=["Stream"])


def get_youtube_audio_stream_url(video_id_or_url: str):
    """Возвращает (stream_url, headers) или (None, {})."""
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "skip_download": True,
    }
    try:
        url = (
            video_id_or_url
            if video_id_or_url.startswith("http")
            else f"https://www.youtube.com/watch?v={video_id_or_url}"
        )
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("url"), info.get("http_headers", {})
    except Exception as e:
        print(f"[YouTube Extractor] Ошибка для {video_id_or_url}: {e}")
        return None, {}


def search_youtube_candidates(query: str, exclude_id: str = None) -> list[str]:
    """
    Ищет треки на YouTube и возвращает список ID кандидатов.
    exclude_id — уже попробованный заблокированный ID, его пропускаем.
    """
    ydl_opts = {"quiet": True, "extract_flat": True}
    candidates = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(f"ytsearch5:{query}", download=False)
            if res and "entries" in res:
                for entry in res["entries"]:
                    vid_id = entry.get("id")
                    if vid_id and vid_id != exclude_id:
                        candidates.append(vid_id)
    except Exception as e:
        print(f"[YouTube Search] Ошибка поиска '{query}': {e}")
    return candidates


def simplify_query(artist: str, title: str) -> list[str]:
    """
    Возвращает список поисковых запросов от точного к простому.
    Убирает теги вроде 'Official MV', '방탄소년단', лейблы и т.д.
    """
    queries = []

    if artist and title:
        queries.append(f"{artist} {title}")

    if title:
        # Убираем скобки с лейблами, языки и теги
        clean = re.sub(r"\([^)]*\)", "", title)          # (방탄소년단)
        clean = re.sub(r"\[[^\]]*\]", "", clean)          # [Official]
        clean = re.sub(
            r"\b(official|mv|music video|lyrics?|audio|hd|4k|ver\.?)\b",
            "", clean, flags=re.IGNORECASE
        )
        clean = clean.strip()
        if clean and clean != title:
            queries.append(clean)

    # Самый простой запрос — только название без артиста
    if title:
        queries.append(title)

    return [q for q in queries if q]


def try_youtube_stream(query: str, exclude_id: str = None) -> tuple:
    """
    Пробует найти рабочий поток на YouTube.
    Возвращает (stream_url, headers) или (None, {}).
    """
    candidates = search_youtube_candidates(query, exclude_id=exclude_id)
    for vid_id in candidates:
        stream_url, headers = get_youtube_audio_stream_url(vid_id)
        if stream_url:
            print(f"[YouTube Search] Рабочий кандидат: {vid_id}")
            return stream_url, headers
        print(f"[YouTube Search] {vid_id} тоже заблокирован, пробуем следующий...")
    return None, {}


def try_soundcloud_stream(artist: str, title: str) -> tuple:
    """
    Пробует получить поток через SoundCloud.
    Возвращает (stream_url, media_type) или (None, None).
    """
    try:
        query        = f"{artist} {title}" if (artist and title) else (title or artist or "Music")
        access_token = fetch_soundcloud_access_token()
        if not access_token:
            return None, None

        sc = SoundCloudPlugin(access_token=access_token)
        results = sc.search(query)
        if results:
            stream_url = sc.get_stream_url(str(results[0].id))
            if stream_url and "m3u8" not in stream_url:
                print(f"[SoundCloud] Найден трек: {results[0].title}")
                return stream_url, "audio/mpeg"
    except Exception as e:
        print(f"[SoundCloud Fallback] Ошибка: {e}")
    return None, None


@router.get("/{track_id}")
def stream_track(
    track_id: str,
    request: Request,
    source: str  = Query("soundcloud"),
    title: str   = Query(None),
    artist: str  = Query(None),
    db: Session  = Depends(get_db),
):
    if source == "soundcloud" and len(track_id) == 11 and not track_id.isdigit():
        print(f"[Stream AutoFix] YouTube ID '{track_id}' под маской soundcloud.")
        source = "youtube"

    print(f"[Stream Router] Запрос: {artist} - {title} [source={source}, id={track_id}]")

    send_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    client_range = request.headers.get("range")
    if client_range:
        send_headers["Range"] = client_range

    stream_url = None
    media_type = "audio/mpeg"

    # ── YOUTUBE / SPOTIFY ────────────────────────────────────────────────────
    if source in ("youtube", "spotify"):

        # Определяем реальный YouTube ID
        if source == "spotify":
            yt_target = None   # Нет прямого ID, сразу поиск
        elif track_id.isdigit():
            track_db  = db.query(models.Track).filter(models.Track.id == int(track_id)).first()
            yt_target = track_db.source_id if track_db else None
            print(f"[Stream DB] source_id = {yt_target}")
        else:
            yt_target = track_id

        # Попытка 1: прямой ID
        if yt_target:
            stream_url, yt_headers = get_youtube_audio_stream_url(yt_target)
            if stream_url:
                send_headers.update(yt_headers)
                send_headers.pop("Accept-Encoding", None)
                media_type = "audio/webm"

        # Попытка 2: поиск по нескольким вариантам запроса, исключая уже попробованный ID
        # ИСПРАВЛЕНО: раньше поиск возвращал тот же заблокированный ID.
        # Теперь simplify_query() строит запросы от точного к простому,
        # а search_youtube_candidates() исключает уже попробованный ID
        # и возвращает список кандидатов — перебираем пока один не заработает.
        if not stream_url:
            queries = simplify_query(artist or "", title or "")
            for q in queries:
                print(f"[YouTube Search] Пробуем запрос: '{q}'")
                stream_url, yt_headers = try_youtube_stream(q, exclude_id=yt_target)
                if stream_url:
                    send_headers.update(yt_headers)
                    send_headers.pop("Accept-Encoding", None)
                    media_type = "audio/webm"
                    break

        # Попытка 3: SoundCloud как последний резерв
        if not stream_url:
            print("[Stream] YouTube недоступен, пробуем SoundCloud...")
            stream_url, sc_media = try_soundcloud_stream(artist, title)
            if stream_url:
                media_type = sc_media

    # ── SOUNDCLOUD ───────────────────────────────────────────────────────────
    elif source == "soundcloud":
        try:
            access_token = fetch_soundcloud_access_token()
            sc           = SoundCloudPlugin(access_token=access_token)
            stream_url   = sc.get_stream_url(track_id)

            if stream_url and "m3u8" in stream_url:
                print("[SoundCloud] HLS (.m3u8), переключаемся на YouTube...")
                stream_url = None
        except Exception as e:
            print(f"[SoundCloud] Ошибка: {e}")
            stream_url = None

        if not stream_url:
            queries = simplify_query(artist or "", title or "")
            for q in queries:
                stream_url, yt_headers = try_youtube_stream(q)
                if stream_url:
                    send_headers.update(yt_headers)
                    send_headers.pop("Accept-Encoding", None)
                    media_type = "audio/webm"
                    break

    # ── ОТДАЁМ ПОТОК ─────────────────────────────────────────────────────────
    if not stream_url:
        raise HTTPException(
            status_code=404,
            detail=f"Аудиопоток недоступен для '{title or track_id}'"
        )

    try:
        remote_resp = requests.get(stream_url, headers=send_headers, stream=True, timeout=15)

        response_headers = {"Accept-Ranges": "bytes"}
        if "Content-Range"  in remote_resp.headers:
            response_headers["Content-Range"]  = remote_resp.headers["Content-Range"]
        if "Content-Length" in remote_resp.headers:
            response_headers["Content-Length"] = remote_resp.headers["Content-Length"]

        return StreamingResponse(
            remote_resp.iter_content(chunk_size=1024 * 64),
            status_code=remote_resp.status_code,
            headers=response_headers,
            media_type=media_type,
        )
    except Exception as e:
        print(f"[Stream Proxy] Критическая ошибка: {e}")
        raise HTTPException(status_code=500, detail="Ошибка стриминг-прокси")