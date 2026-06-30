import axios from "axios";

const API = "http://localhost:8000";

export const addFavorite = async (track, token) => {
  // Формируем чистый payload, соответствующий ожиданиям FastAPI
  const payload = {
    track_id: String(track.id),
    title: track.title || "Unknown Title",
    artist: track.artist || "Unknown Artist",
    source: track.source || "soundcloud"
  };

  const response = await axios.post("http://localhost:8000/favorites/add", payload, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json"
    }
  });
  return response.data;
};

export async function removeFavorite(trackId, token) {
  // Проверьте метод вашего бэкенда (DELETE или POST)
  const res = await axios.delete(`${API}/favorites/remove/${trackId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
}

export async function getFavorites(token) {
  const res = await axios.get(`${API}/favorites`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
}

export const listFavorites = async (token) => {
  const response = await fetch("http://localhost:8000/favorites", {
    headers: { Authorization: `Bearer ${token}` }
  });
  return response.json(); // должен возвращать массив ID или объектов
};

export default { addFavorite, removeFavorite, getFavorites };