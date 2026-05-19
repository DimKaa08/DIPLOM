import axios from "axios";

const API = "http://localhost:8000";

export async function searchTracks(query, source = "youtube") {
  const res = await axios.get(`${API}/search`, {
    params: { q: query, source }
  });
  return res.data;
}
