import { useEffect, useRef, useState } from "react";
import "./Player.css";

export default function Player({ track }) {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    if (!track || !track.url) return;

    const audio = new Audio(track.url);
    audioRef.current = audio;

    audio.play();
    setIsPlaying(true);

    return () => {
      audio.pause();
    };
  }, [track]);

  const togglePlay = () => {
    if (!audioRef.current) return;

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  if (!track) return null;

  return (
    <div className="player">
      <div className="info">
        <strong>{track.title}</strong>
        <span>{track.artist}</span>
      </div>

      <button onClick={togglePlay}>
        {isPlaying ? "⏸ Пауза" : "▶️ Играть"}
      </button>
    </div>
  );
}
