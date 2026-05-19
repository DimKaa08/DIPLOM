from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from db.session import get_db
from db import models

router = APIRouter()


# TODO: заменить на реальную авторизацию
def get_current_user_id() -> int:
    return 1


# ---------------------------------------------------------
# ⭐ Заглушка для рекомендаций (потом заменим на ML)
# ---------------------------------------------------------
def dummy_recommendations(db: Session, user_id: int, limit: int = 10) -> List[models.Track]:
    """
    Возвращает случайные треки как рекомендации.
    Потом заменим на ML-модель.
    """
    tracks = db.query(models.Track).all()

    if not tracks:
        return []

    # берём первые N треков (можно заменить на random.sample)
    return tracks[:limit]


# ---------------------------------------------------------
# 📌 Получить рекомендации (и обновить плейлист)
# ---------------------------------------------------------
@router.get("/user/{user_id}")
def get_user_recommendations(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user_id)
):
    if user_id != current_user:
        raise HTTPException(status_code=403, detail="Access denied")

    # ищем плейлист рекомендаций
    playlist = (
        db.query(models.Playlist)
        .filter(
            models.Playlist.user_id == user_id,
            models.Playlist.type == "recommendations"
        )
        .first()
    )

    # если нет — создаём
    if not playlist:
        playlist = models.Playlist(
            name="Рекомендации",
            type="recommendations",
            user_id=user_id
        )
        db.add(playlist)
        db.commit()
        db.refresh(playlist)

    # получаем рекомендации (заглушка)
    recommended_tracks = dummy_recommendations(db, user_id)

    # очищаем старые рекомендации
    playlist.tracks.clear()

    # добавляем новые
    for track in recommended_tracks:
        playlist.tracks.append(track)

    db.commit()
    db.refresh(playlist)

    return {
        "playlist_id": playlist.id,
        "tracks": playlist.tracks
    }
