import axios from "axios";

const API = "http://localhost:8000";

// основной метод поиска
export async function searchTracks(query, source = "youtube") {
  const res = await axios.get(`${API}/search`, {
    params: { q: query, source }
  });
  return res.data;
}

// default‑экспорт, чтобы App.jsx мог делать import searchApi from ...
export default {
  searchTracks
};

