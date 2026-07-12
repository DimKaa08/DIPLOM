// frontend/src/context/PlayerContext.jsx
import { createContext, useState, useRef, useEffect, useCallback } from "react";
import { addFavorite, removeFavorite, getFavorites } from "../api/favorites";
import client, { API_BASE } from "../api/client";

export const PlayerContext = createContext(null);

export function PlayerProvider({ children }) {
  const audioRef = useRef(null);
  const [queue,         setQueue]         = useState([]);
  const [currentIndex,  setCurrentIndex]  = useState(0);
  const [isPlaying,     setIsPlaying]     = useState(false);
  const [shuffle,       setShuffle]       = useState(false);
  const [repeat,        setRepeat]        = useState("none");

  const [favorites, setFavorites] = useState(() => {
    try { return JSON.parse(localStorage.getItem("player_favorites") || "[]"); }
    catch { return []; }
  });

  // Колбэк «очередь закончилась» — устанавливается из Home.jsx
  const onQueueEndRef = useRef(null);
  const setOnQueueEnd = useCallback((fn) => { onQueueEndRef.current = fn; }, []);

  // ── СИНХРОНИЗАЦИЯ ИЗБРАННОГО ─────────────────────────────────────────────
  useEffect(() => {
    const sync = async () => {
      const token = localStorage.getItem("token");
      if (!token) return;
      try {
        const data = await getFavorites();
        if (Array.isArray(data)) {
          setFavorites(data);
          localStorage.setItem("player_favorites", JSON.stringify(data));
        }
      } catch {}
    };
    sync();
  }, []);

  useEffect(() => {
    localStorage.setItem("player_favorites", JSON.stringify(favorites));
  }, [favorites]);

  // ── ИЗБРАННОЕ ────────────────────────────────────────────────────────────
  const toggleFavorite = async (track) => {
    if (!track?.id) return;
    const isAlreadyFav = favorites.some((t) => t.id === track.id);
    // Оптимистичное обновление
    setFavorites((prev) =>
      isAlreadyFav ? prev.filter((t) => t.id !== track.id) : [...prev, track]
    );
    try {
      isAlreadyFav ? await removeFavorite(track.id) : await addFavorite(track);
    } catch {
      // Откат при ошибке
      try {
        const fresh = await getFavorites();
        if (Array.isArray(fresh)) setFavorites(fresh);
      } catch {}
    }
  };

  const isTrackFavorite = (trackId) =>
    !!trackId && favorites.some((t) => t.id === trackId);

  // ── ДИЗЛАЙК — убрать из очереди + сообщить нейросети ───────────────────
  const dislikeTrack = useCallback(async (track) => {
    if (!track?.id) return;

    // 1. Убираем трек из очереди немедленно
    setQueue((prevQueue) => {
      const newQueue = prevQueue.filter((t) => t.id !== track.id);

      if (newQueue.length === 0) {
        setIsPlaying(false);
        setCurrentIndex(0);
      } else {
        // Сохраняем воспроизведение следующего трека
        setCurrentIndex((prevIdx) => {
          const removedIdx = prevQueue.findIndex((t) => t.id === track.id);
          if (removedIdx < 0) return prevIdx;
          // Если убрали трек до текущего — сдвигаем индекс
          if (removedIdx < prevIdx) return prevIdx - 1;
          // Если убрали текущий — играем следующий (тот же индекс в новой очереди)
          if (removedIdx === prevIdx) {
            const nextIdx = Math.min(prevIdx, newQueue.length - 1);
            if (newQueue[nextIdx] && audioRef.current) {
              const t = newQueue[nextIdx];
              const params = new URLSearchParams({
                source: t.source || "youtube",
                title:  t.title  || "",
                artist: t.artist || "",
              });
              audioRef.current.src = `${API_BASE}/stream/${encodeURIComponent(t.id)}?${params}`;
              audioRef.current.load();
              audioRef.current.play().catch(() => setIsPlaying(false));
            }
            return nextIdx;
          }
          return prevIdx;
        });
      }

      return newQueue;
    });

    // 2. Отправляем негативный сигнал нейросети
    try {
      await client.post(`/recommendations/dislike/${encodeURIComponent(track.id)}`);
      console.log(`[ML] Дизлайк трека ${track.id} отправлен`);
    } catch (e) {
      console.error("[Dislike]", e.message);
    }
  }, [audioRef]);

  // ── ВОСПРОИЗВЕДЕНИЕ ──────────────────────────────────────────────────────
  const playTrack = useCallback((track, targetQueue = null) => {
    if (!track?.id) return;
    const tracks     = Array.isArray(targetQueue) ? targetQueue : queue;
    const foundIndex = tracks.findIndex((t) => t.id === track.id);
    setCurrentIndex(foundIndex !== -1 ? foundIndex : 0);
    setIsPlaying(true);

    if (audioRef.current) {
      const params = new URLSearchParams({
        source: track.source || "youtube",
        title:  track.title  || "",
        artist: track.artist || "",
      });
      const src = track.src || `${API_BASE}/stream/${encodeURIComponent(track.id)}?${params}`;
      audioRef.current.src = src;
      audioRef.current.load();
      audioRef.current.play().catch((e) => {
        if (e.name !== "AbortError") setIsPlaying(false);
      });
    }
  }, [queue, audioRef]);

  const nextTrack = useCallback(() => {
    if (!queue.length) return;

    if (repeat === "one") {
      if (audioRef.current) {
        audioRef.current.currentTime = 0;
        audioRef.current.play().catch(() => {});
      }
      return;
    }

    const isLast = currentIndex >= queue.length - 1;
    if (isLast && repeat !== "all") {
      setIsPlaying(false);
      if (onQueueEndRef.current) onQueueEndRef.current();
      return;
    }

    const nextIdx = shuffle
      ? Math.floor(Math.random() * queue.length)
      : (currentIndex + 1) % queue.length;
    setCurrentIndex(nextIdx);
    playTrack(queue[nextIdx], queue);
  }, [queue, currentIndex, repeat, shuffle, playTrack]);

  const prevTrack = useCallback(() => {
    if (!queue.length) return;
    const prev = (currentIndex - 1 + queue.length) % queue.length;
    setCurrentIndex(prev);
    playTrack(queue[prev], queue);
  }, [queue, currentIndex, playTrack]);

  // ── ПРЕДЗАГРУЗКА СЛЕДУЮЩИХ ТРЕКОВ ────────────────────────────────────────
  // Пока играет текущий трек, в фоне прогреваем Redis-кеш для следующих 2 треков.
  // Когда пользователь нажмёт «следующий» — URL уже готов, задержки нет.
  useEffect(() => {
    const toPreload = queue.slice(currentIndex + 1, currentIndex + 3);
    if (!toPreload.length) return;

    const token = localStorage.getItem("token");

    toPreload.forEach((track) => {
      if (!track?.id) return;
      const params = new URLSearchParams({
        source: track.source || "youtube",
        title:  track.title  || "",
        artist: track.artist || "",
      });
      const url = `${API_BASE}/stream/preload/${encodeURIComponent(track.id)}?${params}`;
      // fire-and-forget: ошибки игнорируем, это только оптимизация
      fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(30000), // не висеть вечно
      }).catch(() => {});
    });
  }, [currentIndex, queue]);


  return (
    <PlayerContext.Provider value={{
      audioRef, queue, setQueue,
      currentIndex, setCurrentIndex,
      isPlaying, setIsPlaying,
      playTrack, nextTrack, prevTrack,
      shuffle, setShuffle,
      repeat, setRepeat,
      favorites, toggleFavorite, isTrackFavorite,
      dislikeTrack,
      setOnQueueEnd,
    }}>
      {children}
    </PlayerContext.Provider>
  );
}