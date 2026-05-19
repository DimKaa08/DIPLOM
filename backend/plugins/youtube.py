from typing import List
from .base import BasePlugin, TrackOut

# сюда потом добавишь yt-dlp или YouTube Data API
class YouTubePlugin(BasePlugin):
    source_name = "youtube"

    def search(self, query: str) -> List[TrackOut]:
        # TODO: реальная интеграция
        # пока — заглушка
        return [
            TrackOut(
                id="dummy_youtube_id",
                source=self.source_name,
                title=f"Result for {query}",
                artist="Unknown",
                duration=180,
                thumbnail_url=None,
            )
        ]

    def get_stream_url(self, track_id: str) -> str:
        # TODO: реальная ссылка через yt-dlp
        return f"https://youtube.com/watch?v={track_id}"
