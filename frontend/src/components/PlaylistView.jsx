import { useContext, useEffect, useState } from "react";
import { PlayerContext } from "../context/PlayerContext";
import { AuthContext } from "../context/AuthContext";

import { addFavorite, removeFavorite, listFavorites } from "../api/favorites";
import { removeTrackFromPlaylist } from "../api/playlist";
import "./PlaylistView.css";

export default function PlaylistView({ tracks, playlistId, onTracksUpdated }) {
  const { playTrack, setQueue } = useContext(PlayerContext);
  const { token } = useContext(AuthContext);

  const [favoriteIds, setFavoriteIds] = useState(new Set());

  useEffect(() => {
    if (!token) return;
    listFavorites(token).then((ids) => setFavoriteIds(new Set(ids)));
  }, [token]);

  const handlePlay = (track) => {
    setQueue(tracks);
    playTrack(track, tracks);
  };

  const toggleFavorite = async (track) => {
    const isFav = favoriteIds.has(track.id);
    const newSet = new Set(favoriteIds);

    if (isFav) newSet.delete(track.id);
    else newSet.add(track.id);

    setFavoriteIds(newSet);

    try {
      if (isFav) await removeFavorite(track.id, token);
      else await addFavorite(track.id, token);
    } catch {
      setFavoriteIds(favoriteIds); // rollback
    }
  };

  const deleteTrack = async (track) => {
    if (!playlistId) return; // нельзя удалить из "Рекомендаций"

    try {
      await removeTrackFromPlaylist(playlistId, track.id, token);

      const updated = tracks.filter((t) => t.id !== track.id);
      onTracksUpdated(updated);
    } catch (err) {
      console.error("Ошибка удаления трека", err);
    }
  };

  return (
    <div className="playlist-view">
      <h2>Треки</h2>

      {tracks.length === 0 && <p style={{ opacity: 0.6 }}>Нет треков</p>}

      <div className="track-list">
        {tracks.map((track) => {
          const isFav = favoriteIds.has(track.id);

          return (
            <div key={track.id} className="track-item">
              <div className="track-left" onClick={() => handlePlay(track)}>
                <div className="track-title">{track.title}</div>
                <div className="track-artist">{track.artist}</div>
              </div>

              <div className="track-actions">
                <button
                  className={`fav-btn ${isFav ? "fav" : ""}`}
                  onClick={() => toggleFavorite(track)}
                >
                  {isFav ? "★" : "☆"}
                </button>

                {playlistId && (
                  <button
                    className="delete-btn"
                    onClick={() => deleteTrack(track)}
                    title="Удалить из плейлиста"
                  >
                    ✖
                  </button>
                )}

                <button
                  className="play-btn"
                  onClick={() => handlePlay(track)}
                >
                  ▶
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
