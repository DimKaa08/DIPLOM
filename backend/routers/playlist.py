# backend/routers/playlist.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from backend.db.session import get_db
from backend.db import models
from backend.routers.auth import get_current_user
from backend.db.models import TrackBlacklist

router = APIRouter(prefix="/playlist", tags=["playlist"])


def serialize_track(t: models.Track) -> dict:
    """
    Единый формат трека для всех эндпоинтов плейлиста.
    id = source_id (строка), чтобы совпадать с форматом избранного и поиска.
    """
    return {
        "id":            t.source_id,
        "source":        t.source        or "youtube",
        "title":         t.title         or "Unknown",
        "artist":        t.artist        or "Unknown",
        "duration":      t.duration      or 180,
        "thumbnail_url": t.thumbnail_url,
        "stream_url":    (
            f"/stream/{t.source_id}"
            f"?source={t.source or 'youtube'}"
            f"&title={t.title or ''}"
            f"&artist={t.artist or ''}"
        ),
    }


@router.post("/create")
def create_playlist(
    name: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    playlist = models.Playlist(name=name, type="custom", user_id=current_user.id)
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return {"status": "ok", "playlist_id": playlist.id}


@router.get("/list")
def list_playlists(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return (
        db.query(models.Playlist)
        .filter(models.Playlist.user_id == current_user.id)
        .all()
    )


# ИСПРАВЛЕНО: /recommendations стоит ВЫШЕ /{playlist_id}/tracks.
# FastAPI читает маршруты сверху вниз — если /{playlist_id}/tracks стоял первым,
# он перехватывал /recommendations как playlist_id="recommendations" и падал с ошибкой
# валидации (ожидал int, получал строку).
@router.get("/recommendations")
def get_recommendations_playlist(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    playlist = (
        db.query(models.Playlist)
        .filter(
            models.Playlist.user_id == current_user.id,
            models.Playlist.type == "recommendations",
        )
        .first()
    )
    if not playlist:
        playlist = models.Playlist(
            name="Рекомендации",
            type="recommendations",
            user_id=current_user.id,
        )
        db.add(playlist)
        db.commit()
        db.refresh(playlist)

    blacklisted_ids = [
        b.track_id
        for b in db.query(TrackBlacklist.track_id)
        .filter(TrackBlacklist.user_id == current_user.id)
        .all()
    ]

    query = db.query(models.Track)
    if blacklisted_ids:
        query = query.filter(models.Track.id.notin_(blacklisted_ids))

    random_tracks = query.order_by(func.random()).limit(15).all()

    # ИСПРАВЛЕНО: раньше возвращались сырые ORM-объекты, у которых id — Integer.
    # Фронтенд сравнивал track.id (число) с избранным track.id (source_id строка)
    # и всегда видел трек как "не в избранном" → дубликаты при лайке.
    # Теперь serialize_track() отдаёт id = source_id (строка "dQw4w9WgXcQ").
    return {
        "id":      playlist.id,
        "name":    playlist.name,
        "type":    playlist.type,
        "user_id": playlist.user_id,
        "tracks":  [serialize_track(t) for t in random_tracks],
    }


@router.get("/{playlist_id}/tracks")
def get_playlist_tracks(
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    playlist = (
        db.query(models.Playlist)
        .filter(
            models.Playlist.id == playlist_id,
            models.Playlist.user_id == current_user.id,
        )
        .first()
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    return [serialize_track(t) for t in playlist.tracks]


@router.post("/{playlist_id}/add_track")
def add_track_to_playlist(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    playlist = (
        db.query(models.Playlist)
        .filter(
            models.Playlist.id == playlist_id,
            models.Playlist.user_id == current_user.id,
        )
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


@router.delete("/{playlist_id}/remove_track")
def remove_track_from_playlist(
    playlist_id: str,
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if playlist_id == "recommendations":
        playlist = (
            db.query(models.Playlist)
            .filter(
                models.Playlist.user_id == current_user.id,
                models.Playlist.type == "recommendations",
            )
            .first()
        )
        if not playlist:
            playlist = models.Playlist(
                name="Рекомендации",
                type="recommendations",
                user_id=current_user.id,
            )
            db.add(playlist)
            db.commit()
            db.refresh(playlist)

        already_blacklisted = (
            db.query(TrackBlacklist)
            .filter(
                TrackBlacklist.user_id == current_user.id,
                TrackBlacklist.track_id == track_id,
            )
            .first()
        )
        if not already_blacklisted:
            db.add(TrackBlacklist(user_id=current_user.id, track_id=track_id))
            db.commit()
    else:
        try:
            playlist = (
                db.query(models.Playlist)
                .filter(
                    models.Playlist.id == int(playlist_id),
                    models.Playlist.user_id == current_user.id,
                )
                .first()
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID плейлиста")

    if not playlist:
        raise HTTPException(status_code=404, detail="Плейлист не найден")

    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        return {"status": "ok", "message": "Трек отсутствовал в БД, фидбек учтён"}

    if track in playlist.tracks:
        playlist.tracks.remove(track)
        db.commit()

    return {"status": "ok", "message": "Трек скрыт и добавлен в чёрный список"}