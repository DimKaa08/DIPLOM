import { useState, useContext } from "react";
import Sidebar from "../components/Sidebar/Sidebar";
import Player from "../components/Player/Player";
import PlaylistView from "../components/PlaylistView";
import SearchBar from "../components/SearchBar";
import { AuthContext } from "../context/AuthContext";
import { getPlaylistTracks } from "../api/playlists";
import { getRecommendations } from "../api/recommendations";

export default function Home() {
  const { token, user } = useContext(AuthContext);
  const [tracks, setTracks] = useState([]);
  const [selectedPlaylist, setSelectedPlaylist] = useState(null);

  const loadPlaylist = async (pl) => {
    setSelectedPlaylist(pl);

    if (pl.id === "recommendations") {
      const data = await getRecommendations(user.id, token);
      setTracks(data.tracks);
    } else {
      const data = await getPlaylistTracks(pl.id, token);
      setTracks(data);
    }
  };

  return (
    <div className="home">
      <Sidebar onSelectPlaylist={loadPlaylist} />

      <div className="content">
        <SearchBar onResults={(res) => {
          setSelectedPlaylist(null);
          setTracks(res);
        }} />

        <PlaylistView
          tracks={tracks}
          playlistId={selectedPlaylist?.id}
          onTracksUpdated={setTracks}
        />
      </div>

      <Player />
    </div>
  );
}

