import axios from "axios";

const API = "http://localhost:8000";

export async function getRecommendations(token) {
  const res = await axios.get(`${API}/recommendations`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
}

export async function replaceTrackInQueue(trackId, currentQueue, token) {
  const res = await axios.post(`${API}/recommendations/replace`, {
    track_id: String(trackId),
    current_queue: currentQueue.map(String)
  }, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
}

// Новая функция для полного удаления трека из рекомендаций навсегда
export async function hideTrackFromRecommendations(trackId, token) {
  // Отправляем пустой объект {} в качестве body, так как ID передается в URL параметре
  const res = await axios.post(`${API}/recommendations/hide/${trackId}`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return res.data;
}

export default { getRecommendations, replaceTrackInQueue, hideTrackFromRecommendations };