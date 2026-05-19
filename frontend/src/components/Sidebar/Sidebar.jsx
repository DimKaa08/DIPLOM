import { useEffect, useState, useContext } from "react";
import { AuthContext } from "../../context/AuthContext";
import { getPlaylists } from "../../api/playlists";

export default function Sidebar({ onSelectPlaylist }) {
  const { token } = useContext(AuthContext);
  const [playlists, setPlaylists] = useState([]);

  useEffect(() => {
    if (token) {
      getPlaylists(token).then(setPlaylists);
    }
  }, [token]);

  return (
    <div className="sidebar">
      <h2>Плейлисты</h2>

      {playlists.map(pl => (
        <div
          key={pl.id}
          className="playlist-item"
          onClick={() => onSelectPlaylist(pl)}
        >
          {pl.name}
        </div>
      ))}

      <div
        className="playlist-item"
        onClick={() => onSelectPlaylist({ id: "recommendations", name: "Рекомендации" })}
      >
        ⭐ Рекомендации
      </div>
    </div>
  );
}

