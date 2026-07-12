# backend/routers/recommendations.py
import os
import random
import yt_dlp
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
from backend.services.cache import get_cached_recs, set_cached_recs, invalidate_recs

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class ReplaceTrackRequest(BaseModel):
    track_id: str
    current_queue: List[str]


# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ─────────────────────────────────────────────────

def get_or_create_track(db: Session, source_id: str) -> models.Track:
    track = db.query(models.Track).filter(models.Track.source_id == source_id).first()
    if not track:
        source = "youtube" if len(source_id) == 11 else "soundcloud"
        track  = models.Track(source_id=source_id, source=source, title="Unknown", artist="Unknown")
        db.add(track)
        db.flush()
    return track


def _has_valid_mappings() -> bool:
    if not os.path.exists(MAPPINGS_PATH):
        return False
    try:
        m = torch.load(MAPPINGS_PATH, map_location="cpu")
        return "user2idx" in m and "item2idx" in m
    except Exception:
        return False


def _soundcloud_fallback(query: str, blacklisted_ids: set, limit: int) -> List[TrackOut]:
    token = fetch_soundcloud_access_token()
    raw   = SoundCloudPlugin(access_token=token).search(query)
    return [t for t in raw if str(t.id) not in blacklisted_ids][:limit]


def _discover_new_tracks(db, preferred_artists, preferred_genres, limit=10, cookie_path=None):
    """Ищет новые треки по вкусам пользователя. Использует cookies если загружены."""
    known_ids = {t.source_id for t in db.query(models.Track.source_id).all()}
    top_artists = [a for a, _ in sorted(preferred_artists.items(), key=lambda x: x[1], reverse=True)[:3]]
    top_genres  = [g for g, _ in sorted(preferred_genres.items(),  key=lambda x: x[1], reverse=True)[:2]]

    queries = []
    for artist in top_artists:
        queries.append(f"{artist} official audio")
    for genre in top_genres:
        queries.append(f"best {genre} music 2024")
    if not queries:
        queries = ["popular music 2024"]

    ydl_opts = {
        "quiet": True, "no_warnings": True, "extract_flat": True,
        "extractor_args": {"youtube": {"player_client": ["ios"]}},
    }
    if cookie_path and os.path.exists(cookie_path):
        ydl_opts["cookies"] = cookie_path

    discovered: List[TrackOut] = []
    random.shuffle(queries)

    for query in queries[:4]:
        if len(discovered) >= limit:
            break
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                res = ydl.extract_info(f"ytsearch8:{query}", download=False)
                if not (res and "entries" in res):
                    continue
                for entry in res["entries"]:
                    vid_id = entry.get("id")
                    if not vid_id or vid_id in known_ids:
                        continue
                    title = entry.get("title", "")
                    if any(x in title.lower() for x in ["official mv", "official m/v"]):
                        continue
                    discovered.append(TrackOut(
                        id=vid_id, source="youtube",
                        title=title or "Unknown",
                        artist=entry.get("uploader") or entry.get("channel") or "Unknown",
                        duration=int(entry.get("duration") or 180),
                        thumbnail_url=entry.get("thumbnail"),
                    ))
                    known_ids.add(vid_id)
                    if len(discovered) >= limit:
                        break
        except Exception as e:
            print(f"[Discover] Ошибка '{query}': {e}")

    return discovered


def _db_personalized_fallback(db, user_id, limit, blacklisted_ids, preferred_artists, preferred_genres):
    """
    Рекомендации из БД на основе ТОЛЬКО истории текущего пользователя.
    ИСПРАВЛЕНО: раньше использовались avg_scores от ВСЕХ пользователей,
    из-за чего новый пользователь получал треки, которые лайкал предыдущий.
    Теперь скоринг основан только на взаимодействиях текущего user_id.
    """
    # Треки которые текущий пользователь скипнул
    skipped_ids = {i.track_id for i in db.query(models.UserInteraction)
        .filter(models.UserInteraction.user_id == user_id,
                models.UserInteraction.engagement_score <= 0.0).all()}

    # Треки с позитивным откликом от ТЕКУЩЕГО пользователя
    user_scores = {i.track_id: float(i.engagement_score) for i in
        db.query(models.UserInteraction)
        .filter(models.UserInteraction.user_id == user_id).all()}

    all_tracks = db.query(models.Track).filter(
        models.Track.source_id.isnot(None),
        ~models.Track.source_id.in_(blacklisted_ids),
        ~models.Track.id.in_(skipped_ids),
    ).all()

    if not all_tracks:
        return []

    scored = []
    for track in all_tracks:
        # Базовый скор — только из истории ЭТОГО пользователя (не других)
        base  = user_scores.get(track.id, 0.0)
        score = base
        if track.artist in preferred_artists:  score += preferred_artists[track.artist] * 0.3
        if track.genre  in preferred_genres:   score += preferred_genres[track.genre]   * 0.2
        scored.append((track, score))

    # Шаффл среди треков с одинаковым скором (разнообразие)
    random.shuffle(scored)
    scored.sort(key=lambda x: x[1], reverse=True)
    return [
        TrackOut(id=t.source_id, source=t.source or "youtube",
                 title=t.title or "Unknown", artist=t.artist or "Рекомендация",
                 duration=180, thumbnail_url=None)
        for t, _ in scored[:limit] if t.source_id
    ]


def generate_ml_recommendations(db: Session, user_id: int, limit: int = 15) -> List[TrackOut]:
    """
    Гибридная система с Redis-кешем.

    Порядок:
    1. Проверяем Redis-кеш (TTL 5 мин). Если свежие данные — возвращаем.
    2. Генерируем заново: нейросеть → SoundCloud → DB-фолбек.
    3. Сохраняем результат в кеш.
    """
    # ── УРОВЕНЬ 0: КЕSH ───────────────────────────────────────────────────────
    cached = get_cached_recs(user_id)
    if cached:
        print(f"[Recs] ✓ Кеш для юзера {user_id} ({len(cached)} треков)")
        return [TrackOut(**t) for t in cached]

    print(f"[Recs] Кеш пуст, генерируем рекомендации для юзера {user_id}...")

    blacklisted_ids = {b.track_id for b in db.query(models.RecommendationBlacklist)
        .filter(models.RecommendationBlacklist.user_id == user_id).all()}

    pref              = db.query(models.UserPreference).filter(models.UserPreference.user_id == user_id).first()
    preferred_genres  = pref.preferred_genres  if (pref and pref.preferred_genres)  else {}
    preferred_artists = pref.preferred_artists if (pref and pref.preferred_artists) else {}

    # Cookies пользователя (если загружены) для поиска новых треков
    from backend.routers.onboarding import get_user_cookie_path
    cookie_path = get_user_cookie_path(user_id)

    def top_genre(default="Top Hits"):
        return max(preferred_genres, key=preferred_genres.get) if preferred_genres else default

    interactions = (db.query(models.UserInteraction)
        .filter(models.UserInteraction.user_id == user_id)
        .order_by(models.UserInteraction.engagement_score.desc()).all())

    print(f"[Recs] Юзер {user_id}: {len(interactions)} взаимодействий")

    # Автозапуск обучения
    if len(interactions) >= 10 and not _has_valid_mappings():
        try:
            train_task.delay(epochs=5, batch_size=16)
            print("[Recs] Автозапуск обучения...")
        except Exception:
            pass

    result = []

    # ── УРОВЕНЬ 1: НЕЙРОСЕТЬ ──────────────────────────────────────────────────
    if len(interactions) >= 3 and _has_valid_mappings():
        try:
            db_tracks  = _neural_recommendations(db, user_id, limit // 2, blacklisted_ids,
                                                  preferred_genres, preferred_artists, interactions)
            new_tracks = _discover_new_tracks(db, preferred_artists, preferred_genres,
                                               limit - len(db_tracks), cookie_path)
            result = db_tracks + new_tracks
            if result:
                print(f"[Recs] ✓ Нейросеть: {len(db_tracks)} БД + {len(new_tracks)} новых")
        except Exception as e:
            print(f"[Recs] Нейросеть: {e}")

    # ── УРОВЕНЬ 1б: ВКУСОВОЙ ПОИСК (если нейросеть не готова) ───────────────
    if not result and (preferred_artists or preferred_genres):
        new_tracks = _discover_new_tracks(db, preferred_artists, preferred_genres,
                                           limit // 2, cookie_path)
        db_tracks  = _db_personalized_fallback(db, user_id, limit - len(new_tracks),
                                                blacklisted_ids, preferred_artists, preferred_genres)
        result = db_tracks + new_tracks
        if result:
            print(f"[Recs] ✓ Вкусовой поиск: {len(db_tracks)} БД + {len(new_tracks)} новых")

    # ── УРОВЕНЬ 2: SOUNDCLOUD ─────────────────────────────────────────────────
    if not result:
        try:
            result = _soundcloud_fallback(f"{top_genre('Chill')} mix", blacklisted_ids, limit)
            if result:
                print(f"[Recs] ✓ SoundCloud: {len(result)} треков")
        except Exception as e:
            print(f"[Recs] SoundCloud: {e}")

    # ── УРОВЕНЬ 3: DB FALLBACK ────────────────────────────────────────────────
    if not result:
        result = _db_personalized_fallback(db, user_id, limit, blacklisted_ids,
                                            preferred_artists, preferred_genres)
        print(f"[Recs] DB fallback: {len(result)} треков")

    # ── КЕШИРУЕМ РЕЗУЛЬТАТ ────────────────────────────────────────────────────
    if result:
        set_cached_recs(user_id, [t.dict() for t in result])

    return result


def _neural_recommendations(db, user_id, limit, blacklisted_ids,
                              preferred_genres, preferred_artists, interactions):
    mappings = torch.load(MAPPINGS_PATH, map_location="cpu")
    user2idx = mappings["user2idx"]
    item2idx = mappings["item2idx"]

    if user_id not in user2idx:
        raise KeyError(f"Пользователь {user_id} не в маппинге")

    checkpoint = torch.load(MODEL_PATH, map_location="cpu")
    model      = RecSysNN(n_users=checkpoint["n_users"], n_items=checkpoint["n_items"])
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    user_tensor      = torch.tensor([user2idx[user_id]], dtype=torch.long)
    listened_bad_ids = {i.track_id for i in interactions if i.engagement_score < 0.3}
    scored_tracks    = []

    with torch.no_grad():
        for track in db.query(models.Track).all():
            if track.source_id in blacklisted_ids:
                continue
            item_idx_val = item2idx.get(track.id)
            nn_score = (0.5 if item_idx_val is None
                        else model(user_tensor, torch.tensor([item_idx_val], dtype=torch.long)).item())
            genre_bonus  = preferred_genres.get(track.genre,   0.0) * 0.2 if track.genre  else 0.0
            artist_bonus = preferred_artists.get(track.artist, 0.0) * 0.3 if track.artist else 0.0
            scored_tracks.append((track, nn_score + genre_bonus + artist_bonus))

    scored_tracks.sort(key=lambda x: x[1], reverse=True)
    result = []
    for track, _ in scored_tracks:
        if track.id in listened_bad_ids:
            continue
        result.append(TrackOut(id=track.source_id, source=track.source,
                                title=track.title, artist=track.artist or "Выбор нейросети 🧠",
                                duration=180, thumbnail_url=None))
        if len(result) >= limit:
            break
    return result


# ─── ЭНДПОИНТЫ ───────────────────────────────────────────────────────────────

@router.get("")
def get_user_recommendations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user_id  = current_user.id
    playlist = (db.query(models.Playlist)
        .filter(models.Playlist.user_id == user_id, models.Playlist.type == "recommendations").first())
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
            db_track = models.Track(source_id=track.id, source=track.source,
                                     title=track.title, artist=track.artist)
            db.add(db_track)
            db.flush()
        playlist.tracks.append(db_track)

    db.commit()
    db.refresh(playlist)

    return {
        "playlist_id": playlist.id,
        "tracks": [
            {"id": t.source_id, "title": t.title, "artist": t.artist, "source": t.source,
             "thumbnail_url": t.thumbnail_url,
             "stream_url": f"/stream/{t.source_id}?source={t.source}&title={t.title}&artist={t.artist}"}
            for t in playlist.tracks
        ],
    }


@router.post("/dislike/{track_id}")
def dislike_track(
    track_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user_id = current_user.id
    track   = get_or_create_track(db, track_id)

    existing = (db.query(models.UserInteraction)
        .filter(models.UserInteraction.user_id == user_id,
                models.UserInteraction.track_id == track.id).first())
    if existing:
        existing.engagement_score = -1.0
        existing.was_skipped      = True
        existing.skip_type        = "immediate"
    else:
        db.add(models.UserInteraction(
            user_id=user_id, track_id=track.id, listen_duration=0,
            completion_rate=0.0, is_finished=False, is_looped=False,
            was_skipped=True, skip_position=0, skip_type="immediate", engagement_score=-1.0,
        ))

    pref = (db.query(models.UserPreference)
        .filter(models.UserPreference.user_id == user_id).first())
    if pref and track.artist and track.artist != "Unknown":
        artists = dict(pref.preferred_artists or {})
        artists[track.artist] = round(max(artists.get(track.artist, 0.0) - 1.0, -3.0), 2)
        pref.preferred_artists = artists

    db.commit()
    invalidate_recs(user_id)   # ← инвалидируем кеш после дизлайка
    return {"status": "ok", "message": "Нейросеть учтёт, кеш обновлён"}


@router.post("/replace")
def replace_track_in_queue(
    data: ReplaceTrackRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    skipped = get_or_create_track(db, data.track_id)
    db.add(models.UserInteraction(
        user_id=current_user.id, track_id=skipped.id, listen_duration=0,
        completion_rate=0.0, is_finished=False, is_looped=False,
        was_skipped=True, skip_position=0, skip_type="immediate", engagement_score=0.0,
    ))

    pref = (db.query(models.UserPreference)
        .filter(models.UserPreference.user_id == current_user.id).first())
    preferred_artists = [a for a, s in pref.preferred_artists.items() if s > 0] if pref else []
    preferred_genres  = [g for g, s in pref.preferred_genres.items()  if s > 0] if pref else []
    blacklist   = {b.track_id for b in db.query(models.RecommendationBlacklist)
        .filter(models.RecommendationBlacklist.user_id == current_user.id).all()}
    exclude_ids = set(data.current_queue) | blacklist | {data.track_id}

    replacement = None
    if preferred_artists:
        replacement = (db.query(models.Track)
            .filter(models.Track.artist.in_(preferred_artists), ~models.Track.source_id.in_(exclude_ids))
            .order_by(func.random()).first())
    if not replacement and preferred_genres:
        replacement = (db.query(models.Track)
            .filter(models.Track.genre.in_(preferred_genres), ~models.Track.source_id.in_(exclude_ids))
            .order_by(func.random()).first())
    if not replacement:
        replacement = (db.query(models.Track)
            .filter(~models.Track.source_id.in_(exclude_ids)).order_by(func.random()).first())

    if not replacement:
        raise HTTPException(status_code=404, detail="Нет доступных треков")

    db.commit()
    return {
        "id": replacement.source_id, "title": replacement.title,
        "artist": replacement.artist, "source": replacement.source,
        "stream_url": f"/stream/{replacement.source_id}?source={replacement.source}&title={replacement.title}&artist={replacement.artist}",
    }


@router.post("/hide/{track_id}")
def hide_track(
    track_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user_id = current_user.id
    if not (db.query(models.RecommendationBlacklist)
            .filter(models.RecommendationBlacklist.user_id == user_id,
                    models.RecommendationBlacklist.track_id == track_id).first()):
        db.add(models.RecommendationBlacklist(user_id=user_id, track_id=track_id))
    track    = get_or_create_track(db, track_id)
    existing = (db.query(models.UserInteraction)
        .filter(models.UserInteraction.user_id == user_id,
                models.UserInteraction.track_id == track.id).first())
    if existing:
        existing.engagement_score = 0.0
    else:
        db.add(models.UserInteraction(
            user_id=user_id, track_id=track.id, listen_duration=0, completion_rate=0.0,
            is_finished=False, is_looped=False, was_skipped=True,
            skip_position=0, skip_type="immediate", engagement_score=0.0,
        ))
    playlist = (db.query(models.Playlist)
        .filter(models.Playlist.user_id == user_id, models.Playlist.type == "recommendations").first())
    if playlist and track in playlist.tracks:
        playlist.tracks.remove(track)
    db.commit()
    invalidate_recs(user_id)
    return {"status": "ok"}


@router.post("/train-now")
def trigger_training(current_user: models.User = Depends(get_current_user)):
    task = train_task.delay(epochs=5, batch_size=16)
    return {"status": "queued", "task_id": task.id}


@router.get("/train-status/{task_id}")
def training_status(task_id: str, current_user: models.User = Depends(get_current_user)):
    result   = train_task.AsyncResult(task_id)
    response = {"task_id": task_id, "status": result.state}
    if result.state == "PROGRESS":
        meta = result.info or {}
        response.update({"step": meta.get("step"), "epoch": meta.get("epoch"), "epochs": meta.get("epochs")})
    elif result.state == "SUCCESS":
        response.update(result.result or {})
    elif result.state == "FAILURE":
        response["error"] = str(result.info)
    return response