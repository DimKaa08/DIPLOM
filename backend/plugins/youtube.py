from typing import List, Optional
from .base import BasePlugin, TrackOut
import yt_dlp


class YouTubePlugin(BasePlugin):
    source_name = "youtube"

    # -----------------------------
    # 🔧 Общие настройки yt-dlp
    # -----------------------------
    def _opts(self):
        return {
            "quiet": True,
            "skip_download": True,

            # Ключевой момент: используем android-клиент
            "extractor_args": {
                "youtube": {
                    "player_client": ["android"],
                    "player_skip": ["web"],
                }
            }
        }

    # -----------------------------
    # 🔍 Поиск
    # -----------------------------
    def search(self, query: str) -> List[TrackOut]:
        opts = self._opts()
        opts["default_search"] = "ytsearch10"

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(query, download=False)

            entries = info.get("entries") or [info]

            results = []
            for v in entries:
                if not v:
                    continue

                results.append(
                    TrackOut(
                        id=v.get("id"),
                        source=self.source_name,
                        title=v.get("title") or "Unknown title",
                        artist=v.get("uploader") or v.get("channel") or "Unknown",
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
    def get_stream_url(self, track_id: str) -> Optional[str]:
        opts = self._opts()
        opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"

        url = f"https://www.youtube.com/watch?v={track_id}"

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            # 1) yt-dlp иногда сразу даёт прямой URL
            if info.get("url"):
                return info["url"]

            # 2) иначе ищем аудио формат вручную
            for f in info.get("formats", []):
                if f.get("acodec") != "none" and f.get("url"):
                    return f["url"]

            return None

        except Exception as e:
            print("YouTube stream error:", e)
            return None
