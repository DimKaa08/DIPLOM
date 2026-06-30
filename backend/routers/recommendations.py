# backend/routers/recommendations.py
import os
import torch
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from pydantic import BaseModel

from ..db.session import get_db
from ..db import models
from backend.plugins.base import TrackOut
from backend.routers.auth import get_current_user
from backend.ml.model import RecSysNN
from backend.ml.config import MODEL_PATH, MAPPINGS_PATH
from backend.plugins.soundcloud import SoundCloudPlugin
from backend.soundcloud_auth import fetch_soundcloud_access_token
from backend.ml.train import train_model

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

class ReplaceTrackRequest(BaseModel):
    track_id: str
    current_queue: List[str]

def safe_load_weights(model_instance, path: str):
    """Безопасно загружает веса нейросети, распаковывая вложенный state_dict"""
    if os.path.exists(path):
        checkpoint = torch.load(path, map_location=torch.device('cpu'))
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            model_instance.load_state_dict(checkpoint["state_dict"])
        else:
            model_instance.load_state_dict(checkpoint)
    model_instance.eval()
    return model_instance

def generate_ml_recommendations(db: Session, user_id: int, limit: int = 10) -> List[TrackOut]:
    # Получаем черный список
    blacklisted_ids = {
        b.track_id for b in db.query(models.RecommendationBlacklist)
        .filter(models.RecommendationBlacklist.user_id == user_id).all()
    }

    # Получаем историю взаимодействий
    interactions = db.query(models.UserInteraction).filter(
        models.UserInteraction.user_id == user_id
    ).order_by(models.UserInteraction.engagement_score.desc()).all()

    # Загружаем профиль накопленных предпочтений по Жанрам и Артистам
    pref = db.query(models.UserPreference).filter(models.UserPreference.user_id == user_id).first()
    preferred_genres = pref.preferred_genres if (pref and pref.preferred_genres) else {}
    preferred_artists = pref.preferred_artists if (pref and pref.preferred_artists) else {}

    # --- УМНЫЙ ХОЛОДНЫЙ СТАРТ (SoundCloud на основе любимого жанра) ---
    if len(interactions) < 3:
        # Пытаемся вытащить самый любимый жанр из логов, если он есть
        top_genre = max(preferred_genres, key=preferred_genres.get, default=None) if preferred_genres else None
        fallback_query = f"{top_genre} mix" if top_genre else "Top Hits"
        
        print(f"[Recs] Холодный старт для юзера {user_id}. Ищем в SoundCloud по тегу: {fallback_query}")

        try:
            token = fetch_soundcloud_access_token()
            sc_plugin = SoundCloudPlugin(access_token=token)
            raw_recs = sc_plugin.search(fallback_query)
            
            clean_recs = []
            for track in raw_recs:
                if str(track.id) in blacklisted_ids:
                    continue
                clean_recs.append(track)
                if len(clean_recs) >= limit:
                    break
            return clean_recs
        except Exception as e:
            print("[Recs Error] Ошибка авто-поиска SoundCloud при холодном старте:", e)

    # --- РАБОТА ГИБРИДНОЙ НЕЙРОСЕТИ PYTORCH + USER PREFERENCES ---
    try:
        model = RecSysNN(n_users=2000, n_items=10000) 
        model = safe_load_weights(model, MODEL_PATH)

        # Берем все треки из общей базы, чтобы прогнать их через сито рекомендаций
        all_tracks = db.query(models.Track).all()
        
        scored_tracks = []
        with torch.no_grad():
            for track in all_tracks:
                track_id = track.source_id
                if track_id in blacklisted_ids:
                    continue
                    
                # 1. Базовое предсказание PyTorch (Коллаборативный скор)
                user_tensor = torch.tensor([user_id % 2000], dtype=torch.long)
                item_idx = abs(hash(track_id)) % 10000
                item_tensor = torch.tensor([item_idx], dtype=torch.long)
                nn_score = model(user_tensor, item_tensor).item()
                
                # 2. Коррекция на основе карты вкусов (Контентный бустинг)
                # Если у пользователя в логах высокий балл по этому жанру/артисту — поднимаем трек выше
                genre_bonus = preferred_genres.get(track.genre, 0.0) * 0.2 if track.genre else 0.0
                artist_bonus = preferred_artists.get(track.artist, 0.0) * 0.3 if track.artist else 0.0
                
                final_score = nn_score + genre_bonus + artist_bonus
                scored_tracks.append((track, final_score))

        # Сортируем по финальному гибридному скору
        scored_tracks.sort(key=lambda x: x[1], reverse=True)
        
        # Исключаем треки, которые пользователь жестко скипнул в прошлый раз (score < 0.3)
        listened_bad_tracks = {i.track_id for i in interactions if i.engagement_score < 0.3}
        
        final_list = []
        for track, score in scored_tracks:
            if track.source_id in listened_bad_tracks:
                continue
            
            final_list.append(
                TrackOut(
                    id=track.source_id,
                    source=track.source,
                    title=track.title,
                    artist=track.artist if track.artist else "Выбор нейросети 🧠",
                    duration=180,
                    thumbnail_url=None
                )
            )
            if len(final_list) >= limit:
                break
                
        return final_list

    except Exception as e:
        print("Ошибка нейросети, включаем защитный фолбек по жанрам:", e)
        token = fetch_soundcloud_access_token()
        sc_plugin = SoundCloudPlugin(access_token=token)
        
        top_genre = max(preferred_genres, key=preferred_genres.get, default="Chill") if preferred_genres else "Chill"
        raw_recs = sc_plugin.search(f"{top_genre} mix")
        return [t for t in raw_recs if str(t.id) not in blacklisted_ids][:limit]


# 📌 Эндпоинт получения рекомендаций текущего пользователя
@router.get("")
def get_user_recommendations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    user_id = current_user.id

    playlist = (
        db.query(models.Playlist)
        .filter(models.Playlist.user_id == user_id, models.Playlist.type == "recommendations")
        .first()
    )

    if not playlist:
        playlist = models.Playlist(name="Умные рекомендации", type="recommendations", user_id=user_id)
        db.add(playlist)
        db.commit()
        db.refresh(playlist)

    recommended_tracks = generate_ml_recommendations(db, user_id, limit=15)
    playlist.tracks.clear()
    
    for track in recommended_tracks:
        db_track = db.query(models.Track).filter(models.Track.source_id == track.id).first()
        if not db_track:
            db_track = models.Track(source_id=track.id, source=track.source, title=track.title, artist=track.artist)
            db.add(db_track)
            db.flush() 
            
        playlist.tracks.append(db_track)

    db.commit()
    db.refresh(playlist)

    return {
        "playlist_id": playlist.id,
        "tracks": [
            {
                "id": t.source_id, 
                "title": t.title,
                "artist": t.artist,
                "source": t.source,
                "stream_url": f"/stream/{t.source_id}?source={t.source}&title={t.title}&artist={t.artist}"
            }
            for t in playlist.tracks
        ]
    }


# 📌 Эндпоинт мгновенной замены пропущенного трека (Учитывает и Жанры, и Артистов)
@router.post("/replace")
def replace_track_in_queue(
    data: ReplaceTrackRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Фиксируем мгновенный сброс (сигнал для ИИ)
    negative_interaction = models.UserInteraction(
        user_id=current_user.id,
        track_id=data.track_id,
        source="youtube" if len(data.track_id) == 11 else "soundcloud",
        engagement_score=0.0,
        listen_duration=0,
        completion_rate=0.0,
        is_finished=False,
        is_looped=False,
        was_skipped=True,
        skip_type="immediate"
    )
    db.add(negative_interaction)
    
    # Извлекаем предпочтения из логов
    pref = db.query(models.UserPreference).filter(models.UserPreference.user_id == current_user.id).first()
    preferred_artists = [a for a, score in pref.preferred_artists.items() if score > 0] if pref else []
    preferred_genres = [g for g, score in pref.preferred_genres.items() if score > 0] if pref else []
    
    blacklist = {b.track_id for b in db.query(models.RecommendationBlacklist).filter(models.RecommendationBlacklist.user_id == current_user.id).all()}
    exclude_ids = set(data.current_queue) | blacklist | {data.track_id}
    
    replacement = None
    
    # Стратегия 1: Ищем трек любимого исполнителя
    if preferred_artists:
        replacement = db.query(models.Track).filter(
            models.Track.artist.in_(preferred_artists),
            ~models.Track.source_id.in_(exclude_ids)
        ).order_by(func.random()).first()
        
    # Стратегия 2: Если артистов нет, ищем по любимым жанрам
    if not replacement and preferred_genres:
        replacement = db.query(models.Track).filter(
            models.Track.genre.in_(preferred_genres),
            ~models.Track.source_id.in_(exclude_ids)
        ).order_by(func.random()).first()
        
    # Стратегия 3: Ротация из общей базы данных
    if not replacement:
        replacement = db.query(models.Track).filter(
            ~models.Track.source_id.in_(exclude_ids)
        ).order_by(func.random()).first()

    # Стратегия 4: Запрос к SoundCloud на основе лучшего жанра
    if not replacement:
        try:
            token = fetch_soundcloud_access_token()
            sc_plugin = SoundCloudPlugin(access_token=token)
            q = preferred_artists[0] if preferred_artists else (preferred_genres[0] if preferred_genres else "Chill mix")
            sc_tracks = sc_plugin.search(q)
            for t in sc_tracks:
                if str(t.id) not in exclude_ids:
                    replacement = models.Track(source_id=str(t.id), source=t.source, title=t.title, artist=t.artist)
                    db.add(replacement)
                    break
        except Exception:
            pass

    if not replacement:
        raise HTTPException(status_code=404, detail="Нет доступных треков для замены")
        
    db.commit()
    
    return {
        "id": replacement.source_id,
        "title": replacement.title,
        "artist": replacement.artist,
        "source": replacement.source,
        "stream_url": f"/stream/{replacement.source_id}?source={replacement.source}&title={replacement.title}&artist={replacement.artist}"
    }


# 📌 Эндпоинт: Полное удаление трека из текущей выдачи и перманентный бан
@router.post("/hide/{track_id}")
def hide_track_from_recommendations(
    track_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    user_id = current_user.id

    already_blocked = db.query(models.RecommendationBlacklist).filter(
        models.RecommendationBlacklist.user_id == user_id,
        models.RecommendationBlacklist.track_id == track_id
    ).first()

    if not already_blocked:
        blacklist_entry = models.RecommendationBlacklist(user_id=user_id, track_id=track_id)
        db.add(blacklist_entry)
    
    existing_interaction = db.query(models.UserInteraction).filter(
        models.UserInteraction.user_id == user_id,
        models.UserInteraction.track_id == track_id
    ).first()

    if existing_interaction:
        existing_interaction.engagement_score = 0.0
    else:
        negative_interaction = models.UserInteraction(
            user_id=user_id,
            track_id=track_id,
            source="youtube" if len(track_id) == 11 else "soundcloud",
            engagement_score=0.0,
            listen_duration=0,
            completion_rate=0.0,
            is_finished=False,
            is_looped=False,
            was_skipped=True,
            skip_type="immediate"
        )
        db.add(negative_interaction)

    playlist = (
        db.query(models.Playlist)
        .filter(models.Playlist.user_id == user_id, models.Playlist.type == "recommendations")
        .first()
    )

    if playlist:
        db_track = db.query(models.Track).filter(models.Track.source_id == track_id).first()
        if db_track and db_track in playlist.tracks:
            playlist.tracks.remove(db_track)

    db.commit()
    return {"status": "ok", "message": "Трек полностью удален из текущих и будущих рекомендаций"}

@router.post("/train-now")
def trigger_ml_training(current_user: models.User = Depends(get_current_user)):
    # В реальном проекте тут нужна проверка if not current_user.is_admin
    # Но для диплома достаточно, чтобы авторизованный юзер мог нажать кнопку
    
    success = train_model(epochs=5, batch_size=16)
    if not success:
        raise HTTPException(
            status_code=400, 
            detail="Недостаточно данных для запуска обучения. Послушайте больше треков!"
        )
    return {"status": "success", "message": "Нейросеть успешно переобучена на новых логах бд!"}