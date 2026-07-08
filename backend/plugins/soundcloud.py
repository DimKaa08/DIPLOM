# backend/plugins/soundcloud.py
import re
import requests
from typing import List
from .base import BasePlugin, TrackOut

class SoundCloudPlugin(BasePlugin):
    source_name = "soundcloud"

    def __init__(self, access_token: str):
        self.access_token = access_token
        # Официальный API требует авторизацию через заголовок OAuth
        self.headers = {
            "Authorization": f"OAuth {self.access_token}",
            "Accept": "application/json; charset=utf-8"
        }

    def search(self, query: str) -> List[TrackOut]:
        if not self.access_token:
            print("[SoundCloud API] Поиск невозможен: отсутствует access_token")
            return []

        # Официальный эндпоинт поиска треков
        url = "https://api.soundcloud.com/tracks"
        
        sanitized_query = re.sub(r'[!?.,\(\)\[\]"\'\-]', ' ', query)
        sanitized_query = " ".join(sanitized_query.split())
        
        params = {
            "q": sanitized_query,
            "limit": 15,
            "linked_partitioning": "true"  # Для получения структурированной коллекции коллекций
        }

        try:
            print(f"[SoundCloud API] Поиск трека: '{sanitized_query}'")
            r = requests.get(url, params=params, headers=self.headers, timeout=5)
            
            if r.status_code != 200:
                print(f"[SoundCloud API] Ошибка поиска. Статус: {r.status_code}")
                return []

            data = r.json()
            results = []
            
            # Официальный API при linked_partitioning возвращает данные в ключе "collection"
            tracks_list = data.get("collection", []) if isinstance(data, dict) else data

            for t in tracks_list:
                # Фильтруем коммерческие превью-заглушки (30 секунд)
                if t.get("policy") == "SNIPPET" or t.get("duration", 0) <= 30000:
                    continue

                results.append(
                    TrackOut(
                        id=str(t["id"]),
                        source=self.source_name,
                        title=t.get("title"),
                        artist=t.get("user", {}).get("username", "Unknown Artist"),
                        duration=int(t.get("duration", 0) / 1000),
                        thumbnail_url=t.get("artwork_url"),
                    )
                )
            return results

        except Exception as e:
            print("[SoundCloud API] Исключение при поиске:", e)
            return []

    def get_stream_url(self, track_id: str) -> str:
        if not self.access_token:
            return None

        # Официальный эндпоинт стриминга возвращает 302 редирект на защищенный MP3/AAC файл в CDN
        url = f"https://api.soundcloud.com/tracks/{track_id}/stream"
        
        try:
            print(f"[SoundCloud API Stream] Запрос локации аудиопотока для ID={track_id}")
            # Запрещаем редирект (allow_redirects=False), чтобы перехватить конечную CDN-ссылку
            r = requests.get(url, headers=self.headers, allow_redirects=False, timeout=5)
            
            if r.status_code in [302, 307]:
                return r.headers.get("Location")
            elif r.status_code == 200:
                return r.json().get("url")
                
            print(f"[SoundCloud API Stream] Не удалось получить поток. Статус: {r.status_code}")
        except Exception as e:
            print("[SoundCloud API Stream] Ошибка стрима:", e)
            
        return None