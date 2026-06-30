from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func  # Добавлено для случайной перемешки треков в БД
from typing import List, Optional

from backend.db.session import get_db
from backend.db import models
from backend.routers.auth import get_current_user
from backend.db.models import TrackBlacklist

router = APIRouter(prefix="/playlist", tags=["playlist"])

@router.post("/create")
def create_playlist(
    name: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    playlist = models.Playlist(
        name=name,
        type="custom",
        user_id=current_user.id
    )
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return {"status": "ok", "playlist_id": playlist.id}


@router.get("/list")
def list_playlists(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    playlists = (
        db.query(models.Playlist)
        .filter(models.Playlist.user_id == current_user.id)
        .all()
    )
    return playlists


@router.delete("/{playlist_id}/remove_track")
def remove_track_from_playlist(
    playlist_id: str,
    track_id: int,  
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Обработка удаления из Умных Рекомендаций
    if playlist_id == "recommendations":
        playlist = (
            db.query(models.Playlist)
            .filter(
                models.Playlist.user_id == current_user.id,
                models.Playlist.type == "recommendations"
            )
            .first()
        )
        if not playlist:
            playlist = models.Playlist(
                name="Рекомендации",
                type="recommendations",
                user_id=current_user.id
            )
            db.add(playlist)
            db.commit()
            db.refresh(playlist)

        # ЛОГИКА НЕГАТИВНОГО ФИДБЕКА: Заносим трек в черный список для ИИ
        already_blacklisted = db.query(TrackBlacklist).filter(
            TrackBlacklist.user_id == current_user.id,
            TrackBlacklist.track_id == track_id
        ).first()

        if not already_blacklisted:
            blacklist_entry = TrackBlacklist(user_id=current_user.id, track_id=track_id)
            db.add(blacklist_entry)
            db.commit()
            
    else:
        # Обработка удаления из обычных кастомных плейлистов
        try:
            playlist = (
                db.query(models.Playlist)
                .filter(models.Playlist.id == int(playlist_id), models.Playlist.user_id == current_user.id)
                .first()
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID плейлиста")

    if not playlist:
        raise HTTPException(status_code=404, detail="Плейлист не найден")

    # 2. Безопасный поиск трека
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    
    if not track:
        return {"status": "ok", "message": "Трек отсутствовал в БД, негативный фидбек учтен"}

    # 3. Удаление связи из таблицы отношений плейлиста
    if track in playlist.tracks:
        playlist.tracks.remove(track)
        db.commit()

    return {"status": "ok", "message": "Трек успешно скрыт и добавлен в черный список"}


@router.post("/{playlist_id}/add_track")
def add_track_to_playlist(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    playlist = (
        db.query(models.Playlist)
        .filter(models.Playlist.id == playlist_id, models.Playlist.user_id == current_user.id)
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


@router.get("/{playlist_id}/tracks")
def get_playlist_tracks(
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    playlist = (
        db.query(models.Playlist)
        .filter(models.Playlist.id == playlist_id, models.Playlist.user_id == current_user.id)
        .first()
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    return playlist.tracks


@router.get("/recommendations")
def get_recommendations_playlist(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Проверяем или инициализируем запись плейлиста рекомендаций для пользователя
    playlist = (
        db.query(models.Playlist)
        .filter(
            models.Playlist.user_id == current_user.id,
            models.Playlist.type == "recommendations"
        )
        .first()
    )

    if not playlist:
        playlist = models.Playlist(
            name="Рекомендации",
            type="recommendations",
            user_id=current_user.id
        )
        db.add(playlist)
        db.commit()
        db.refresh(playlist)

    # 2. ХАРД-ФИЛЬТР: Вытаскиваем все ID забаненных пользователем треков
    blacklisted_ids = [
        b.track_id for b in db.query(TrackBlacklist.track_id)
        .filter(TrackBlacklist.user_id == current_user.id)
        .all()
    ]

    # 3. ДИНАМИКА: Берем случайные треки из таблицы Track, исключая чёрный список
    query = db.query(models.Track)
    if blacklisted_ids:
        query = query.filter(models.Track.id.notin_(blacklisted_ids))
        
    # Выбираем 7 случайных треков при каждом вызове эндпоинта
    dynamic_random_tracks = query.order_by(func.random()).limit(7).all()

    # 4. Возвращаем JSON-структуру плейлиста со свежим набором треков
    return {
        "id": playlist.id,
        "name": playlist.name,
        "type": playlist.type,
        "user_id": playlist.user_id,
        "tracks": dynamic_random_tracks
    }