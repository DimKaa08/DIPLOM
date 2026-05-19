from fastapi import APIRouter, Depends, Query
from typing import List

from plugins.youtube import YouTubePlugin
# from plugins.soundcloud import SoundCloudPlugin
# from plugins.spotify import SpotifyPlugin
from plugins.base import TrackOut

router = APIRouter()

# временно просто один плагин
youtube_plugin = YouTubePlugin()


@router.get("/", response_model=List[TrackOut])
def search_tracks(
    q: str = Query(..., description="Поисковый запрос"),
    source: str = Query("youtube", description="Источник: youtube/soundcloud/spotify"),
):
    if source == "youtube":
        return youtube_plugin.search(q)
    # elif source == "soundcloud":
    #     return soundcloud_plugin.search(q)
    # elif source == "spotify":
    #     return spotify_plugin.search(q)
    else:
        return []
