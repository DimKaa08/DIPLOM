// frontend/src/components/Search.jsx
import { useState } from "react";
import { searchTracks } from "../api/search";

export default function SearchBar({ onResults }) {
  const [query,  setQuery]  = useState("");
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
    <form onSubmit={handleSearch} style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <div style={{ position: "relative", flex: 1 }}>
        <svg
          style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", color: "var(--text-4)", pointerEvents: "none" }}
          width="15" height="15" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        >
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          type="text"
          placeholder="Поиск треков, артистов…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{
            width: "100%",
            background: "var(--surface-1)",
            border: "0.5px solid var(--border-2)",
            borderRadius: "var(--radius)",
            padding: "9px 14px 9px 36px",
            color: "var(--text-1)",
            fontSize: 13,
            outline: "none",
            fontFamily: "var(--sans)",
          }}
          onFocus={e => e.target.style.borderColor = "var(--accent)"}
          onBlur={e => e.target.style.borderColor = "var(--border-2)"}
        />
      </div>

      <select
        value={source}
        onChange={(e) => setSource(e.target.value)}
        style={{
          background: "var(--surface-1)",
          border: "0.5px solid var(--border-2)",
          borderRadius: "var(--radius)",
          padding: "9px 12px",
          color: "var(--text-2)",
          fontSize: 13,
          outline: "none",
          fontFamily: "var(--sans)",
          cursor: "pointer",
        }}
      >
        <option value="youtube">YouTube</option>
        <option value="soundcloud">SoundCloud</option>
        <option value="spotify">Spotify</option>
      </select>

      <button
        type="submit"
        disabled={loading}
        style={{
          background: loading ? "var(--surface-2)" : "var(--accent)",
          border: "none",
          borderRadius: "var(--radius)",
          padding: "9px 18px",
          color: "#fff",
          fontSize: 13,
          fontWeight: 500,
          cursor: loading ? "not-allowed" : "pointer",
          fontFamily: "var(--sans)",
          transition: "background .15s",
          flexShrink: 0,
        }}
      >
        {loading ? "…" : "Найти"}
      </button>
    </form>
  );
}