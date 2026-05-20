import axios from "axios";

const API = "http://localhost:8000";

// получить список плейлистов пользователя
export async function getPlaylists(token) {
  const res = await axios.get(`${API}/playlists/list`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
}

// получить треки конкретного плейлиста
export async function getPlaylistTracks(id, token) {
  const res = await axios.get(`${API}/playlists/${id}/tracks`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
}

// удалить трек из плейлиста
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

// корректный default‑экспорт
export default {
  getPlaylists,
  getPlaylistTracks,
  removeTrackFromPlaylist
};
