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

export async function getRecommendations(user_id, token) {
  const res = await axios.get(`${API}/recommendations/user/${user_id}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
}
