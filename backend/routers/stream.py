# backend/routers/stream.py
import re
import json
import requests
import yt_dlp
from fastapi import APIRouter, Query, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db import models
from backend.plugins.soundcloud import SoundCloudPlugin
from backend.soundcloud_auth import fetch_soundcloud_access_token
from backend.services.cache import get_redis

router = APIRouter(prefix="/stream", tags=["Stream"])

YT_CLIENTS = ["ios", "android", "mweb", "web"]

# ── REDIS-КЕШ ДЛЯ STREAM URL ─────────────────────────────────────────────────
# YouTube URL действителен ~6 часов, кешируем на 25 минут.
# Это позволяет мгновенно отвечать на повторные запросы и на предзагруженные треки.
STREAM_TTL = 1500  # секунд = 25 минут


def _stream_cache_key(track_id: str, source: str) -> str:
    return f"stream:{source}:{track_id}"


def _get_cached_url(track_id: str, source: str):
    """Возвращает (url, headers, media_type) из кеша или None."""
    try:
        raw = get_redis().get(_stream_cache_key(track_id, source))
        if raw:
            data = json.loads(raw)
            print(f"[Stream Cache] ✓ HIT для {track_id} ({source})")
            return data["url"], data.get("headers", {}), data.get("media_type", "audio/webm")
    except Exception as e:
        print(f"[Stream Cache] Ошибка чтения: {e}")
    return None


def _set_cached_url(track_id: str, source: str,
                    url: str, headers: dict, media_type: str) -> None:
    """Сохраняет результат yt-dlp в Redis."""
    try:
        payload = json.dumps({"url": url, "headers": headers, "media_type": media_type},
                             ensure_ascii=False)
        get_redis().setex(_stream_cache_key(track_id, source), STREAM_TTL, payload)
    except Exception as e:
        print(f"[Stream Cache] Ошибка записи: {e}")


def _invalidate_stream_cache(track_id: str, source: str) -> None:
    """Удаляет просроченный кеш (вызывается при 403/410 от YouTube)."""
    try:
        get_redis().delete(_stream_cache_key(track_id, source))
    except Exception:
        pass


# ── yt-dlp ИЗВЛЕЧЕНИЕ ─────────────────────────────────────────────────────────

def get_youtube_audio_stream_url(video_id_or_url: str) -> tuple:
    url = (video_id_or_url if video_id_or_url.startswith("http")
           else f"https://www.youtube.com/watch?v={video_id_or_url}")

    formats_to_try = [
        "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
        "bestaudio/best",
        "best[height<=480]/best",
        "best",
        None,
    ]

    for client in YT_CLIENTS:
        for fmt in formats_to_try:
            opts = {
                "quiet": True, "no_warnings": True,
                "nocheckcertificate": True, "skip_download": True,
                "extractor_args": {"youtube": {"player_client": [client]}},
            }
            if fmt is not None:
                opts["format"] = fmt
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    stream_url = info.get("url")
                    if stream_url:
                        print(f"[YouTube] ✓ '{client}'/'{fmt}': {video_id_or_url}")
                        return stream_url, info.get("http_headers", {})
            except Exception as e:
                err = str(e)
                if "Requested format is not available" in err:
                    continue
                if any(x in err for x in ("Please sign in", "Sign in", "no longer supported")):
                    print(f"[YouTube] Клиент '{client}' заблокирован")
                    break
                if any(x in err for x in ("Video unavailable", "Private video")):
                    return None, {}
                print(f"[YouTube] Ошибка ({client}/{fmt}): {err}")

    return None, {}


def search_youtube_candidates(query: str, exclude_id: str = None) -> list:
    ydl_opts = {"quiet": True, "extract_flat": True,
                "extractor_args": {"youtube": {"player_client": ["ios"]}}}
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
        print(f"[YouTube Search] Ошибка '{query}': {e}")
    return candidates


def build_search_queries(artist: str, title: str) -> list:
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
            seen.add(q); result.append(q)
    return result


def try_youtube_stream(query: str, exclude_id: str = None) -> tuple:
    candidates = search_youtube_candidates(query, exclude_id=exclude_id)
    for vid_id in candidates:
        # Проверяем кеш прежде чем запускать yt-dlp
        cached = _get_cached_url(vid_id, "youtube")
        if cached:
            return cached[0], cached[1]
        stream_url, headers = get_youtube_audio_stream_url(vid_id)
        if stream_url:
            _set_cached_url(vid_id, "youtube", stream_url, headers, "audio/webm")
            print(f"[YouTube Search] ✓ {vid_id}")
            return stream_url, headers
        print(f"[YouTube Search] {vid_id} заблокирован")
    return None, {}


def try_soundcloud_stream(artist: str, title: str) -> tuple:
    try:
        clean = re.sub(r"\([^)]*\)", "", title or "").strip() if title else ""
        query = f"{artist} {clean}" if (artist and clean) else (clean or artist or "Music")
        token = fetch_soundcloud_access_token()
        if not token:
            return None, None
        sc = SoundCloudPlugin(access_token=token)
        results = sc.search(query)
        if results:
            url = sc.get_stream_url(str(results[0].id))
            if url and "m3u8" not in url:
                print(f"[SoundCloud] ✓ {results[0].title}")
                return url, "audio/mpeg"
    except Exception as e:
        print(f"[SoundCloud] Ошибка: {e}")
    return None, None


# ─────────────────────────────────────────────────────────────────────────────
# ЭНДПОИНТ ПРЕДЗАГРУЗКИ
# ВАЖНО: /preload/{track_id} должен быть ВЫШЕ /{track_id} —
# иначе FastAPI распознаёт "preload" как track_id
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/preload/{track_id}")
def preload_track(
    track_id: str,
    source: str = Query("youtube"),
    title:  str = Query(None),
    artist: str = Query(None),
    db: Session = Depends(get_db),
):
    """
    Предзагрузка: резолвит URL через yt-dlp и кеширует его в Redis.
    Не стримит данные — только прогревает кеш для последующего быстрого ответа.
    Вызывается фронтендом в фоне для следующих треков в очереди.

    Типичный сценарий:
    1. Начинает играть трек N.
    2. Фронтенд вызывает preload для треков N+1, N+2.
    3. yt-dlp работает пока пользователь слушает N (3–4 мин).
    4. Когда начинает играть N+1 — URL уже в кеше, ответ мгновенный.
    """
    if source == "soundcloud" and len(track_id) == 11 and not track_id.isdigit():
        source = "youtube"

    # Уже в кеше — ничего делать не нужно
    if _get_cached_url(track_id, source):
        return {"status": "already_cached", "track_id": track_id}

    stream_url  = None
    media_type  = "audio/webm"
    yt_headers  = {}

    if source in ("youtube", "spotify"):
        yt_target = track_id
        if track_id.isdigit():
            t = db.query(models.Track).filter(models.Track.id == int(track_id)).first()
            yt_target = t.source_id if t else None

        if yt_target:
            stream_url, yt_headers = get_youtube_audio_stream_url(yt_target)
            if stream_url:
                _set_cached_url(yt_target, "youtube", stream_url, yt_headers, "audio/webm")
                return {"status": "cached", "track_id": yt_target}

        # Fallback — поиск по названию
        if not stream_url:
            for q in build_search_queries(artist or "", title or "")[:2]:
                stream_url, yt_headers = try_youtube_stream(q, exclude_id=yt_target)
                if stream_url:
                    break

    elif source == "soundcloud":
        stream_url, sc_media = try_soundcloud_stream(artist, title)
        if stream_url:
            media_type = sc_media or "audio/mpeg"
            _set_cached_url(track_id, source, stream_url, {}, media_type)
            return {"status": "cached", "track_id": track_id}

    if stream_url:
        _set_cached_url(track_id, source, stream_url, yt_headers, media_type)
        return {"status": "cached", "track_id": track_id}

    return {"status": "failed", "track_id": track_id}


# ─────────────────────────────────────────────────────────────────────────────
# ОСНОВНОЙ СТРИМИНГ
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{track_id}")
def stream_track(
    track_id: str,
    request: Request,
    source: str = Query("soundcloud"),
    title:  str = Query(None),
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
        yt_target = None if source == "spotify" else track_id
        if track_id.isdigit():
            t = db.query(models.Track).filter(models.Track.id == int(track_id)).first()
            yt_target = t.source_id if t else None
            print(f"[Stream DB] source_id = {yt_target}")

        # ── ПРОВЕРЯЕМ КЕШ СНАЧАЛА ────────────────────────────────────────────
        cache_key = yt_target or track_id
        cached = _get_cached_url(cache_key, "youtube")
        if cached:
            stream_url, yt_headers, media_type = cached
            send_headers.update(yt_headers)
            send_headers.pop("Accept-Encoding", None)
        else:
            # Попытка 1: прямой ID (медленно — запрашиваем yt-dlp)
            if yt_target:
                stream_url, yt_headers = get_youtube_audio_stream_url(yt_target)
                if stream_url:
                    send_headers.update(yt_headers)
                    send_headers.pop("Accept-Encoding", None)
                    media_type = "audio/webm"
                    # Кешируем для следующего запроса
                    _set_cached_url(yt_target, "youtube", stream_url, yt_headers, media_type)

            # Попытка 2: поиск по названию
            if not stream_url:
                for q in build_search_queries(artist or "", title or ""):
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
        # Проверяем кеш
        cached = _get_cached_url(track_id, "soundcloud")
        if cached:
            stream_url, _, media_type = cached
        else:
            try:
                token = fetch_soundcloud_access_token()
                sc = SoundCloudPlugin(access_token=token)
                stream_url = sc.get_stream_url(track_id)
                if stream_url and "m3u8" in stream_url:
                    print("[SoundCloud] HLS, переключаемся на YouTube...")
                    stream_url = None
                elif stream_url:
                    _set_cached_url(track_id, "soundcloud", stream_url, {}, "audio/mpeg")
                    media_type = "audio/mpeg"
            except Exception as e:
                print(f"[SoundCloud] Ошибка: {e}")
                stream_url = None

            if not stream_url:
                for q in build_search_queries(artist or "", title or ""):
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

        # Если YouTube вернул 403 (URL просрочен) — инвалидируем кеш и пробуем заново
        if remote_resp.status_code in (403, 410):
            print(f"[Stream] URL просрочен (HTTP {remote_resp.status_code}), инвалидируем кеш")
            _invalidate_stream_cache(yt_target or track_id, "youtube")
            fresh_url, fresh_headers = get_youtube_audio_stream_url(yt_target or track_id)
            if fresh_url:
                _set_cached_url(yt_target or track_id, "youtube",
                                fresh_url, fresh_headers, "audio/webm")
                send_headers.update(fresh_headers)
                send_headers.pop("Accept-Encoding", None)
                remote_resp = requests.get(fresh_url, headers=send_headers, stream=True, timeout=15)

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