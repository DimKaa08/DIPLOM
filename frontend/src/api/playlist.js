import axios from "axios";

const API = "http://localhost:8000";

export async function getPlaylists(token) {
  const res = await axios.get(`${API}/playlists/list`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
}

export async function getPlaylistTracks(id, token) {
  const res = await axios.get(`${API}/playlists/${id}/tracks`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
}

export async function removeTrackFromPlaylist(playlistId, trackId, token) {
  const res = await axios.delete(
    `${API}/playlists/${playlistId}/remove_track`,
    {
      params: { track_id: trackId },
      headers: { Authorization: `Bearer ${token}` }
    }
  );
  return res.data;
}
