# backend/routers/events.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ..db.session import get_db
from ..db import models
from backend.routers.auth import get_current_user

# ИСПРАВЛЕНО: Префикс изменен на /activity, чтобы эндпоинт полностью совпадал с запросом фронтенда (/activity/log)
router = APIRouter(prefix="/activity", tags=["events"])

# Схема данных, которую теперь присылает наш продвинутый React-плеер
class TrackLogIn(BaseModel):
    # ИСПРАВЛЕНО: Изменено на str, чтобы валидировать строковые хэши и внешние ID (например, "#WIKqgE4BwAY")
    track_id: str  
    listen_duration: int
    completion_rate: float
    is_finished: bool
    is_looped: bool
    was_skipped: bool
    skip_position: Optional[int] = None
    skip_type: str  # 'immediate', 'partial', 'none'


# backend/routers/events.py — стало
@router.post("/log")
def log_track_interaction(
    payload: TrackLogIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    print(f"[AI Engine] Лог от юзера {current_user.id} на трек #{payload.track_id}")

    # ✅ Ищем по source_id — это строковый внешний ID ("dQw4w9WgXcQ")
    track = db.query(models.Track).filter(
        models.Track.source_id == payload.track_id
    ).first()

    # Если трека ещё нет в БД — создаём его на лету
    # (такое бывает при первом прослушивании до добавления в избранное)
    if not track:
        track = models.Track(
            source_id=payload.track_id,
            source="youtube" if len(payload.track_id) == 11 else "soundcloud",
            title="Unknown",
            artist="Unknown"
        )
        db.add(track)
        db.flush()  # flush, не commit — получаем track.id без закрытия транзакции

    # Теперь track.id — это корректный Integer для FK в UserInteraction
    score = 0.0
    if payload.is_finished:
        score += 2.0
    if payload.is_looped:
        score += 3.0

    if payload.was_skipped:
        if payload.skip_type == "immediate":
            score -= 2.0
        elif payload.skip_type == "partial":
            score -= 0.5

    score += (payload.completion_rate * 1.5)

    # ✅ track.id — Integer FK, всё совпадает с моделью
    new_interaction = models.UserInteraction(
        user_id=current_user.id,
        track_id=track.id,          # ← Integer PK, не строка
        listen_duration=payload.listen_duration,
        completion_rate=payload.completion_rate,
        is_finished=payload.is_finished,
        is_looped=payload.is_looped,
        was_skipped=payload.was_skipped,
        skip_position=payload.skip_position,
        skip_type=payload.skip_type,
        engagement_score=round(score, 2)
    )
    db.add(new_interaction)

    # Обновляем профиль вкусов пользователя
    pref = db.query(models.UserPreference).filter(
        models.UserPreference.user_id == current_user.id
    ).first()
    if not pref:
        pref = models.UserPreference(
            user_id=current_user.id,
            preferred_genres={},
            preferred_artists={}
        )
        db.add(pref)

    genres_map  = dict(pref.preferred_genres)
    artists_map = dict(pref.preferred_artists)

    if track.genre:
        genres_map[track.genre] = round(genres_map.get(track.genre, 0.0) + score, 2)
    if track.artist and track.artist != "Unknown":
        artists_map[track.artist] = round(artists_map.get(track.artist, 0.0) + score, 2)

    pref.preferred_genres  = genres_map
    pref.preferred_artists = artists_map

    if payload.was_skipped and payload.skip_position:
        pref.skip_threshold = round((pref.skip_threshold + payload.skip_position) / 2, 1)

    db.commit()

    return {
        "status": "success",
        "message": "Данные собраны, профиль ИИ обновлён",
        "calculated_score": round(score, 2)
    }
   