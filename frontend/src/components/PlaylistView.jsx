import { useContext, useEffect, useState } from "react";
import { PlayerContext } from "../context/PlayerContext";
import { AuthContext } from "../context/AuthContext";

import { addFavorite, removeFavorite, getFavorites } from "../api/favorites";
import { removeTrackFromPlaylist } from "../api/playlist";
import "./PlaylistView.css";

export default function PlaylistView({ tracks, playlistId, onTracksUpdated, onRefresh }) {
  const { playTrack, setQueue, favorites, toggleFavorite: contextToggleFavorite } = useContext(PlayerContext);
  const { token } = useContext(AuthContext);

  const [favoriteIds, setFavoriteIds] = useState(new Set());

  // Синхронизация сердечек
  useEffect(() => {
    if (!token) return;
    getFavorites(token).then((tracks) => {
      const ids = Array.isArray(tracks) ? tracks.map(t => t.id) : (tracks?.tracks?.map(t => t.id) || []);
      setFavoriteIds(new Set(ids));
    });
  }, [token]);

  const handlePlay = (track, event) => {
    if (event) event.stopPropagation(); 
    setQueue(tracks);
    playTrack(track, tracks); 
  };

  const toggleFavorite = async (track) => {
    const isFav = favoriteIds.has(track.id);
    const newSet = new Set(favoriteIds);

    if (isFav) newSet.delete(track.id);
    else newSet.add(track.id);

    setFavoriteIds(newSet);

    if (contextToggleFavorite) {
      contextToggleFavorite(track);
    }

    try {
      if (isFav) await removeFavorite(track.id, token);
      else await addFavorite(track.id, token);
    } catch (err) {
      console.error("Не удалось обновить лайк", err);
      setFavoriteIds(favoriteIds);
    }
  };

  const deleteTrack = async (track) => {
    if (!playlistId || playlistId === "recommendations") return;

    try {
      if (playlistId === "favorites_fallback" || playlistId === "favorites") {
        await removeFavorite(track.id, token);
        const newSet = new Set(favoriteIds);
        newSet.delete(track.id);
        setFavoriteIds(newSet);

        const isStillInContextFav = favorites.some((t) => t.id === track.id);
        if (isStillInContextFav && contextToggleFavorite) {
          contextToggleFavorite(track);
        }
      } else {
        await removeTrackFromPlaylist(playlistId, track.id, token);
      }

      const updated = tracks.filter((t) => t.id !== track.id);
      onTracksUpdated(updated);

    } catch (err) {
      console.error("Ошибка при удалении трека:", err);
      alert("Не удалось удалить трек с сервера.");
    }
  };

  return (
    <div className="playlist-view">
      
      {/* Красивая шапка с кнопкой обновления */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <h2>Треки</h2>
        {playlistId === "recommendations" && onRefresh && (
          <button 
            onClick={onRefresh}
            style={{
              padding: "8px 16px",
              backgroundColor: "#3b82f6",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              cursor: "pointer",
              fontWeight: "600",
              transition: "background 0.2s"
            }}
            onMouseOver={(e) => e.target.style.backgroundColor = "#2563eb"}
            onMouseOut={(e) => e.target.style.backgroundColor = "#3b82f6"}
          >
            🔄 Обновить рекомендации
          </button>
        )}
      </div>

      {tracks.length === 0 && <p style={{ opacity: 0.6 }}>Нет треков</p>}

      <div className="track-list">
        {tracks.map((track, index) => { 
          const isFav = favoriteIds.has(track.id);

          return (
            <div key={track.id || index} className="track-item">
              
              <div className="track-left" onClick={(e) => handlePlay(track, e)}>
                <div className="track-title">{track.title}</div>
                <div className="track-artist">{track.artist}</div>
              </div>

              <div className="track-actions">
                
                <button
                  className={`fav-btn ${isFav ? "fav" : ""}`}
                  onClick={() => toggleFavorite(track)}
                  style={{ background: "none", border: "none", cursor: "pointer", fontSize: "18px" }}
                >
                  {isFav ? "❤️" : "🤍"}
                </button>

                {/* Крестик скрывается, если это рекомендации */}
                {playlistId && playlistId !== "recommendations" && (
                  <button
                    className="delete-btn"
                    onClick={() => deleteTrack(track)}
                    title="Удалить трек"
                  >
                    ✖
                  </button>
                )}

                <button
                  className="play-btn"
                  onClick={(e) => handlePlay(track, e)}
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