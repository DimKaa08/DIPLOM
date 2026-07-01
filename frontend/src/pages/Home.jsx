// frontend/src/pages/Home.jsx
import { useState, useEffect, useContext } from "react";
import client from "../api/client";
import { getFavorites } from "../api/favorites";
import { AuthContext } from "../context/AuthContext";
import { PlayerContext } from "../context/PlayerContext";
import Sidebar from "../components/Sidebar/Sidebar";
import SearchBar from "../components/Search";
import PlaylistView from "../components/PlaylistView";
import Player from "../components/Player/Player";

export default function Home() {
  const { logout, user }          = useContext(AuthContext);
  const { queue, currentIndex }   = useContext(PlayerContext);

  const [tracks, setTracks]                       = useState([]);
  const [selectedPlaylistId, setSelectedPlaylistId] = useState("recommendations");
  const [viewTitle, setViewTitle]                 = useState("Персональные рекомендации 🧠");
  const [isRecommendations, setIsRecommendations] = useState(true);

  useEffect(() => { loadRecommendations(); }, []);

  const loadRecommendations = async () => {
    try {
      // client.js добавляет baseURL и токен — никакого хардкода
      const { data } = await client.get("/playlist/recommendations");
      setTracks(data?.tracks && Array.isArray(data.tracks) ? data.tracks : []);
      setViewTitle("Персональные рекомендации 🧠");
      setIsRecommendations(true);
      if (data?.id) setSelectedPlaylistId(data.id);
    } catch (error) {
      console.error("[Home] Ошибка загрузки рекомендаций:", error);
    }
  };

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
    setViewTitle("Результаты поиска");
    setIsRecommendations(false);
    setSelectedPlaylistId(null);
  };

  const currentTrack = queue[currentIndex] || null;

  return (
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
          <h2 className="view-title">{viewTitle}</h2>
          <PlaylistView
            tracks={tracks}
            playlistId={isRecommendations ? "recommendations" : selectedPlaylistId}
            onTracksUpdated={setTracks}
            onRefresh={isRecommendations ? loadRecommendations : (selectedPlaylistId === "favorites" ? loadFavorites : null)}
          />
        </main>
      </div>

      {currentTrack && <Player track={currentTrack} />}
    </div>
  );
}
