import { useState } from "react";
import searchApi from "./api/search";
import favoritesApi from "./api/favorites";
import playlistApi from "./api/playlist";
import axios from "axios";

function App() {
  const [query, setQuery] = useState("");
  const [tracks, setTracks] = useState([]);
  const [currentTrack, setCurrentTrack] = useState(null);
  const [audio, setAudio] = useState(null);

  // 🔍 Поиск треков
  const handleSearch = async () => {
    if (!query.trim()) return;

    try {
      const res = await searchApi.search(query);
      setTracks(res.data);
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
      const data = await res.json();

      if (audio) audio.pause();

      const newAudio = new Audio(data.url);
      newAudio.play();

      setAudio(newAudio);
      setCurrentTrack(track);
    } catch (err) {
      console.error("Play error:", err);
    }
  };

  // ⭐ Добавить в избранное
  const addToFavorites = async (track) => {
    try {
      await favoritesApi.add(track.id, track.source);
      alert("Добавлено в избранное");
    } catch (err) {
      console.error("Favorites error:", err);
    }
  };

  // ➕ Добавить в плейлист
  const addToPlaylist = async (track) => {
    try {
      await playlistApi.addTrack(1, track.id); // плейлист №1 для примера
      alert("Добавлено в плейлист");
    } catch (err) {
      console.error("Playlist error:", err);
    }
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
