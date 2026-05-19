import { useContext, useEffect } from "react";
import { PlayerContext } from "../../context/PlayerContext";

export default function Player() {
  const { audioRef, queue, currentIndex, nextTrack } = useContext(PlayerContext);

  const current = queue[currentIndex];

  useEffect(() => {
    if (audioRef.current && current) {
      audioRef.current.src = `http://localhost:8000/stream?track_id=${current.source_id}&source=${current.source}`;
      audioRef.current.play();
    }
  }, [current]);

  return (
    <div className="player">
      <audio
        ref={audioRef}
        onEnded={nextTrack}
        controls
        style={{ width: "100%" }}
      />

      {current && (
        <div className="track-info">
          <h3>{current.title}</h3>
          <p>{current.artist}</p>
        </div>
      )}
    </div>
  );
}
