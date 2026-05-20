from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.db.session import get_db
from backend.db import models
#from auth import get_current_user

router = APIRouter()


# -----------------------------
# 📌 Создать плейлист
# -----------------------------
@router.post("/create")
def create_playlist(
    name: str,
    db: Session = Depends(get_db),
    #user_id: int = Depends(get_current_user)   # ← заменено
):
    playlist = models.Playlist(
        name=name,
        type="custom",
        #user_id=user_id
    )
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return {"status": "ok", "playlist_id": playlist.id}


# -----------------------------
# 📌 Получить все плейлисты пользователя
# -----------------------------
@router.get("/list")
def list_playlists(
    db: Session = Depends(get_db),
    #user_id: int = Depends(get_current_user)   # ← заменено
):
    playlists = (
        db.query(models.Playlist)
        #.filter(models.Playlist.user_id == user_id)
        .all()
    )
    return playlists


# -----------------------------
# 📌 Удалить плейлист
# -----------------------------
@router.delete("/delete/{playlist_id}")
def delete_playlist(
    playlist_id: int,
    db: Session = Depends(get_db),
    #user_id: int = Depends(get_current_user)   # ← заменено
):
    playlist = (
        db.query(models.Playlist)
        .filter(models.Playlist.id == playlist_id)#, models.Playlist.user_id == user_id)
        .first()
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    db.delete(playlist)
    db.commit()
    return {"status": "ok"}


# -----------------------------
# 📌 Добавить трек в плейлист
# -----------------------------
@router.post("/{playlist_id}/add_track")
def add_track_to_playlist(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db),
    #user_id: int = Depends(get_current_user)   # ← заменено
):
    playlist = (
        db.query(models.Playlist)
        .filter(models.Playlist.id == playlist_id)#, models.Playlist.user_id == user_id)
        .first()
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    playlist.tracks.append(track)
    db.commit()

    return {"status": "ok"}


# -----------------------------
# 📌 Удалить трек из плейлиста
# -----------------------------
@router.delete("/{playlist_id}/remove_track")
def remove_track_from_playlist(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db),
    #user_id: int = Depends(get_current_user)   # ← заменено
):
    playlist = (
        db.query(models.Playlist)
        .filter(models.Playlist.id == playlist_id)#, models.Playlist.user_id == user_id)
        .first()
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if track in playlist.tracks:
        playlist.tracks.remove(track)
        db.commit()

    return {"status": "ok"}


# -----------------------------
# 📌 Получить треки плейлиста
# -----------------------------
@router.get("/{playlist_id}/tracks")
def get_playlist_tracks(
    playlist_id: int,
    db: Session = Depends(get_db),
    #user_id: int = Depends(get_current_user)   # ← заменено
):
    playlist = (
        db.query(models.Playlist)
        .filter(models.Playlist.id == playlist_id)#, models.Playlist.user_id == user_id)
        .first()
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    return playlist.tracks


# -----------------------------
# ⭐ Специальный плейлист «Рекомендации»
# -----------------------------
@router.get("/recommendations")
def get_recommendations_playlist(
    db: Session = Depends(get_db),
    #user_id: int = Depends(get_current_user)   # ← заменено
):
    playlist = (
        db.query(models.Playlist)
        .filter(
            #models.Playlist.user_id == user_id,
            models.Playlist.type == "recommendations"
        )
        .first()
    )

    # если нет — создаём автоматически
    if not playlist:
        playlist = models.Playlist(
            name="Рекомендации",
            type="recommendations",
            #user_id=user_id
        )
        db.add(playlist)
        db.commit()
        db.refresh(playlist)

    return playlist
