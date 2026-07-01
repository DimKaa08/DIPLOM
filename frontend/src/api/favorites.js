// frontend/src/api/favorites.js
import client from "./client";

export const addFavorite = async (track) => {
  const res = await client.post("/favorites/add", {
    track_id: String(track.id),
    title:    track.title  || "Unknown Title",
    artist:   track.artist || "Unknown Artist",
    source:   track.source || "soundcloud",
  });
  return res.data;
};

export const removeFavorite = async (trackId) => {
  const res = await client.delete(`/favorites/remove/${encodeURIComponent(trackId)}`);
  return res.data;
};

export const getFavorites = async () => {
  const res = await client.get("/favorites");
  return res.data;
};

export default { addFavorite, removeFavorite, getFavorites };