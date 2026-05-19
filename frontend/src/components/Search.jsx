import { useState } from "react";
import { searchTracks } from "../api/search";

export default function SearchBar({ onResults }) {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("youtube");
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    try {
      const results = await searchTracks(query, source);
      onResults(results);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="search-bar">
      <form onSubmit={handleSearch} className="search-form">
        <input
          type="text"
          placeholder="Поиск музыки..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />

        <select value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="youtube">YouTube</option>
          <option value="soundcloud">SoundCloud</option>
          <option value="spotify">Spotify</option>
        </select>

        <button type="submit" disabled={loading}>
          {loading ? "Поиск..." : "Найти"}
        </button>
      </form>
    </div>
  );
}
