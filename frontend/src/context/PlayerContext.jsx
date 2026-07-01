// frontend/src/context/PlayerContext.jsx
import { createContext, useState, useRef, useEffect } from "react";
import { addFavorite, removeFavorite, getFavorites } from "../api/favorites";
import { API_BASE } from "../api/client";

export const PlayerContext = createContext(null);

export function PlayerProvider({ children }) {
  const audioRef     = useRef(null);
  const [queue, setQueue]               = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying]       = useState(false);
  const [shuffle, setShuffle]           = useState(false);
  const [repeat, setRepeat]             = useState("none");

  const [favorites, setFavorites] = useState(() => {
    const saved = localStorage.getItem("player_favorites");
    return saved ? JSON.parse(saved) : [];
  });

  // Синхронизируем избранное с сервером при монтировании
  useEffect(() => {
    const syncFavorites = async () => {
      const token = localStorage.getItem("token");
      if (!token) return;
      try {
        // Токен подставляет интерцептор в client.js — параметр не нужен
        const data = await getFavorites();
        if (Array.isArray(data)) {
          setFavorites(data);
          localStorage.setItem("player_favorites", JSON.stringify(data));
        }
      } catch (err) {
        console.error("[PlayerContext] Не удалось загрузить избранное:", err);
      }
    };
    syncFavorites();
  }, []);

  useEffect(() => {
    localStorage.setItem("player_favorites", JSON.stringify(favorites));
  }, [favorites]);

  // Добавление / удаление из избранного
  const toggleFavorite = async (track) => {
    if (!track?.id) {
      console.warn("[PlayerContext] Нельзя лайкнуть трек без ID:", track);
      return;
    }

    const token             = localStorage.getItem("token");
    const isAlreadyFavorite = favorites.some((t) => t.id === track.id);

    // Оптимистичное обновление UI
    setFavorites((prev) =>
      isAlreadyFavorite
        ? prev.filter((t) => t.id !== track.id)
        : [...prev, track]
    );

    if (!token) return;

    try {
      if (isAlreadyFavorite) {
        await removeFavorite(track.id);
      } else {
        await addFavorite(track);
      }
    } catch (err) {
      console.error("[Favorites] Ошибка синхронизации:", err.message);
      // Откат до актуального состояния БД
      try {
        const freshData = await getFavorites();
        if (Array.isArray(freshData)) setFavorites(freshData);
      } catch { /* оставляем локальный кэш */ }
    }
  };

  const isTrackFavorite = (trackId) => {
    if (!trackId) return false;
    return favorites.some((t) => t.id === trackId);
  };

  // Воспроизведение
  const playTrack = (track, targetQueue = null) => {
    if (!track?.id) {
      console.warn("[PlayerContext] Нет трека или ID");
      return;
    }

    const currentTracks = Array.isArray(targetQueue) ? targetQueue : queue;
    const foundIndex    = currentTracks.findIndex((t) => t.id === track.id);
    setCurrentIndex(foundIndex !== -1 ? foundIndex : 0);
    setIsPlaying(true);

    if (audioRef.current) {
      try {
        const params    = new URLSearchParams({
          source: track.source || "youtube",
          title:  track.title  || "",
          artist: track.artist || "",
        });
        // API_BASE из client.js — единственное место, где живёт URL сервера
        const streamUrl = track.src || `${API_BASE}/stream/${encodeURIComponent(track.id)}?${params}`;

        audioRef.current.src = streamUrl;
        audioRef.current.load();
        audioRef.current.play().catch((err) => {
          console.error("[PlayerContext] Ошибка .play():", err.message);
          setIsPlaying(false);
        });
      } catch (error) {
        console.error("[PlayerContext] Критическая ошибка:", error);
        setIsPlaying(false);
      }
    }
  };

  const nextTrack = () => {
    if (!queue.length) return;
    const next = (currentIndex + 1) % queue.length;
    setCurrentIndex(next);
    playTrack(queue[next], queue);
  };

  const prevTrack = () => {
    if (!queue.length) return;
    const prev = (currentIndex - 1 + queue.length) % queue.length;
    setCurrentIndex(prev);
    playTrack(queue[prev], queue);
  };

  return (
    <PlayerContext.Provider value={{
      audioRef, queue, setQueue,
      currentIndex, setCurrentIndex,
      isPlaying, setIsPlaying,
      playTrack, nextTrack, prevTrack,
      shuffle, setShuffle,
      repeat, setRepeat,
      favorites, toggleFavorite, isTrackFavorite,
    }}>
      {children}
    </PlayerContext.Provider>
  );
}
