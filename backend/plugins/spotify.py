from typing import List
from .base import BasePlugin, TrackOut
import requests
import base64
import time


class SpotifyPlugin(BasePlugin):
    source_name = "spotify"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expires = 0

    # -----------------------------
    # 🔐 Получение access_token
    # -----------------------------
    def _get_token(self):
        if time.time() < self.token_expires:
            return self.token

        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

        r = requests.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {auth}"},
            data={"grant_type": "client_credentials"},
        )

        data = r.json()
        self.token = data["access_token"]
        self.token_expires = time.time() + data["expires_in"] - 30
        return self.token

    # -----------------------------
    # 🔍 Поиск треков
    # -----------------------------
    def search(self, query: str) -> List[TrackOut]:
        token = self._get_token()

        r = requests.get(
            "https://api.spotify.com/v1/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": query, "type": "track", "limit": 10},
        )

        data = r.json()
        items = data.get("tracks", {}).get("items", [])

        results = []
        for t in items:
            results.append(
                TrackOut(
                    id=t["id"],
                    source=self.source_name,
                    title=t["name"],
                    artist=t["artists"][0]["name"],
                    duration=int(t["duration_ms"] / 1000),
                    thumbnail_url=t["album"]["images"][0]["url"] if t["album"]["images"] else None,
                )
            )

        return results

    # -----------------------------
    # 🎧 Spotify НЕ даёт stream URL
    # -----------------------------
    def get_stream_url(self, track_id: str) -> str:
        return None  # стримим через YouTube/SoundCloud
