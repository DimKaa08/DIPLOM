# backend/routers/recommendations.py
import os
from typing import List

import torch
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import models
from ..db.session import get_db
from backend.ml.config import MAPPINGS_PATH, MODEL_PATH
from backend.ml.model import RecSysNN
from backend.ml.tasks import train_task
from backend.plugins.base import TrackOut
from backend.plugins.soundcloud import SoundCloudPlugin
from backend.routers.auth import get_current_user
from backend.soundcloud_auth import fetch_soundcloud_access_token

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


# ─── СХЕМЫ ──────────────────────────────────────────────────────────────────

class ReplaceTrackRequest(BaseModel):
    track_id: str
    current_queue: List[str]


# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ────────────────────────────────────────────────

def get_or_create_track(db: Session, source_id: str) -> models.Track:
    """
    Возвращает трек по source_id. Если трека нет — создаёт заглушку.
    flush() даёт нам track.id без закрытия транзакции.
    """
    track = db.query(models.Track).filter(
        models.Track.source_id == source_id
    ).first()

    if not track:
        source = "youtube" if len(source_id) == 11 else "soundcloud"
        track  = models.Track(
            source_id=source_id, source=source,
            title="Unknown", artist="Unknown",
        )
        db.add(track)
        db.flush()

    return track


def _soundcloud_fallback(query: str, blacklisted_ids: set, limit: int) -> List[TrackOut]:
    token = fetch_soundcloud_access_token()
    raw   = SoundCloudPlugin(access_token=token).search(query)
    return [t for t in raw if str(t.id) not in blacklisted_ids][:limit]


def generate_ml_recommendations(db: Session, user_id: int, limit: int = 10) -> List[TrackOut]:
    blacklisted_ids = {
        b.track_id for b in db.query(models.RecommendationBlacklist)
        .filter(models.RecommendationBlacklist.user_id == user_id).all()
    }

    pref = (
        db.query(models.UserPreference)
        .filter(models.UserPreference.user_id == user_id).first()
    )
    preferred_genres  = pref.preferred_genres  if (pref and pref.preferred_genres)  else {}
    preferred_artists = pref.preferred_artists if (pref and pref.preferred_artists) else {}

    def top_genre(default: str = "Top Hits") -> str:
        return max(preferred_genres, key=preferred_genres.get) if preferred_genres else default

    interactions = (
        db.query(models.UserInteraction)
        .filter(models.UserInteraction.user_id == user_id)
        .order_by(models.UserInteraction.engagement_score.desc()).all()
    )

    # Холодный старт
    if len(interactions) < 3:
        query = f"{top_genre()} mix"
        print(f"[Recs] Холодный старт для юзера {user_id}. Запрос: '{query}'")
        try:
            return _soundcloud_fallback(query, blacklisted_ids, limit)
        except Exception as e:
            print("[Recs] Ошибка холодного старта:", e)
            return []

    # Нейросеть + контентный бустинг
    try:
        if not os.path.exists(MAPPINGS_PATH):
            raise FileNotFoundError("mappings.pt не найден. Запустите /train-now.")

        mappings = torch.load(MAPPINGS_PATH, map_location="cpu")
        user2idx: dict = mappings["user2idx"]
        item2idx: dict = mappings["item2idx"]

        if user_id not in user2idx:
            raise KeyError(f"Пользователь {user_id} не в маппинге — нужно переобучить модель.")

        checkpoint = torch.load(MODEL_PATH, map_location="cpu")
        model = RecSysNN(n_users=checkpoint["n_users"], n_items=checkpoint["n_items"])
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()

        user_tensor = torch.tensor([user2idx[user_id]], dtype=torch.long)

        listened_bad_track_ids = {
            i.track_id for i in interactions if i.engagement_score < 0.3
        }

        scored_tracks = []
        with torch.no_grad():
            for track in db.query(models.Track).all():
                if track.source_id in blacklisted_ids:
                    continue

                item_idx_val = item2idx.get(track.id)
                nn_score = (
                    0.5 if item_idx_val is None
                    else model(user_tensor, torch.tensor([item_idx_val], dtype=torch.long)).item()
                )

                genre_bonus  = preferred_genres.get(track.genre,   0.0) * 0.2 if track.genre  else 0.0
                artist_bonus = preferred_artists.get(track.artist, 0.0) * 0.3 if track.artist else 0.0

                scored_tracks.append((track, nn_score + genre_bonus + artist_bonus))

        scored_tracks.sort(key=lambda x: x[1], reverse=True)

        final_list = []
        for track, _ in scored_tracks:
            if track.id in listened_bad_track_ids:
                continue
            final_list.append(TrackOut(
                id=track.source_id, source=track.source,
                title=track.title, artist=track.artist or "Выбор нейросети",
                duration=180, thumbnail_url=None,
            ))
            if len(final_list) >= limit:
                break

        return final_list

    except Exception as e:
        print(f"[Recs] Нейросеть недоступна ({e}), фолбек на SoundCloud")
        try:
            return _soundcloud_fallback(f"{top_genre('Chill')} mix", blacklisted_ids, limit)
        except Exception as e2:
            print("[Recs] Фолбек тоже упал:", e2)
            return []


# ─── ЭНДПОИНТЫ ──────────────────────────────────────────────────────────────

@router.get("")
def get_user_recommendations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
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
                "id": t.source_id, "title": t.title, "artist": t.artist, "source": t.source,
                "stream_url": f"/stream/{t.source_id}?source={t.source}&title={t.title}&artist={t.artist}",
            }
            for t in playlist.tracks
        ],
    }


@router.post("/replace")
def replace_track_in_queue(
    data: ReplaceTrackRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    skipped_track = get_or_create_track(db, data.track_id)

    db.add(models.UserInteraction(
        user_id=current_user.id, track_id=skipped_track.id,
        listen_duration=0, completion_rate=0.0,
        is_finished=False, is_looped=False,
        was_skipped=True, skip_position=0, skip_type="immediate", engagement_score=0.0,
    ))

    pref = db.query(models.UserPreference).filter(models.UserPreference.user_id == current_user.id).first()
    preferred_artists = [a for a, s in pref.preferred_artists.items() if s > 0] if pref else []
    preferred_genres  = [g for g, s in pref.preferred_genres.items()  if s > 0] if pref else []

    blacklist   = {b.track_id for b in db.query(models.RecommendationBlacklist).filter(models.RecommendationBlacklist.user_id == current_user.id).all()}
    exclude_ids = set(data.current_queue) | blacklist | {data.track_id}

    replacement = None

    if preferred_artists:
        replacement = db.query(models.Track).filter(models.Track.artist.in_(preferred_artists), ~models.Track.source_id.in_(exclude_ids)).order_by(func.random()).first()

    if not replacement and preferred_genres:
        replacement = db.query(models.Track).filter(models.Track.genre.in_(preferred_genres), ~models.Track.source_id.in_(exclude_ids)).order_by(func.random()).first()

    if not replacement:
        replacement = db.query(models.Track).filter(~models.Track.source_id.in_(exclude_ids)).order_by(func.random()).first()

    if not replacement:
        try:
            query = preferred_artists[0] if preferred_artists else (preferred_genres[0] if preferred_genres else "Chill mix")
            token = fetch_soundcloud_access_token()
            for t in SoundCloudPlugin(access_token=token).search(query):
                if str(t.id) not in exclude_ids:
                    replacement = models.Track(source_id=str(t.id), source=t.source, title=t.title, artist=t.artist)
                    db.add(replacement)
                    db.flush()
                    break
        except Exception as e:
            print("[Replace] Ошибка SoundCloud:", e)

    if not replacement:
        raise HTTPException(status_code=404, detail="Нет доступных треков для замены")

    db.commit()

    return {
        "id": replacement.source_id, "title": replacement.title,
        "artist": replacement.artist, "source": replacement.source,
        "stream_url": f"/stream/{replacement.source_id}?source={replacement.source}&title={replacement.title}&artist={replacement.artist}",
    }


@router.post("/hide/{track_id}")
def hide_track_from_recommendations(
    track_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user_id = current_user.id

    if not db.query(models.RecommendationBlacklist).filter(models.RecommendationBlacklist.user_id == user_id, models.RecommendationBlacklist.track_id == track_id).first():
        db.add(models.RecommendationBlacklist(user_id=user_id, track_id=track_id))

    track    = get_or_create_track(db, track_id)
    existing = db.query(models.UserInteraction).filter(models.UserInteraction.user_id == user_id, models.UserInteraction.track_id == track.id).first()

    if existing:
        existing.engagement_score = 0.0
    else:
        db.add(models.UserInteraction(
            user_id=user_id, track_id=track.id,
            listen_duration=0, completion_rate=0.0,
            is_finished=False, is_looped=False,
            was_skipped=True, skip_position=0, skip_type="immediate", engagement_score=0.0,
        ))

    playlist = db.query(models.Playlist).filter(models.Playlist.user_id == user_id, models.Playlist.type == "recommendations").first()
    if playlist and track in playlist.tracks:
        playlist.tracks.remove(track)

    db.commit()
    return {"status": "ok", "message": "Трек удалён из текущих и будущих рекомендаций"}


# ─── CELERY: ОБУЧЕНИЕ ────────────────────────────────────────────────────────

@router.post("/train-now")
def trigger_ml_training(
    current_user: models.User = Depends(get_current_user),
):
    """
    Ставит задачу обучения нейросети в очередь Celery.
    Возвращает task_id — по нему можно следить за прогрессом через /train-status.
    """
    task = train_task.delay(epochs=5, batch_size=16)

    return {
        "status":  "queued",
        "task_id": task.id,
        "message": "Обучение поставлено в очередь. Следите за прогрессом через /train-status/{task_id}",
    }


@router.get("/train-status/{task_id}")
def get_training_status(
    task_id: str,
    current_user: models.User = Depends(get_current_user),
):
    """
    Возвращает текущий статус и прогресс задачи обучения.

    Возможные значения status:
      PENDING  — задача в очереди, ещё не взята воркером
      STARTED  — воркер взял задачу
      PROGRESS — обучение идёт, в progress номер текущей эпохи
      SUCCESS  — готово, в result детали
      FAILURE  — ошибка, в error описание
    """
    result = train_task.AsyncResult(task_id)

    response = {"task_id": task_id, "status": result.state}

    if result.state == "PROGRESS":
        meta = result.info or {}
        response["step"]   = meta.get("step", "")
        response["epoch"]  = meta.get("epoch", 0)
        response["epochs"] = meta.get("epochs", 0)

    elif result.state == "SUCCESS":
        info = result.result or {}
        response["success"] = info.get("success")
        response["n_users"] = info.get("n_users")
        response["n_items"] = info.get("n_items")

    elif result.state == "FAILURE":
        response["error"] = str(result.info)

    return response