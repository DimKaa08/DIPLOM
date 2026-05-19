import { createContext, useState, useRef } from "react";

export const PlayerContext = createContext(null);

export function PlayerProvider({ children }) {
  const audioRef = useRef(null);

  const [queue, setQueue] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  const [shuffle, setShuffle] = useState(false);
  const [repeat, setRepeat] = useState("none"); // none | one | all

  const playTrack = (track, list = null) => {
    if (list) setQueue(list);
    const index = list ? list.indexOf(track) : queue.indexOf(track);
    setCurrentIndex(index);
  };

  const nextTrack = () => {
    if (repeat === "one") return;

    if (shuffle) {
      setCurrentIndex(Math.floor(Math.random() * queue.length));
      return;
    }

    if (currentIndex + 1 < queue.length) {
      setCurrentIndex(currentIndex + 1);
    } else if (repeat === "all") {
      setCurrentIndex(0);
    }
  };

  return (
    <PlayerContext.Provider
      value={{
        audioRef,
        queue,
        setQueue,
        currentIndex,
        setCurrentIndex,
        playTrack,
        nextTrack,
        shuffle,
        setShuffle,
        repeat,
        setRepeat
      }}
    >
      {children}
    </PlayerContext.Provider>
  );
}
