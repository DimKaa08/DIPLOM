# backend/routers/search.py
import re
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
import yt_dlp

from backend.db.session import get_db
from backend.db import models
from backend.routers.auth import get_current_user
from backend.plugins.soundcloud import SoundCloudPlugin
from backend.soundcloud_auth import fetch_soundcloud_access_token

router = APIRouter(prefix="/search", tags=["search"])

def clean_string(text: str) -> str:
    """Нормализация строк для дедупликации."""
    if not text:
        return ""
    return re.sub(r'[^a-z0-9а-яё]', '', text.lower())


def search_youtube(query: str, max_results: int = 5) -> list:
    """Ищет чистые студийные треки на YouTube, отфильтровывая шумные концертные записи."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True, 
    }
    try:
        fetch_limit = max_results * 3
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_result = ydl.extract_info(f"ytsearch{fetch_limit}:{query}", download=False)
            tracks = []
            
            YT_STOP_KEYWORDS = [
                "live", "concert", "концерт", "выступление", "fancam", "фанкам", 
                "tour", "audience", "crowd", "vlog", "реакция", "reaction", 
                "live performance", "shaky", "fest", "фестиваль"
            ]
            
            query_lower = query.lower()
            active_stop_keywords = [kw for kw in YT_STOP_KEYWORDS if kw not in query_lower]

            if 'entries' in search_result:
                for entry in search_result['entries']:
                    if not entry:
                        continue
                    
                    title = entry.get("title", "")
                    title_lower = title.lower()
                    
                    if any(kw in title_lower for kw in active_stop_keywords):
                        continue
                        
                    tracks.append({
                        "id": entry.get("id"),
                        "title": title,
                        "artist": entry.get("uploader") or "YouTube Creator",
                        "source": "youtube"
                    })
                    
                    if len(tracks) >= max_results:
                        break
                        
            return tracks
    except Exception as e:
        print(f"[YouTube Engine] Ошибка поиска '{query}': {e}")
        return []


def search_soundcloud(query: str) -> list:
    """Ищет полные треки в SoundCloud (без превью и коротких клипов)."""
    try:
        access_token = fetch_soundcloud_access_token()
        soundcloud_plugin = SoundCloudPlugin(access_token=access_token)
        
        results = soundcloud_plugin.search(query)
        tracks = []
        
        STOP_KEYWORDS = ["preview", "snippet", "teaser", "превью", "тизер", "short version", "clip"]

        for track in results:
            title_lower = track.title.lower()
            if any(kw in title_lower for kw in STOP_KEYWORDS):
                continue
                
            duration_ms = getattr(track, 'duration', 0)
            if duration_ms and duration_ms < 60000:  
                continue

            tracks.append({
                "id": str(track.id),
                "title": track.title,
                "artist": track.artist or "Unknown Artist",
                "source": "soundcloud"
            })
        return tracks
    except Exception as e:
        print(f"[SoundCloud Engine] Ошибка поиска '{query}': {e}")
        return []


@router.get("")
def global_search(
    q: str = Query(..., description="Поисковый запрос"),
    source: str = Query("auto", description="Источник: auto, soundcloud, youtube"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Достаем черный список пользователя для фильтрации контекстных рекомендаций
    blacklisted_ids = {
        b.track_id for b in db.query(models.RecommendationBlacklist)
        .filter(models.RecommendationBlacklist.user_id == current_user.id).all()
    }

    primary_results = []

    # Шаг 1: Получаем прямые результаты поиска
    if source in ["auto", "soundcloud"]:
        primary_results.extend(search_soundcloud(q))

    if source in ["auto", "youtube"]:
        primary_results.extend(search_youtube(q, max_results=5))

    extended_results = list(primary_results)

    # Шаг 2: Генерация контекстных рекомендаций (Похожие треки)
    if primary_results:
        reference_track = primary_results[0]
        ref_artist = reference_track["artist"]
        ref_title = reference_track["title"]

        is_valid_artist = ref_artist and ref_artist not in ["Unknown Artist", "YouTube Creator", "HYBE LABELS"]

        if is_valid_artist:
            extended_results.extend(search_youtube(f"{ref_artist} official audio", max_results=3))
            extended_results.extend(search_youtube(f"{ref_artist} {ref_title} studio audio", max_results=3))
        else:
            extended_results.extend(search_youtube(f"{q} mix official", max_results=4))

    # Шаг 3: Глубокая очистка данных, дедупликация + Фильтр черного списка
    final_results = []
    seen_tracks = set()

    for track in extended_results:
        # УМНЫЙ ФИЛЬТР: Проверяем, скрывал ли пользователь этот трек ранее
        if track["id"] in blacklisted_ids:
            print(f"[Search Blacklist] Трек {track['title']} ({track['id']}) вырезан из рекомендаций.")
            continue

        norm_title = clean_string(track["title"])
        norm_artist = clean_string(track["artist"])
        
        if not norm_title:
            continue
            
        track_key = (norm_artist, norm_title)

        if track_key not in seen_tracks:
            seen_tracks.add(track_key)
            final_results.append(track)

    print(f"[Search Engine] Итог выдачи с учетом блэклиста: {len(final_results)}")
    return final_results