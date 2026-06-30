import React from "react";

export default function Sidebar({ onSelectPlaylist }) {
  // Статичные плейлисты платформы: рекомендации и избранное
  const staticPlaylists = [
    { id: "recommendations", name: "🧠 Умные рекомендации", icon: "🧠" },
    { id: "favorites", name: "⭐ Моё Избранное", icon: "⭐" }
  ];

  return (
    <aside className="sidebar" style={{ width: 240, background: "#1a1a1a", padding: 20 }}>
      <h3 style={{ color: "#7f8c8d", fontSize: 12, textTransform: "uppercase", letterSpacing: 1 }}>
        Моя медиатека
      </h3>
      <ul style={{ listStyle: "none", padding: 0, margin: "10px 0 0 0" }}>
        {staticPlaylists.map((playlist) => (
          <li
            key={playlist.id}
            onClick={() => onSelectPlaylist(playlist)}
            className="playlist-item"
            style={{
              padding: "10px 12px",
              cursor: "pointer",
              borderRadius: 6,
              color: "#fff",
              marginBottom: 5,
              transition: "0.2s"
            }}
          >
            <span style={{ marginRight: 10 }}>{playlist.icon}</span>
            {playlist.name}
          </li>
        ))}
      </ul>
    </aside>
  );
}