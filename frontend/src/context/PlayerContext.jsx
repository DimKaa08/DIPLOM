import { createContext, useState, useRef, useEffect } from "react";
import axios from "axios"; // Импортируем axios для связи с бэкендом

export const PlayerContext = createContext(null);

export function PlayerProvider({ children }) {
  const audioRef = useRef(null);
  const [queue, setQueue] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [shuffle, setShuffle] = useState(false);
  const [repeat, setRepeat] = useState("none");

  // Состояние избранного (инициализируем из localStorage как резерв)
  const [favorites, setFavorites] = useState(() => {
    const saved = localStorage.getItem("player_favorites");
    return saved ? JSON.parse(saved) : [];
  });

  // === СИНХРОНИЗАЦИЯ С БЭКЕНДОМ ПРИ ЗАГРУЗКЕ ===
  useEffect(() => {
    const fetchBackendFavorites = async () => {
      const token = localStorage.getItem("token");
      if (!token) return;

      try {
        // Замени URL на свой эндпоинт получения избранного, если он отличается
        const res = await axios.get("http://localhost:8000/favorites", {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (Array.isArray(res.data)) {
          setFavorites(res.data);
          localStorage.setItem("player_favorites", JSON.stringify(res.data));
        }
      } catch (err) {
        console.error("Не удалось загрузить избранное с сервера, используем локальное:", err);
      }
    };

    fetchBackendFavorites();
  }, []);

  // Резервное сохранение локально при любых изменениях
  useEffect(() => {
    localStorage.setItem("player_favorites", JSON.stringify(favorites));
  }, [favorites]);


  // === ФУНКЦИЯ ДОБАВЛЕНИЯ / УДАЛЕНИЯ ИЗБРАННОГО ===
  const toggleFavorite = async (track) => {
    // ЗАЩИТА: Если объект трека "битый" или у него нет ID (как у Unknown Title), прерываем работу
    if (!track || !track.id) {
      console.warn("[PlayerContext] Невозможно лайкнуть трек без ID:", track);
      return;
    }
    
    const token = localStorage.getItem("token");
    const isAlreadyFavorite = favorites.some((t) => t.id === track.id);

    // 1. Оптимистичное обновление интерфейса (сердечко загорится сразу, не дожидаясь ответа сервера)
    setFavorites((prevFavorites) => {
      if (isAlreadyFavorite) {
        return prevFavorites.filter((t) => t.id !== track.id);
      } else {
        return [...prevFavorites, track];
      }
    });

    if (!token) return;

    // 2. Синхронизация с базой данных бэкенда
    try {
      const safeTrackId = encodeURIComponent(track.id);
      
      if (isAlreadyFavorite) {
        // Удаляем из избранного на бэкенде
        // (Предполагается эндпоинт DELETE /favorites/{track_id})
        await axios.delete(`http://localhost:8000/favorites/${safeTrackId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        console.log(`[API] Трек #${track.id} удален из избранного на сервере`);
      } else {
        // Добавляем в избранное на бэкенде
        // (Предполагается эндпоинт POST /favorites, принимающий JSON с track_id)
        await axios.post("http://localhost:8000/favorites", { 
          track_id: track.id 
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
        console.log(`[API] Трек #${track.id} успешно добавлен в избранное на сервере`);
      }
    } catch (err) {
      console.error("Ошибка при синхронизации избранного с бэкендом:", err.message);
      
      // Откат состояния UI в случае жесткой ошибки сети/сервера
      // (чтобы пользователь видел актуальный статус базы данных)
      const freshRes = await axios.get("http://localhost:8000/favorites", {
        headers: { Authorization: `Bearer ${token}` }
      }).catch(() => null);
      if (freshRes && Array.isArray(freshRes.data)) setFavorites(freshRes.data);
    }
  };

  const isTrackFavorite = (trackId) => {
    if (!trackId) return false;
    return favorites.some((t) => t.id === trackId);
  };
  // ==========================================

  const playTrack = (track, targetQueue = null) => {
    if (!track || !track.id) {
      console.warn("[PlayerContext] Отмена воспроизведения: трек отсутствует или не имеет ID");
      return;
    }

    const currentTracks = Array.isArray(targetQueue) ? targetQueue : queue;
    const foundIndex = currentTracks.findIndex((t) => t.id === track.id);
    const safeIndex = foundIndex !== -1 ? foundIndex : 0;

    setCurrentIndex(safeIndex);
    setIsPlaying(true);

    if (audioRef.current) {
      try {
        const safeTrackId = encodeURIComponent(track.id);
        const token = localStorage.getItem("token");
        const queryParams = token ? `?token=${token}` : "";
        const streamUrl = track.src || `http://localhost:8000/tracks/${safeTrackId}/stream${queryParams}`; 

        audioRef.current.src = streamUrl;
        audioRef.current.load(); 

        audioRef.current.play().catch(err => {
          console.error("[PlayerContext] Ошибка вызова .play():", err.message);
          setIsPlaying(false);
        });
      } catch (error) {
        console.error("[PlayerContext] Критическая ошибка при инициализации трека:", error);
        setIsPlaying(false);
      }
    }
  };

  const nextTrack = () => {
    if (queue.length === 0) return;
    const nextIndex = (currentIndex + 1) % queue.length;
    setCurrentIndex(nextIndex);
    playTrack(queue[nextIndex], queue);
  };

  const prevTrack = () => {
    if (queue.length === 0) return;
    const prevIndex = (currentIndex - 1 + queue.length) % queue.length;
    setCurrentIndex(prevIndex);
    playTrack(queue[prevIndex], queue);
  };

  return (
    <PlayerContext.Provider
      value={{
        audioRef, queue, setQueue,
        currentIndex, setCurrentIndex,
        isPlaying, setIsPlaying,
        playTrack, nextTrack, prevTrack,
        shuffle, setShuffle,
        repeat, setRepeat,
        favorites,
        toggleFavorite,
        isTrackFavorite
      }}
    >
      {children}
    </PlayerContext.Provider>
  );
}