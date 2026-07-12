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

# Клиенты YouTube в порядке приоритета.
# ios и android — мобильные клиенты, обходят большинство ограничений.
# tv_embedded убран — YouTube его отключил ("no longer supported").
YT_CLIENTS = ["ios", "android", "mweb", "web"]


def get_youtube_audio_stream_url(video_id_or_url: str) -> tuple:
    """
    Пробует получить аудиопоток через разные YouTube-клиенты.
    Для каждого клиента пробуем несколько форматов — разные клиенты
    возвращают разные наборы форматов.
    """
    url = (
        video_id_or_url
        if video_id_or_url.startswith("http")
        else f"https://www.youtube.com/watch?v={video_id_or_url}"
    )

    # Форматы от предпочтительного к самому простому.
    # None = yt-dlp выбирает сам (наиболее совместимый вариант).
    formats_to_try = [
        "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
        "bestaudio/best",
        "best[height<=480]/best",
        "best",
        None,   # yt-dlp default — берёт что есть
    ]

    for client in YT_CLIENTS:
        for fmt in formats_to_try:
            opts = {
                "quiet": True,
                "no_warnings": True,
                "nocheckcertificate": True,
                "skip_download": True,
                "extractor_args": {"youtube": {"player_client": [client]}},
            }
            if fmt is not None:
                opts["format"] = fmt
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    stream_url = info.get("url")
                    if stream_url:
                        print(f"[YouTube] ✓ Клиент '{client}', формат '{fmt}': {video_id_or_url}")
                        return stream_url, info.get("http_headers", {})
            except Exception as e:
                err = str(e)
                if "Requested format is not available" in err:
                    continue  # пробуем следующий формат
                if any(x in err for x in ("Please sign in", "Sign in", "no longer supported")):
                    print(f"[YouTube] Клиент '{client}' заблокирован, пробуем следующий...")
                    break  # переходим к следующему клиенту
                if any(x in err for x in ("Video unavailable", "Private video")):
                    print(f"[YouTube] Видео {video_id_or_url} недоступно")
                    return None, {}
                print(f"[YouTube] Ошибка ({client}/{fmt}): {err}")

    print(f"[YouTube] Все клиенты/форматы исчерпаны для {video_id_or_url}")
    return None, {}


def search_youtube_candidates(query: str, exclude_id: str = None) -> list:
    """Поиск кандидатов на YouTube, исключая уже попробованный ID."""
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "extractor_args": {"youtube": {"player_client": ["tv_embedded"]}},
    }
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


def build_search_queries(artist: str, title: str) -> list:
    """Список запросов от наиболее доступного к точному."""
    clean_title = re.sub(r"\([^)]*\)", "", title or "")
    clean_title = re.sub(r"\[[^\]]*\]", "", clean_title)
    clean_title = re.sub(
        r"\b(official|mv|music video|lyrics?|audio|hd|4k|ver\.?|prod\.?)\b",
        "", clean_title, flags=re.IGNORECASE
    )
    clean_title = " ".join(clean_title.split())

    clean_artist = re.sub(
        r"\b(HYBE LABELS?|SM Entertainment|YG Entertainment|JYP Entertainment)\b",
        "", artist or "", flags=re.IGNORECASE
    ).strip()

    queries = []
    if clean_artist and clean_title:
        queries.append(f"{clean_artist} {clean_title} audio")
        queries.append(f"{clean_artist} {clean_title} lyrics")
    if clean_title:
        queries.append(f"{clean_title} audio")
        queries.append(f"{clean_title} lyrics")
    if artist and title:
        queries.append(f"{artist} {title}")
    if clean_title:
        queries.append(clean_title)

    seen, result = set(), []
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            result.append(q)
    return result


def try_youtube_stream(query: str, exclude_id: str = None) -> tuple:
    """Поиск + получение потока для первого рабочего кандидата."""
    candidates = search_youtube_candidates(query, exclude_id=exclude_id)
    for vid_id in candidates:
        stream_url, headers = get_youtube_audio_stream_url(vid_id)
        if stream_url:
            print(f"[YouTube Search] ✓ Рабочий кандидат '{query}': {vid_id}")
            return stream_url, headers
        print(f"[YouTube Search] {vid_id} заблокирован, пробуем следующий...")
    return None, {}


def try_soundcloud_stream(artist: str, title: str) -> tuple:
    """SoundCloud как финальный резерв."""
    try:
        clean = re.sub(r"\([^)]*\)", "", title or "").strip() if title else ""
        query = f"{artist} {clean}" if (artist and clean) else (clean or artist or "Music")
        access_token = fetch_soundcloud_access_token()
        if not access_token:
            return None, None
        sc = SoundCloudPlugin(access_token=access_token)
        results = sc.search(query)
        if results:
            stream_url = sc.get_stream_url(str(results[0].id))
            if stream_url and "m3u8" not in stream_url:
                print(f"[SoundCloud] ✓ Найден: {results[0].title}")
                return stream_url, "audio/mpeg"
    except Exception as e:
        print(f"[SoundCloud] Ошибка: {e}")
    return None, None


@router.get("/{track_id}")
def stream_track(
    track_id: str,
    request: Request,
    source: str = Query("soundcloud"),
    title: str  = Query(None),
    artist: str = Query(None),
    db: Session = Depends(get_db),
):
    if source == "soundcloud" and len(track_id) == 11 and not track_id.isdigit():
        print(f"[Stream AutoFix] YouTube ID '{track_id}' под маской soundcloud.")
        source = "youtube"

    print(f"[Stream] {artist} - {title} [source={source}, id={track_id}]")

    send_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    if r := request.headers.get("range"):
        send_headers["Range"] = r

    stream_url = None
    media_type = "audio/mpeg"

    # ── YOUTUBE / SPOTIFY ─────────────────────────────────────────────────────
    if source in ("youtube", "spotify"):
        if source == "spotify":
            yt_target = None
        elif track_id.isdigit():
            track_db  = db.query(models.Track).filter(models.Track.id == int(track_id)).first()
            yt_target = track_db.source_id if track_db else None
            print(f"[Stream DB] source_id = {yt_target}")
        else:
            yt_target = track_id

        # Попытка 1: прямой ID через все клиенты
        if yt_target:
            stream_url, yt_headers = get_youtube_audio_stream_url(yt_target)
            if stream_url:
                send_headers.update(yt_headers)
                send_headers.pop("Accept-Encoding", None)
                media_type = "audio/webm"

        # Попытка 2: поиск с упрощёнными запросами
        if not stream_url:
            queries = build_search_queries(artist or "", title or "")
            for q in queries:
                print(f"[YouTube Search] Пробуем: '{q}'")
                stream_url, yt_headers = try_youtube_stream(q, exclude_id=yt_target)
                if stream_url:
                    send_headers.update(yt_headers)
                    send_headers.pop("Accept-Encoding", None)
                    media_type = "audio/webm"
                    break

        # Попытка 3: SoundCloud
        if not stream_url:
            print("[Stream] YouTube недоступен, пробуем SoundCloud...")
            stream_url, sc_media = try_soundcloud_stream(artist, title)
            if stream_url:
                media_type = sc_media

    # ── SOUNDCLOUD ────────────────────────────────────────────────────────────
    elif source == "soundcloud":
        try:
            access_token = fetch_soundcloud_access_token()
            sc = SoundCloudPlugin(access_token=access_token)
            stream_url = sc.get_stream_url(track_id)
            if stream_url and "m3u8" in stream_url:
                print("[SoundCloud] HLS, переключаемся на YouTube...")
                stream_url = None
        except Exception as e:
            print(f"[SoundCloud] Ошибка: {e}")
            stream_url = None

        if not stream_url:
            queries = build_search_queries(artist or "", title or "")
            for q in queries:
                stream_url, yt_headers = try_youtube_stream(q)
                if stream_url:
                    send_headers.update(yt_headers)
                    send_headers.pop("Accept-Encoding", None)
                    media_type = "audio/webm"
                    break

    # ── ПОТОК ─────────────────────────────────────────────────────────────────
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