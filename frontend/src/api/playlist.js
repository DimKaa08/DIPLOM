// frontend/src/api/playlist.js
import client from "./client";

export async function getPlaylists() {
  const res = await client.get("/playlist/list");
  return res.data;
}

export async function getPlaylistTracks(id) {
  const res = await client.get(`/playlist/${id}/tracks`);
  return res.data;
}

export const removeTrackFromPlaylist = async (playlistId, trackId) => {
  const res = await client.delete(`/playlist/${playlistId}/remove_track`, {
    params: { track_id: String(trackId) },
  });
  return res.data;
};

export default { getPlaylists, getPlaylistTracks, removeTrackFromPlaylist };