from fastapi import APIRouter, Depends, Query
from typing import List

from backend.plugins.youtube import YouTubePlugin
from backend.plugins.soundcloud import SoundCloudPlugin
from backend.plugins.spotify import SpotifyPlugin
from backend.plugins.base import TrackOut

router = APIRouter()

# временно просто один плагин
youtube_plugin = YouTubePlugin()
soundcloud_plugin = SoundCloudPlugin(client_id="kx4fF4ceuBgYA1Rl7dy7LLubaoJXUpSN")
spotify_plugin = SpotifyPlugin(client_id="006a93ddd0e341a3bc7ca85df7db6131", client_secret="44646bae24834a7793963c9cdad3ffbc")

@router.get("/", response_model=List[TrackOut])
def search_tracks(
    q: str = Query(..., description="Поисковый запрос"),
    source: str = Query("youtube", description="Источник: youtube/soundcloud/spotify"),
):
    if source == "youtube":
        return youtube_plugin.search(q)
    elif source == "soundcloud":
        return soundcloud_plugin.search(q)
    elif source == "spotify":
        return spotify_plugin.search(q)
    else:
        return []
