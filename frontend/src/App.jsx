import { useState } from "react";
import searchApi from "./api/search";
import favoritesApi from "./api/favorites";
import playlistApi from "./api/playlist";
import "./App.css";

function App() {
  const [query, setQuery] = useState("");
  const [tracks, setTracks] = useState([]);
  const [currentTrack, setCurrentTrack] = useState(null);
  const [audio, setAudio] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(null);
  const [loop, setLoop] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);

  // 🔍 Поиск треков
  const handleSearch = async () => {
    if (!query.trim()) return;

    try {
      const res = await searchApi.searchTracks(query);
      setTracks(res);
    } catch (err) {
      console.error("Search error:", err);
    }
  };

  // ▶️ Проигрывание трека
  const playTrack = async (track, index) => {
    try {
      if (currentTrack && currentTrack.id === track.id && audio) {
        if (audio.paused) audio.play();
        else audio.pause();
        return;
      }

      const res = await fetch(
        `http://localhost:8000/stream/${track.id}?source=${track.source}`
      );
      const data = await res.json();

      if (audio) audio.pause();

      const newAudio = new Audio(data.url);

      newAudio.onloadedmetadata = () => {
        setDuration(newAudio.duration || 0);
      };

      newAudio.ontimeupdate = () => {
        setProgress(newAudio.currentTime || 0);
      };

      // ⭐ НАДЁЖНЫЙ АВТОПЕРЕХОД
      newAudio.addEventListener("ended", () => {
        if (loop) {
          newAudio.currentTime = 0;
          newAudio.play();
        } else {
          playNext();
        }
      });

      newAudio.loop = loop;
      newAudio.play();

      setAudio(newAudio);
      setCurrentTrack(track);
      setCurrentIndex(index);

    } catch (err) {
      console.error("Play error:", err);
    }
  };

  // ⏭ Следующий трек
  const playNext = () => {
    if (currentIndex === null) return;

    const nextIndex = currentIndex + 1;
    if (nextIndex < tracks.length) {
      playTrack(tracks[nextIndex], nextIndex);
    }
  };

  // ⏮ Предыдущий трек
  const playPrev = () => {
    if (currentIndex === null) return;

    const prevIndex = currentIndex - 1;
    if (prevIndex >= 0) {
      playTrack(tracks[prevIndex], prevIndex);
    }
  };

  // 🔁 Повтор трека
  const toggleLoop = () => {
    const newLoop = !loop;
    setLoop(newLoop);
    if (audio) audio.loop = newLoop;
  };

  // ⏩ Перемотка
  const seek = (value) => {
    if (!audio) return;
    audio.currentTime = value;
    setProgress(value);
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
  const loadRecommendations = async () => {
    const res = await fetch(`http://localhost:8000/recommendations/${userId}`);
    const data = await res.json();
    setTracks(data);
  };

  // ➕ Добавить в плейлист
  const addToPlaylist = async (track) => {
    alert("Добавление в плейлист пока не реализовано");
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

          {/* Прогресс и перемотка */}
          <div style={{ marginTop: 15 }}>
            <input
              type="range"
              min="0"
              max={duration || 0}
              value={progress}
              onChange={(e) => seek(Number(e.target.value))}
              style={{ width: "100%" }}
            />
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 12,
                marginTop: 4,
              }}
            >
              <span>{Math.floor(progress)} сек</span>
              <span>{Math.floor(duration)} сек</span>
            </div>
          </div>

          {/* 🎛 Управление плеером */}
          <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
            <button onClick={playPrev}>⏮ Предыдущий</button>
            <button onClick={() => playTrack(currentTrack, currentIndex)}>
              ⏯ Пауза / Играть
            </button>
            <button onClick={playNext}>⏭ Следующий</button>
            <button onClick={toggleLoop}>
              {loop ? "🔁 Повтор ВКЛ" : "🔁 Повтор ВЫКЛ"}
            <button onClick={loadRecommendations}>🎵 Рекомендации</button>

            </button>
          </div>
        </div>
      )}

      {/* 🎵 Результаты поиска */}
      <div style={{ marginTop: 30 }}>
        {tracks.map((track, index) => (
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
              <button onClick={() => playTrack(track, index)}>▶️ Play</button>
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
