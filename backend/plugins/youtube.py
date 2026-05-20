from typing import List
from .base import BasePlugin, TrackOut
import yt_dlp


class YouTubePlugin(BasePlugin):
    source_name = "youtube"

    # -----------------------------
    # 🔍 Реальный поиск YouTube
    # -----------------------------
    def search(self, query: str) -> List[TrackOut]:
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "default_search": "ytsearch10",

            # отключаем JS‑solver (иначе YouTube ломает всё)
            "extractor_args": {
                "youtube": {
                    "player_client": ["web"],
                    "js": ["no"],
                    "n_token": ["no-deno"]
                }
            }
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)

            entries = info.get("entries", [])
            results = []

            for v in entries:
                results.append(
                    TrackOut(
                        id=v.get("id"),
                        source=self.source_name,
                        title=v.get("title"),
                        artist=v.get("uploader") or "Unknown",
                        duration=v.get("duration") or 0,
                        thumbnail_url=v.get("thumbnail"),
                    )
                )

            return results

        except Exception as e:
            print("YouTube search error:", e)
            return []


    # -----------------------------
    # 🎧 Получение stream URL
    # -----------------------------
    def get_stream_url(self, track_id: str) -> str:
        """
        Возвращает прямой аудио‑URL для проигрывания.
        """
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "format": "bestaudio/best",

            # отключаем JS‑solver
            "extractor_args": {
                "youtube": {
                    "player_client": ["web"],
                    "js": ["no"],
                    "n_token": ["no-deno"]
                }
            }
        }

        url = f"https://www.youtube.com/watch?v={track_id}"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            # yt-dlp всегда возвращает прямой URL в info["url"]
            return info.get("url")

        except Exception as e:
            print("YouTube stream error:", e)
            return None
