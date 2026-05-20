import { useState } from "react";
import searchApi from "./api/search";
import favoritesApi from "./api/favorites";
import playlistApi from "./api/playlist"; // пока не используем
import "./App.css";
import "./components/Player/Player.jsx";
import "./components/PlaylistView.jsx";




function App() {
  const [query, setQuery] = useState("");
  const [tracks, setTracks] = useState([]);
  const [currentTrack, setCurrentTrack] = useState(null);
  const [audio, setAudio] = useState(null);

  // 🔍 Поиск треков
  const handleSearch = async () => {
    if (!query.trim()) return;

    try {
      const res = await searchApi.searchTracks(query); // res — уже массив
      setTracks(res);
    } catch (err) {
      console.error("Search error:", err);
    }
  };

  // ▶️ Проигрывание трека
  const playTrack = async (track) => {
    try {
      const res = await fetch(
        `http://localhost:8000/stream/${track.id}?source=${track.source}`
      );
      const data = await res.json(); // ожидаем { url: "..." }

      if (audio) {
        audio.pause();
      }

      const newAudio = new Audio(data.url);
      await newAudio.play();

      setAudio(newAudio);
      setCurrentTrack({
        ...track,
        url: data.url
      });
    } catch (err) {
      console.error("Play error:", err);
    }
  };

  // ⭐ Добавить в избранное
  const addToFavorites = async (track) => {
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        alert("Нужна авторизация для избранного");
        return;
      }

      await favoritesApi.addFavorite(track.id, token);
      alert("Добавлено в избранное");
    } catch (err) {
      console.error("Favorites error:", err);
    }
  };

  // ➕ Добавить в плейлист (пока заглушка, чтобы не ломать приложение)
  const addToPlaylist = async (track) => {
    console.warn("addToPlaylist пока не реализован на backend");
    alert("Добавление в плейлист пока не реализовано");
    // когда появится endpoint:
    // await playlistApi.addTrack(playlistId, track.id, token);
  };

  return (
    <div style={{ padding: 40, maxWidth: 800, margin: "0 auto" }}>
      <h1>Музыкальный поиск</h1>

      {/* 🔍 Поисковая строка */}
      <div style={{ display: "flex", gap: 10 }}>
        <input
          type="text"
          placeholder="Введите название трека..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ flex: 1, padding: 10, fontSize: 16 }}
        />
        <button onClick={handleSearch}>Поиск</button>
      </div>

      {/* ▶️ Сейчас играет */}
      {currentTrack && (
        <div style={{ marginTop: 20, padding: 10, border: "1px solid #ccc" }}>
          <h3>Сейчас играет:</h3>
          <p>
            {currentTrack.title} — {currentTrack.artist}
          </p>
        </div>
      )}

      {/* 🎵 Результаты поиска */}
      <div style={{ marginTop: 30 }}>
        {tracks.map((track) => (
          <div
            key={track.id}
            style={{
              padding: 10,
              borderBottom: "1px solid #ddd",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div>
              <strong>{track.title}</strong>
              <br />
              <span>{track.artist}</span>
            </div>

            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={() => playTrack(track)}>▶️ Play</button>
              <button onClick={() => addToFavorites(track)}>⭐ Fav</button>
              <button onClick={() => addToPlaylist(track)}>➕ Playlist</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
