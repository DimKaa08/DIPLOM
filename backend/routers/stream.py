from fastapi import APIRouter, HTTPException, Query
from backend.plugins.youtube import YouTubePlugin
from backend.plugins.soundcloud import SoundCloudPlugin
from backend.plugins.spotify import SpotifyPlugin

router = APIRouter()

youtube = YouTubePlugin()
soundcloud = SoundCloudPlugin(client_id="kx4fF4ceuBgYA1Rl7dy7LLubaoJXUpSN")
spotify = SpotifyPlugin(
    client_id="006a93ddd0e341a3bc7ca85df7db6131",
    client_secret="44646bae24834a7793963c9cdad3ffbc"
)

@router.get("/{track_id}")
def get_stream(track_id: str, source: str = Query(...)):
    if source == "youtube":
        url = youtube.get_stream_url(track_id)
    elif source == "soundcloud":
        url = soundcloud.get_stream_url(track_id)
    elif source == "spotify":
        url = spotify.get_stream_url(track_id)
    else:
        raise HTTPException(status_code=400, detail="Unknown source")

    if not url:
        raise HTTPException(status_code=404, detail="Stream not found")

    return {"url": url}
