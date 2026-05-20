from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..db.session import get_db
from ..db import models
#from auth import get_current_user   # ← добавили

router = APIRouter()


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

    return tracks[:limit]


# ---------------------------------------------------------
# 📌 Получить рекомендации (и обновить плейлист)
# ---------------------------------------------------------
@router.get("/user/{user_id}")
def get_user_recommendations(
    user_id: int,
    db: Session = Depends(get_db),
    #current_user: int = Depends(get_current_user)   # ← заменено
):
    #if user_id != current_user:
    #    raise HTTPException(status_code=403, detail="Access denied")

    playlist = (
        db.query(models.Playlist)
        .filter(
            models.Playlist.user_id == user_id,
            models.Playlist.type == "recommendations"
        )
        .first()
    )

    if not playlist:
        playlist = models.Playlist(
            name="Рекомендации",
            type="recommendations",
            user_id=user_id
        )
        db.add(playlist)
        db.commit()
        db.refresh(playlist)

    recommended_tracks = dummy_recommendations(db, user_id)

    playlist.tracks.clear()

    for track in recommended_tracks:
        playlist.tracks.append(track)

    db.commit()
    db.refresh(playlist)

    return {
        "playlist_id": playlist.id,
        "tracks": playlist.tracks
    }
