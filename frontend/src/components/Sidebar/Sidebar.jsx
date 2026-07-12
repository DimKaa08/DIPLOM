// frontend/src/components/Sidebar/Sidebar.jsx
import React from "react";

export default function Sidebar({ onSelectPlaylist }) {
  const playlists = [
    { id: "recommendations", name: "Умные рекомендации", icon: "✦" },
    { id: "favorites",       name: "Моё избранное",      icon: "♡" },
  ];

  return (
    <aside className="sidebar">
      <h3>Медиатека</h3>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {playlists.map((pl) => (
          <li
            key={pl.id}
            className="playlist-item"
            onClick={() => onSelectPlaylist(pl)}
          >
            <span style={{ fontSize: 14, flexShrink: 0 }}>{pl.icon}</span>
            {pl.name}
          </li>
        ))}
      </ul>
    </aside>
  );
}