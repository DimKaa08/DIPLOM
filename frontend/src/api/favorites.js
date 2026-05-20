import axios from "axios";
const API = "http://localhost:8000";

// добавить в избранное
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

// удалить из избранного
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

// получить список избранных
export async function listFavorites(token) {
  const res = await axios.get(`${API}/favorites/list`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
}

// корректный default‑экспорт
export default {
  addFavorite,
  removeFavorite,
  listFavorites
};
