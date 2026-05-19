// src/api/favorites.js
import axios from "axios";
const API = "http://localhost:8000";

export async function addFavorite(track_id, token) {
  const res = await axios.post(
    `${API}/favorites/add`,
    null,
    {
      params: { track_id },
      headers: { Authorization: `Bearer ${token}` }
    }
  );
  return res.data;
}

export async function removeFavorite(track_id, token) {
  const res = await axios.delete(
    `${API}/favorites/remove`,
    {
      params: { track_id },
      headers: { Authorization: `Bearer ${token}` }
    }
  );
  return res.data;
}

export async function listFavorites(token) {
  const res = await axios.get(`${API}/favorites/list`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data; // возвращает массив track_id
}
