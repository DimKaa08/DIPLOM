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


@router.post("/log")
def log_track_interaction(
    payload: TrackLogIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    print(f"[AI Engine] Лог от юзера {current_user.id} на трек #{payload.track_id}")

    # 1. Находим трек в базе, чтобы вытащить его Жанр и Артиста
    track = db.query(models.Track).filter(models.Track.id == payload.track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Трек не найден в базе данных")

    # 2. Алгоритм расчета веса (Engagement Score) на бэкенде
    score = 0.0
    if payload.is_finished:
        score += 2.0  # Дослушал до конца — отлично
    if payload.is_looped:
        score += 3.0  # Поставил на репит — супер-лайк
        
    if payload.was_skipped:
        if payload.skip_type == "immediate":
            score -= 2.0  # Скипнул сразу же (<10 сек) — трек не нравится
        elif payload.skip_type == "partial":
            score -= 0.5  # Немного послушал и скипнул — нейтрально-негативно

    # Добавляем удержание в коэффицент (от 0.0 до 1.5 очков)
    score += (payload.completion_rate * 1.5)

    # 3. Сохраняем это конкретное прослушивание в лог для датасета ИИ
    new_interaction = models.UserInteraction(
        user_id=current_user.id,
        track_id=payload.track_id,
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

    # 4. Обновляем кумулятивный профиль вкусов юзера (UserPreference) для быстрого поиска
    pref = db.query(models.UserPreference).filter(models.UserPreference.user_id == current_user.id).first()
    if not pref:
        pref = models.UserPreference(user_id=current_user.id, preferred_genres={}, preferred_artists={})
        db.add(pref)

    # Загружаем текущие веса из JSONB (делаем копии, так как SQLAlchemy капризна к мутациям dict)
    genres_map = dict(pref.preferred_genres)
    artists_map = dict(pref.preferred_artists)

    # Плюсуем/минусуем очки жанру трека
    if track.genre:
        genres_map[track.genre] = round(genres_map.get(track.genre, 0.0) + score, 2)
        
    # Плюсуем/минусуем очки исполнителю трека
    if track.artist:
        artists_map[track.artist] = round(artists_map.get(track.artist, 0.0) + score, 2)

    # Сохраняем обновленные карты весов обратно в модель
    pref.preferred_genres = genres_map
    pref.preferred_artists = artists_map

    # Корректируем средний порог терпения юзера при скипах
    if payload.was_skipped and payload.skip_position:
        pref.skip_threshold = round((pref.skip_threshold + payload.skip_position) / 2, 1)

    db.commit()
    
    return {
        "status": "success", 
        "message": "Данные собраны, профиль ИИ обновлен", 
        "calculated_score": round(score, 2)
    }