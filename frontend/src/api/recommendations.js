// frontend/src/api/recommendations.js
import client from "./client";

export async function getRecommendations() {
  const res = await client.get("/recommendations");
  return res.data;
}

export async function replaceTrackInQueue(trackId, currentQueue) {
  const res = await client.post("/recommendations/replace", {
    track_id:      String(trackId),
    current_queue: currentQueue.map(String),
  });
  return res.data;
}

export async function hideTrackFromRecommendations(trackId) {
  const res = await client.post(`/recommendations/hide/${trackId}`, {});
  return res.data;
}

export async function getTrainingStatus(taskId) {
  const res = await client.get(`/recommendations/train-status/${taskId}`);
  return res.data;
}

export async function triggerTraining() {
  const res = await client.post("/recommendations/train-now");
  return res.data;
}

export default {
  getRecommendations,
  replaceTrackInQueue,
  hideTrackFromRecommendations,
  getTrainingStatus,
  triggerTraining,
};