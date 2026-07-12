// frontend/src/pages/Home.jsx
import { useState, useEffect, useContext, useCallback } from "react";
import client from "../api/client";
import { getFavorites } from "../api/favorites";
import { AuthContext } from "../context/AuthContext";
import { PlayerContext } from "../context/PlayerContext";
import Sidebar from "../components/Sidebar/Sidebar";
import SearchBar from "../components/Search";
import PlaylistView from "../components/PlaylistView";
import Player from "../components/Player/Player";
import Onboarding from "../components/Onboarding/Onboarding";

export default function Home() {
  const { logout, user }                              = useContext(AuthContext);
  const { queue, currentIndex, setQueue, setOnQueueEnd } = useContext(PlayerContext);

  const [tracks, setTracks]                         = useState([]);
  const [selectedPlaylistId, setSelectedPlaylistId] = useState("recommendations");
  const [viewTitle, setViewTitle]                   = useState("Персональные рекомендации 🧠");
  const [isRecommendations, setIsRecommendations]   = useState(true);
  const [isLoading, setIsLoading]                   = useState(false);

  // ── ОНБОРДИНГ ─────────────────────────────────────────────────────────────
  // Флаг show_onboarding ставится в Register.jsx после регистрации.
  // Флаг onboarding_done_{userId} ставится после завершения онбординга.
  // Таким образом каждый пользователь видит онбординг ровно один раз.
  const needsOnboarding = useCallback(() => {
    const userId = user?.id;
    if (!userId) return false;
    // Новый пользователь только что зарегистрировался
    if (localStorage.getItem("show_onboarding") === "true") return true;
    // Пользователь ещё не прошёл онбординг (смена аккаунта)
    if (!localStorage.getItem(`onboarding_done_${userId}`)) return true;
    return false;
  }, [user?.id]);

  const [showOnboarding, setShowOnboarding] = useState(false);

  // Проверяем онбординг когда user загрузился из AuthContext
  useEffect(() => {
    if (user?.id) {
      setShowOnboarding(needsOnboarding());
    }
  }, [user?.id, needsOnboarding]);

  const handleOnboardingComplete = useCallback(() => {
    const userId = user?.id;
    // Снимаем глобальный флаг (установлен после регистрации)
    localStorage.removeItem("show_onboarding");
    // Ставим флаг для конкретного пользователя
    if (userId) localStorage.setItem(`onboarding_done_${userId}`, "1");
    setShowOnboarding(false);
    // Загружаем рекомендации с учётом только что выбранных жанров
    loadRecommendations();
  }, [user?.id]);

  // ── РЕКОМЕНДАЦИИ ──────────────────────────────────────────────────────────
  const loadRecommendations = useCallback(async (silent = false) => {
    if (!silent) setIsLoading(true);
    try {
      const { data } = await client.get("/recommendations");
      const newTracks = data?.tracks && Array.isArray(data.tracks) ? data.tracks : [];
      setTracks(newTracks);
      setViewTitle("Персональные рекомендации 🧠");
      setIsRecommendations(true);
      if (data?.playlist_id) setSelectedPlaylistId(data.playlist_id);
      if (newTracks.length > 0 && queue.length === 0) {
        setQueue(newTracks);
      }
    } catch (error) {
      console.error("[Home] Ошибка загрузки рекомендаций:", error);
      try {
        const { data } = await client.get("/playlist/recommendations");
        setTracks(data?.tracks && Array.isArray(data.tracks) ? data.tracks : []);
        setViewTitle("Рекомендации 🎵");
        setIsRecommendations(true);
        if (data?.id) setSelectedPlaylistId(data.id);
      } catch (fallbackError) {
        console.error("[Home] Фолбек тоже упал:", fallbackError);
      }
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, [queue.length, setQueue]);

  // При монтировании — загружаем рекомендации только если онбординг не нужен
  useEffect(() => {
    if (user?.id && !needsOnboarding()) {
      loadRecommendations();
    }
  }, [user?.id]);

  // Авто-перезагрузка когда очередь заканчивается
  useEffect(() => {
    if (!setOnQueueEnd) return;
    setOnQueueEnd(() => async () => {
      try {
        const { data } = await client.get("/recommendations");
        const newTracks = data?.tracks && Array.isArray(data.tracks) ? data.tracks : [];
        if (newTracks.length > 0) {
          setTracks(newTracks);
          setQueue(newTracks);
        }
      } catch (e) {
        console.error("[Home] Авто-перезагрузка:", e);
      }
    });
  }, [setOnQueueEnd, setQueue]);

  const loadFavorites = async () => {
    try {
      const responseData = await getFavorites();
      const rawTracks = Array.isArray(responseData)
        ? responseData
        : (responseData?.tracks || responseData?.items || []);
      const flattenedTracks = rawTracks.map((item) => {
        if (item?.track) {
          return { ...item.track, source: item.track.source || "youtube", favorite_relation_id: item.id };
        }
        return item?.source ? item : { ...item, source: "youtube" };
      });
      setTracks(flattenedTracks);
      setViewTitle("Моё Избранное ⭐");
      setIsRecommendations(false);
      setSelectedPlaylistId("favorites");
    } catch (err) {
      console.error("[Home] Ошибка загрузки избранного:", err);
    }
  };

  const handleSelectPlaylist = async (playlistKey) => {
    if (playlistKey.id === "recommendations") {
      await loadRecommendations();
    } else if (playlistKey.id === "favorites") {
      await loadFavorites();
    } else {
      setIsRecommendations(false);
      setSelectedPlaylistId(playlistKey.id);
    }
  };

  const handleSearchResults = (results) => {
    setTracks(Array.isArray(results) ? results : []);
    setViewTitle("Результаты поиска 🔍");
    setIsRecommendations(false);
    setSelectedPlaylistId(null);
  };

  const currentTrack = queue[currentIndex] || null;

  return (
    <>
      {showOnboarding && (
        <Onboarding onComplete={handleOnboardingComplete} />
      )}

      <div className="app-layout">
        <header className="app-header">
          <div className="logo-section">
            <h1>Music Platform</h1>
            {user && <span className="user-badge">👤 {user.email}</span>}
          </div>
          <button onClick={logout} className="logout-btn">Выйти</button>
        </header>

        <div className="main-container">
          <Sidebar onSelectPlaylist={handleSelectPlaylist} />

          <main className="content-area">
            <SearchBar onResults={handleSearchResults} />

            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <h2 className="view-title" style={{ margin: 0 }}>{viewTitle}</h2>
              {isRecommendations && (
                <button
                  onClick={() => loadRecommendations()}
                  disabled={isLoading}
                  style={{
                    background: "transparent",
                    border: "0.5px solid var(--border-2)",
                    borderRadius: "var(--radius-sm)",
                    color: isLoading ? "var(--text-4)" : "var(--text-2)",
                    padding: "4px 12px", fontSize: 12, cursor: "pointer",
                    fontFamily: "var(--sans)", transition: "color .15s",
                  }}
                >
                  {isLoading ? "..." : "↺ Обновить"}
                </button>
              )}
            </div>

            <PlaylistView
              tracks={tracks}
              playlistId={isRecommendations ? "recommendations" : selectedPlaylistId}
              onTracksUpdated={setTracks}
              showDislike={isRecommendations}
              onRefresh={
                isRecommendations
                  ? loadRecommendations
                  : selectedPlaylistId === "favorites"
                  ? loadFavorites
                  : null
              }
            />
          </main>
        </div>

        {currentTrack && <Player track={currentTrack} />}
      </div>
    </>
  );
}