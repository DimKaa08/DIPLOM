// frontend/src/api/search.js
import client from "./client";

export const searchTracks = async (query) => {
  const res = await client.get("/search", { params: { q: query } });
  return res.data;
};