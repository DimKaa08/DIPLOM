import axios from "axios";

const API = "http://localhost:8000";

export async function getPlaylists(token) {
  const res = await axios.get(`${API}/playlist/list`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
}

export async function getPlaylistTracks(id, token) {
  const res = await axios.get(`${API}/playlist/${id}/tracks`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
}

export const removeTrackFromPlaylist = async (playlistId, trackId, token) => {
  const response = await axios.delete(`http://localhost:8000/playlist/${playlistId}/remove_track`, {
    headers: { 
      Authorization: `Bearer ${token}`
    },
    // Передаем как Query-параметр (?track_id=...)
    params: {
      track_id: String(trackId) // Превращаем ID в строку, как требует бэкенд!
    }
  });
  return response.data;
};

export default {
  getPlaylists,
  getPlaylistTracks,
  removeTrackFromPlaylist
};