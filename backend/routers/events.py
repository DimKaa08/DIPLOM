# backend/routers/events.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..db.session import get_db
from ..db import models
from backend.routers.auth import get_current_user
from backend.services.cache import invalidate_recs   # ← НОВОЕ: инвалидация кеша

router = APIRouter(prefix="/activity", tags=["events"])


class TrackLogIn(BaseModel):
    track_id:        str
    listen_duration: int
    completion_rate: float
    is_finished:     bool
    is_looped:       bool
    was_skipped:     bool
    skip_position:   Optional[int]   = None
    skip_type:       Optional[str]   = "none"


@router.post("/log")
def log_track_interaction(
    payload: TrackLogIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    print(f"[AI Engine] Лог от юзера {current_user.id} на трек #{payload.track_id}")

    # Ищем трек по source_id (строка "dQw4w9WgXcQ"), а не по id (Integer PK)
    track = db.query(models.Track).filter(
        models.Track.source_id == payload.track_id
    ).first()

    # Если трека ещё нет в БД — создаём заглушку
    if not track:
        source = "youtube" if len(payload.track_id) == 11 else "soundcloud"
        track  = models.Track(
            source_id=payload.track_id,
            source=source,
            title="Unknown",
            artist="Unknown",
        )
        db.add(track)
        db.flush()

    # Вычисляем engagement score
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
    score += payload.completion_rate * 1.5

    # Обновляем или создаём запись взаимодействия
    existing = (
        db.query(models.UserInteraction)
        .filter(
            models.UserInteraction.user_id  == current_user.id,
            models.UserInteraction.track_id == track.id,
        )
        .first()
    )
    if existing:
        # Усредняем: повторное прослушивание уточняет оценку
        existing.engagement_score = round((existing.engagement_score + score) / 2, 2)
        existing.completion_rate  = round((existing.completion_rate + payload.completion_rate) / 2, 4)
        existing.is_looped        = existing.is_looped or payload.is_looped
    else:
        db.add(models.UserInteraction(
            user_id=current_user.id,
            track_id=track.id,
            listen_duration=payload.listen_duration,
            completion_rate=payload.completion_rate,
            is_finished=payload.is_finished,
            is_looped=payload.is_looped,
            was_skipped=payload.was_skipped,
            skip_position=payload.skip_position,
            skip_type=payload.skip_type,
            engagement_score=round(score, 2),
        ))

    # Обновляем профиль вкусов пользователя
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

    genres_map  = dict(pref.preferred_genres  or {})
    artists_map = dict(pref.preferred_artists or {})

    if track.genre:
        genres_map[track.genre] = round(genres_map.get(track.genre, 0.0) + score, 2)
    if track.artist and track.artist not in ("Unknown", ""):
        artists_map[track.artist] = round(artists_map.get(track.artist, 0.0) + score, 2)

    if payload.was_skipped and payload.skip_position:
        pref.skip_threshold = round(
            ((pref.skip_threshold or 30) + payload.skip_position) / 2, 1
        )

    pref.preferred_genres  = genres_map
    pref.preferred_artists = artists_map

    db.commit()

    # ── ИНВАЛИДАЦИЯ КЕША ──────────────────────────────────────────────────
    # После каждого нового взаимодействия кеш рекомендаций устаревает.
    # При следующем запросе /recommendations будет сгенерирован свежий список.
    invalidate_recs(current_user.id)

    return {
        "status":            "success",
        "message":           "Данные собраны, профиль ИИ обновлён",
        "calculated_score":  round(score, 2),
        "cache_invalidated": True,
    }