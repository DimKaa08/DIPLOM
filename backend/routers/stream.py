# backend/routers/stream.py
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
    """
    Вытаскивает прямой URL аудиопотока И оригинальные http-заголовки yt-dlp.
    Умеет принимать как 11-значный ID, так и полную ссылку на YouTube.
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'skip_download': True,
    }
    try:
        # Если передана полная ссылка, используем её напрямую, иначе собираем из ID
        if video_id_or_url.startswith("http://") or video_id_or_url.startswith("https://"):
            video_url = video_id_or_url
        else:
            video_url = f"https://www.youtube.com/watch?v={video_id_or_url}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            # Возвращаем сам URL и заголовки, которые использовал yt-dlp для прохождения проверки
            return info.get('url'), info.get('http_headers', {})
    except Exception as e:
        print(f"[YouTube Extractor] Ошибка получения стрима для {video_id_or_url}: {e}")
        return None, {}


def search_youtube_fallback(query: str) -> str:
    """Быстрый поиск трека на YouTube для подмены."""
    ydl_opts = {'quiet': True, 'extract_flat': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if res and 'entries' in res and len(res['entries']) > 0:
                return res['entries'][0].get('id')
    except Exception as e:
        print(f"[YouTube Fallback] Не удалось найти замену для запроса '{query}': {e}")
    return None


@router.get("/{track_id}")
def stream_track(
    track_id: str,
    request: Request,  # Перехватываем объект запроса FastAPI для чтения Range заголовков браузера
    source: str = Query("soundcloud"),
    title: str = Query(None),
    artist: str = Query(None),
    db: Session = Depends(get_db)  # ДОБАВЛЕНО: Доступ к БД для разрешения внутренних числовых ID
):
    if source == "soundcloud" and len(track_id) == 11:
        print(f"[Stream AutoFix] Обнаружен YouTube ID '{track_id}' под маской soundcloud.")
        source = "youtube"

    print(f"[Stream Router] Запрос потока: {artist} - {title} [Source: {source}, ID: {track_id}]")

    # Готовим заголовки для отправки удаленному серверу
    send_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # Пересылаем Range-запрос из браузера (например, bytes=0-), если он есть
    client_range = request.headers.get("range")
    if client_range:
        send_headers["Range"] = client_range

    stream_url = None
    media_type = "audio/mpeg"

    # --- ЛОГИКА ОПРЕДЕЛЕНИЯ ИСТОЧНИКА ---
    if source == "youtube" or source == "spotify":
        if source == "spotify":
            search_query = f"{artist} {title}"
            yt_target = search_youtube_fallback(search_query)
        else:
            # Если источник YouTube, проверяем: это числовой ID из нашей БД или прямой хэш YouTube
            if track_id.isdigit():
                print(f"[Stream DB] Распознан внутренний ID базы данных: {track_id}. Ищем оригинальный трек...")
                track_in_db = db.query(models.Track).filter(models.Track.id == int(track_id)).first()
                
                yt_target = None
                if track_in_db:
                    # БЕЗОПАСНЫЙ ПОИСК: последовательно перебираем возможные варианты названия колонок в твоей БД
                    possible_attrs = ['youtube_id', 'video_id', 'link', 'source_id', 'track_url', 'uri', 'url']
                    for attr in possible_attrs:
                        if hasattr(track_in_db, attr) and getattr(track_in_db, attr):
                            yt_target = getattr(track_in_db, attr)
                            print(f"[Stream DB] Успешно подтянуто поле '{attr}': {yt_target}")
                            break
                
                # Если поле не нашлось или такого трека вообще нет в БД — спасаем ситуацию поиском по названию
                if not yt_target:
                    print(f"[Stream DB] Не удалось извлечь ссылку из модели Track. Включаем текстовый поиск-fallback...")
                    search_query = f"{artist} {title}" if (artist and title) else "Music"
                    yt_target = search_youtube_fallback(search_query)
            else:
                # Это нормальный 11-символьный хэш YouTube, передаем как есть
                yt_target = track_id

        if yt_target:
            stream_url, yt_headers = get_youtube_audio_stream_url(yt_target)
            if stream_url:
                send_headers.update(yt_headers)  # Подмешиваем заголовки yt-dlp, чтобы обойти 403 ошибку
                send_headers.pop("Accept-Encoding", None)  # Убираем сжатие, ломающее потоковое чтение видео
                media_type = "audio/webm"

    elif source == "soundcloud":
        try:
            access_token = fetch_soundcloud_access_token()
            soundcloud_plugin = SoundCloudPlugin(access_token=access_token)
            stream_url = soundcloud_plugin.get_stream_url(track_id)
            
            # Если поток SoundCloud содержит .m3u8 (HLS), requests.get его не прочитает напрямую.
            # В таком случае безопаснее переключиться на YouTube резерв.
            if stream_url and "m3u8" in stream_url:
                print("[SoundCloud Proxy] Обнаружен HLS поток (.m3u8). Включаем YouTube-спасатель...")
                stream_url = None
        except Exception as sc_error:
            print(f"[SoundCloud Error] {sc_error}. Переключаемся на YouTube...")
            stream_url = None

        # Резервный запуск через YouTube, если SoundCloud дал сбой
        if not stream_url:
            search_query = f"{artist} {title}" if (artist and title) else "Music"
            yt_id = search_youtube_fallback(search_query)
            if yt_id:
                stream_url, yt_headers = get_youtube_audio_stream_url(yt_id)
                if stream_url:
                    send_headers.update(yt_headers)
                    send_headers.pop("Accept-Encoding", None)
                    media_type = "audio/webm"

    if not stream_url:
        raise HTTPException(status_code=404, detail="Не удалось получить аудиопоток")

    # --- ПРОКСИРОВАНИЕ И ПЕРЕДАЧА ДИАПАЗОНОВ (RANGE) ---
    try:
        # Делаем стриминг-запрос к источнику с нашими скорректированными заголовками
        remote_resp = requests.get(stream_url, headers=send_headers, stream=True, timeout=15)
        
        # Собираем заголовки ответа, которые критически важны для браузерного аудио-плеера
        response_headers = {
            "Accept-Ranges": "bytes"
        }
        if "Content-Range" in remote_resp.headers:
            response_headers["Content-Range"] = remote_resp.headers["Content-Range"]
        if "Content-Length" in remote_resp.headers:
            response_headers["Content-Length"] = remote_resp.headers["Content-Length"]

        # Возвращаем поток чанками, передавая статус ответа сервера (часто 206 Partial Content)
        return StreamingResponse(
            remote_resp.iter_content(chunk_size=1024 * 64),  # Читаем блоками по 64 КБ
            status_code=remote_resp.status_code,
            headers=response_headers,
            media_type=media_type
        )

    except Exception as e:
        print(f"[Proxy Стрим] Критическая ошибка при трансляции: {e}")
        raise HTTPException(status_code=500, detail="Ошибка работы стриминг-прокси")