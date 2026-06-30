# backend/routers/favorites.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from backend.db.session import get_db
from backend.db import models
from backend.routers.auth import get_current_user
from backend.services.event_logger import EventLogger

# Предполагается, что в main.py этот роутер подключается с prefix="/favorites"
router = APIRouter(prefix="/favorites", tags=["Favorites"])

class FavoriteRequest(BaseModel):
    track_id: str  
    title: str
    artist: str

class TrackSchema(BaseModel):
    id: str
    title: str
    artist: str
    youtube_url: str | None = None

    class Config:
        from_attributes = True


# 📌 1. Добавление в избранное
@router.post("/add")
def add_favorite(
    data: FavoriteRequest, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    track = db.query(models.Track).filter(models.Track.source_id == data.track_id).first()
    
    if not track:
        track = models.Track(
            source="youtube",
            source_id=data.track_id,
            title=data.title,
            artist=data.artist
        )
        db.add(track)
        db.commit()
        db.refresh(track)

    existing = (
        db.query(models.Favorite)
        .filter(
            models.Favorite.user_id == current_user.id,
            models.Favorite.track_id == track.id
        )
        .first()
    )
    if existing:
        return {"status": "already_exists", "favorite_id": existing.id}

    fav = models.Favorite(user_id=current_user.id, track_id=track.id)
    db.add(fav)
    db.commit()
    db.refresh(fav)

    EventLogger.log(db, current_user.id, data.track_id, "favorite")
    return {"status": "ok", "favorite_id": fav.id}


# 📌 2. Получение плейлиста "Избранное"
@router.get("")
def get_favorites(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    favorite_tracks = (
        db.query(models.Track)
        .join(models.Favorite, models.Track.id == models.Favorite.track_id)
        .filter(models.Favorite.user_id == current_user.id)
        .all()
    )
    
    result = []
    for t in favorite_tracks:
        result.append({
            "id": t.source_id,  
            "title": t.title,
            "artist": t.artist,
            "youtube_url": f"https://www.youtube.com/watch?v={t.source_id}"
        })
    return result


# 📌 3. Удаление из избранного (ИСПРАВЛЕНО: Безопасное удаление без 404 ошибки)
@router.delete("/remove/{track_id}")
def remove_favorite(
    track_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Ищем трек в глобальной таблице треков
    track = db.query(models.Track).filter(models.Track.source_id == track_id).first()
    
    # Если трека нет в базе данных, значит его точно нет и в избранном пользователя
    if not track:
        return {"status": "ok", "message": "Трека не было в избранном"}

    # Ищем связь в избранном
    fav = (
        db.query(models.Favorite)
        .filter(
            models.Favorite.user_id == current_user.id,
            models.Favorite.track_id == track.id
        )
        .first()
    )
    
    # Если связь найдена — удаляем её
    if fav:
        db.delete(fav)
        db.commit()
        # Логируем обратное действие для аналитики ML системы
        EventLogger.log(db, current_user.id, track_id, "unfavorite")
        return {"status": "ok", "message": "Успешно удалено из избранного"}
    
    return {"status": "ok", "message": "Трек уже удален из избранного"}