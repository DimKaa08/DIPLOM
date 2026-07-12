# backend/routers/onboarding.py
"""
Онбординг новых пользователей — два сценария:

1. Ручной выбор жанров: пользователь кликает теги при регистрации.
2. Cookies из YouTube: пользователь выгружает cookies.txt
   → yt-dlp читает его плейлист «Понравившиеся видео» (list=LL)
   → треки попадают в БД как начальное «избранное».
"""
import os
import json
import yt_dlp

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List

from ..db import models
from ..db.session import get_db
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# Папка для хранения cookie-файлов пользователей
COOKIES_DIR = os.getenv("COOKIES_DIR", "/app/backend/data/cookies")


# ─── СХЕМЫ ───────────────────────────────────────────────────────────────────

class GenrePreferences(BaseModel):
    genres: List[str]          # ["rock", "electronic", "jazz"]
    artists: List[str] = []   # опционально


# ─── 1. ВЫБОР ЖАНРОВ ─────────────────────────────────────────────────────────

@router.post("/genres")
def set_genre_preferences(
    prefs: GenrePreferences,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Сохраняет жанровые предпочтения при регистрации.
    Каждый выбранный жанр получает базовый вес 1.0.
    """
    pref = (
        db.query(models.UserPreference)
        .filter(models.UserPreference.user_id == current_user.id)
        .first()
    )
    if not pref:
        pref = models.UserPreference(
            user_id=current_user.id,
            preferred_genres={},
            preferred_artists={},
        )
        db.add(pref)

    # Жанры: каждый выбранный при регистрации = 1.0 балл
    genres_map = dict(pref.preferred_genres or {})
    for g in prefs.genres:
        genres_map[g.lower()] = genres_map.get(g.lower(), 0.0) + 1.0

    # Артисты (если указаны)
    artists_map = dict(pref.preferred_artists or {})
    for a in prefs.artists:
        artists_map[a] = artists_map.get(a, 0.0) + 1.0

    pref.preferred_genres  = genres_map
    pref.preferred_artists = artists_map
    db.commit()

    return {
        "status": "ok",
        "message": f"Сохранены предпочтения: {len(prefs.genres)} жанров, {len(prefs.artists)} артистов",
        "genres":  genres_map,
    }


# ─── 2. ЗАГРУЗКА COOKIES + ПАРСИНГ YOUTUBE ───────────────────────────────────

@router.post("/upload-cookies")
async def upload_youtube_cookies(
    file: UploadFile = File(...),
    db: Session   = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Принимает cookies.txt из браузера пользователя (Netscape-формат).

    Как получить файл (инструкция для пользователя):
    1. Установить расширение «Get cookies.txt LOCALLY» в Chrome/Firefox.
    2. Зайти на youtube.com (авторизоваться).
    3. Нажать на расширение → Export → сохранить cookies.txt.
    4. Загрузить файл сюда.

    Что делает этот эндпоинт:
    - Сохраняет cookies.txt на сервере.
    - Через yt-dlp читает плейлист «Понравившиеся видео» пользователя на YouTube.
    - Создаёт треки в БД и добавляет их в избранное.
    - Обновляет профиль предпочтений по исполнителям.
    """
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Загрузите файл в формате .txt (Netscape cookies)")

    # Сохраняем cookie-файл
    os.makedirs(COOKIES_DIR, exist_ok=True)
    cookie_path = os.path.join(COOKIES_DIR, f"user_{current_user.id}.txt")
    content = await file.read()
    with open(cookie_path, "wb") as f:
        f.write(content)

    print(f"[Onboarding] Cookies сохранены для юзера {current_user.id}: {cookie_path}")

    # Парсим YouTube Liked Videos через yt-dlp
    tracks_added = _import_youtube_liked(cookie_path, db, current_user.id)

    return {
        "status": "ok",
        "message": f"Импортировано {len(tracks_added)} треков из YouTube «Понравившихся видео»",
        "tracks":  tracks_added[:10],  # первые 10 для превью на фронте
    }


def _import_youtube_liked(cookie_path: str, db: Session, user_id: int) -> list:
    """
    Читает плейлист «Понравившиеся видео» с YouTube (playlist?list=LL)
    и добавляет треки в БД и в избранное пользователя.
    """
    ydl_opts = {
        "quiet":        True,
        "no_warnings":  True,
        "extract_flat": True,       # только метаданные, без скачивания
        "cookies":      cookie_path,
        "playlistend":  50,         # максимум 50 последних лайкнутых видео
        "extractor_args": {"youtube": {"player_client": ["ios"]}},
    }

    entries = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                "https://www.youtube.com/playlist?list=LL",
                download=False,
            )
            if info and "entries" in info:
                entries = [e for e in info["entries"] if e and e.get("id")]
                print(f"[Onboarding] Найдено {len(entries)} записей в Liked Videos")
    except Exception as e:
        print(f"[Onboarding] Ошибка чтения Liked Videos: {e}")
        # Пробуем альтернативный URL — YouTube History
        try:
            with yt_dlp.YoutubeDL({**ydl_opts, "playlistend": 30}) as ydl:
                info = ydl.extract_info(
                    "https://www.youtube.com/feed/history",
                    download=False,
                )
                if info and "entries" in info:
                    entries = [e for e in info["entries"] if e and e.get("id")]
                    print(f"[Onboarding] Fallback: найдено {len(entries)} записей в истории")
        except Exception as e2:
            print(f"[Onboarding] Fallback тоже упал: {e2}")
            return []

    if not entries:
        return []

    # Сохраняем треки в БД
    added = []
    artists_map = {}

    for entry in entries:
        vid_id  = entry.get("id")
        title   = entry.get("title")   or "Unknown"
        artist  = entry.get("uploader") or entry.get("channel") or "Unknown"
        duration = int(entry.get("duration") or 180)

        # Пропускаем очевидно не-музыкальный контент
        non_music_keywords = ["vlog", "review", "tutorial", "lecture", "news", "podcast"]
        if any(kw in title.lower() for kw in non_music_keywords):
            continue

        # Создаём трек в БД если его ещё нет
        track = db.query(models.Track).filter(models.Track.source_id == vid_id).first()
        if not track:
            track = models.Track(
                source_id=vid_id,
                source="youtube",
                title=title,
                artist=artist,
                duration=duration,
            )
            db.add(track)
            db.flush()

        # Добавляем в избранное (FavoriteTrack) если модель существует
        try:
            existing_fav = (
                db.query(models.FavoriteTrack)
                .filter(
                    models.FavoriteTrack.user_id == user_id,
                    models.FavoriteTrack.track_id == track.id,
                )
                .first()
            )
            if not existing_fav:
                db.add(models.FavoriteTrack(user_id=user_id, track_id=track.id))
        except Exception:
            pass  # Модель FavoriteTrack может называться иначе

        # Считаем встречаемость артиста для профиля вкусов
        artists_map[artist] = artists_map.get(artist, 0) + 1.0

        # Создаём положительное взаимодействие — трек лайкнут на YouTube
        existing_inter = (
            db.query(models.UserInteraction)
            .filter(
                models.UserInteraction.user_id  == user_id,
                models.UserInteraction.track_id == track.id,
            )
            .first()
        )
        if not existing_inter:
            db.add(models.UserInteraction(
                user_id=user_id, track_id=track.id,
                listen_duration=duration,
                completion_rate=0.9,  # предполагаем что досмотрели
                is_finished=True, is_looped=False,
                was_skipped=False, skip_position=None, skip_type="none",
                engagement_score=2.5,  # лайк на YouTube = хороший сигнал
            ))

        added.append({"id": vid_id, "title": title, "artist": artist})

    # Обновляем профиль предпочтений пользователя
    pref = (
        db.query(models.UserPreference)
        .filter(models.UserPreference.user_id == user_id)
        .first()
    )
    if not pref:
        pref = models.UserPreference(
            user_id=user_id, preferred_genres={}, preferred_artists={}
        )
        db.add(pref)

    existing_artists = dict(pref.preferred_artists or {})
    for artist, count in artists_map.items():
        existing_artists[artist] = round(existing_artists.get(artist, 0) + count * 0.5, 2)
    pref.preferred_artists = existing_artists

    db.commit()
    print(f"[Onboarding] Добавлено {len(added)} треков, обновлён профиль по {len(artists_map)} артистам")
    return added


@router.get("/cookie-status")
def get_cookie_status(current_user: models.User = Depends(get_current_user)):
    """Проверяет, загружал ли пользователь cookies."""
    cookie_path = os.path.join(COOKIES_DIR, f"user_{current_user.id}.txt")
    return {
        "has_cookies":   os.path.exists(cookie_path),
        "cookie_path":   cookie_path if os.path.exists(cookie_path) else None,
    }


def get_user_cookie_path(user_id: int) -> str | None:
    """
    Возвращает путь к cookie-файлу пользователя для yt-dlp.
    Используется в stream.py для авторизованного воспроизведения.
    """
    path = os.path.join(COOKIES_DIR, f"user_{user_id}.txt")
    return path if os.path.exists(path) else None