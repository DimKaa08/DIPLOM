from typing import List
from .base import BasePlugin, TrackOut
import requests


class SoundCloudPlugin(BasePlugin):
    source_name = "soundcloud"

    def __init__(self, client_id: str):
        self.client_id = client_id

    # -----------------------------
    # 🔍 Поиск треков
    # -----------------------------
    def search(self, query: str) -> List[TrackOut]:
        url = "https://api-v2.soundcloud.com/search/tracks"
        params = {
            "q": query,
            "client_id": self.client_id,
            "limit": 10
        }

        try:
            r = requests.get(url, params=params)
            data = r.json()

            results = []
            for t in data.get("collection", []):
                results.append(
                    TrackOut(
                        id=str(t["id"]),
                        source=self.source_name,
                        title=t.get("title"),
                        artist=t.get("user", {}).get("username", "Unknown"),
                        duration=int(t.get("duration", 0) / 1000),
                        thumbnail_url=t.get("artwork_url"),
                    )
                )
            return results

        except Exception as e:
            print("SoundCloud search error:", e)
            return []

    # -----------------------------
    # 🎧 Получение stream URL
    # -----------------------------
    def get_stream_url(self, track_id: str) -> str:
        resolve_url = f"https://api.soundcloud.com/tracks/{track_id}/stream"
        params = {"client_id": self.client_id}

        try:
            r = requests.get(resolve_url, params=params, allow_redirects=False)
            return r.headers.get("Location")  # прямой mp3 URL
        except Exception as e:
            print("SoundCloud stream error:", e)
            return None
