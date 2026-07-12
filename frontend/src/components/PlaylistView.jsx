// frontend/src/components/PlaylistView.jsx
import { useContext, useEffect, useState } from "react";
import { PlayerContext } from "../context/PlayerContext";
import { AuthContext } from "../context/AuthContext";
import { addFavorite, removeFavorite, getFavorites } from "../api/favorites";
import { removeTrackFromPlaylist } from "../api/playlist";
import "./PlaylistView.css";

export default function PlaylistView({ tracks, playlistId, onTracksUpdated, onRefresh }) {
  const { playTrack, setQueue, queue, currentIndex, isPlaying, favorites, toggleFavorite: ctxToggle } = useContext(PlayerContext);
  const { token } = useContext(AuthContext);
  const [favoriteIds, setFavoriteIds] = useState(new Set());

  const currentTrackId = queue[currentIndex]?.id;

  useEffect(() => {
    if (!token) return;
    getFavorites(token).then((data) => {
      const ids = Array.isArray(data) ? data.map(t => t.id) : (data?.tracks?.map(t => t.id) || []);
      setFavoriteIds(new Set(ids));
    });
  }, [token]);

  const handlePlay = (track, e) => {
    if (e) e.stopPropagation();
    setQueue(tracks);
    playTrack(track, tracks);
  };

  const toggleFav = async (track) => {
    const isFav = favoriteIds.has(track.id);
    const next  = new Set(favoriteIds);
    isFav ? next.delete(track.id) : next.add(track.id);
    setFavoriteIds(next);
    if (ctxToggle) ctxToggle(track);
    try {
      isFav ? await removeFavorite(track.id, token) : await addFavorite(track, token);
    } catch {
      setFavoriteIds(favoriteIds);
    }
  };

  const deleteTrack = async (track) => {
    if (!playlistId || playlistId === "recommendations") return;
    try {
      if (playlistId === "favorites") {
        await removeFavorite(track.id, token);
        const next = new Set(favoriteIds);
        next.delete(track.id);
        setFavoriteIds(next);
        if (favorites.some(t => t.id === track.id) && ctxToggle) ctxToggle(track);
      } else {
        await removeTrackFromPlaylist(playlistId, track.id, token);
      }
      onTracksUpdated(tracks.filter(t => t.id !== track.id));
    } catch (err) {
      console.error("Ошибка при удалении трека:", err);
    }
  };

  if (tracks.length === 0) {
    return (
      <div className="playlist-view">
        <div className="empty-state">
          <div className="empty-icon">♪</div>
          <div className="empty-text">Нет треков</div>
        </div>
      </div>
    );
  }

  return (
    <div className="playlist-view">
      {/* Заголовок секции */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        {onRefresh && playlistId === "recommendations" && (
          <button
            onClick={onRefresh}
            style={{
              marginLeft: "auto",
              padding: "6px 14px",
              background: "var(--surface-1)",
              border: "0.5px solid var(--border-2)",
              borderRadius: "var(--radius-sm)",
              color: "var(--text-2)",
              fontSize: 12,
              cursor: "pointer",
              fontFamily: "var(--sans)",
              transition: "color .15s, border-color .15s",
            }}
            onMouseOver={e => { e.currentTarget.style.color = "var(--text-1)"; e.currentTarget.style.borderColor = "var(--text-3)"; }}
            onMouseOut={e => { e.currentTarget.style.color = "var(--text-2)"; e.currentTarget.style.borderColor = "var(--border-2)"; }}
          >
            ↺ Обновить
          </button>
        )}
      </div>

      <div className="track-list">
        {tracks.map((track, index) => {
          const isFav     = favoriteIds.has(track.id);
          const isPlaying = track.id === currentTrackId;

          return (
            <div
              key={track.id || index}
              className={`track-item${isPlaying ? " playing" : ""}`}
              onClick={(e) => handlePlay(track, e)}
            >
              {/* Номер / иконка воспроизведения */}
              <div className="track-num">{index + 1}</div>
              <div className="track-play-icon">{isPlaying ? "▶" : "▶"}</div>

              {/* Обложка */}
              <div className="track-thumb">
                {track.thumbnail_url
                  ? <img src={track.thumbnail_url} alt="" />
                  : <span style={{ fontSize: 16, opacity: 0.4 }}>♪</span>
                }
              </div>

              {/* Название + артист */}
              <div className="track-info">
                <div className="track-title">{track.title || "Без названия"}</div>
                <div className="track-artist">{track.artist || "Неизвестный артист"}</div>
              </div>

              {/* Действия */}
              <div className="track-actions" onClick={e => e.stopPropagation()}>
                <button
                  className={`fav-btn${isFav ? " fav" : ""}`}
                  onClick={() => toggleFav(track)}
                  title={isFav ? "Убрать из избранного" : "Добавить в избранное"}
                >
                  {isFav ? "♥" : "♡"}
                </button>

                {playlistId && playlistId !== "recommendations" && (
                  <button
                    className="delete-btn"
                    onClick={() => deleteTrack(track)}
                    title="Удалить"
                  >
                    ✕
                  </button>
                )}

                <button
                  className="play-btn"
                  onClick={(e) => handlePlay(track, e)}
                  title="Слушать"
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