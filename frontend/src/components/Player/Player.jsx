// frontend/src/components/Player/Player.jsx
import { useContext, useEffect, useRef } from "react";
import client, { API_BASE } from "../../api/client";
import { PlayerContext } from "../../context/PlayerContext";
import "./Player.css";

export default function Player() {
  const {
    queue, currentIndex,
    isPlaying, setIsPlaying,
    audioRef, nextTrack, prevTrack,
    shuffle, setShuffle,
    repeat, setRepeat,
  } = useContext(PlayerContext);

  const track = queue[currentIndex] || null;

  const lastLoadedTrackId = useRef(null);
  const maxPositionRef    = useRef(0);
  const durationRef       = useRef(0);
  const isFinishedRef     = useRef(false);
  const repeatRef         = useRef(repeat);

  useEffect(() => { repeatRef.current = repeat; }, [repeat]);

  // Отправка метрик прослушивания на бэкенд для ML
  const sendInteractionLog = async (trackId, stats) => {
    const token = localStorage.getItem("token");
    if (!token || !trackId) return;

    try {
      // client.js подставляет baseURL и токен автоматически
      await client.post("/activity/log", {
        track_id:        trackId,
        listen_duration: Math.round(stats.listenDuration),
        completion_rate: parseFloat(stats.completionRate.toFixed(4)),
        is_finished:     stats.isFinished,
        is_looped:       stats.isLooped,
        was_skipped:     stats.wasSkipped,
        skip_position:   stats.wasSkipped ? Math.round(stats.skipPosition) : null,
        skip_type:       stats.skipType,
      });
    } catch (err) {
      console.error("[AI Logger] Ошибка отправки метрик:", err);
    }
  };

  // Логирование при смене трека
  useEffect(() => {
    if (!track) return;
    const currentTrackId = track.id;

    return () => {
      if (!currentTrackId) return;

      const duration       = durationRef.current || 1;
      const skipPos        = maxPositionRef.current;
      const isFinished     = isFinishedRef.current;
      const wasSkipped     = !isFinished;
      const completionRate = Math.min(skipPos / duration, 1.0);

      let skipType = "none";
      if (wasSkipped) {
        skipType = skipPos < 10 ? "immediate" : "partial";
      }

      sendInteractionLog(currentTrackId, {
        listenDuration: skipPos,
        completionRate,
        isFinished,
        isLooped:    repeatRef.current === "one",
        wasSkipped,
        skipPosition: skipPos,
        skipType,
      });

      maxPositionRef.current = 0;
      durationRef.current    = 0;
      isFinishedRef.current  = false;
    };
  }, [track?.id]);

  // Управление воспроизведением
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    if (!track) {
      audio.pause();
      audio.src = "";
      lastLoadedTrackId.current = null;
      return;
    }

    const params = new URLSearchParams({
      source: track.source || "youtube",
      title:  track.title  || "",
      artist: track.artist || "",
    });

    // API_BASE из client.js — единственное место хранения URL сервера
    const targetSrc = `${API_BASE}/stream/${encodeURIComponent(track.id)}?${params}`;

    if (lastLoadedTrackId.current !== track.id) {
      audio.src = targetSrc;
      audio.load();
      lastLoadedTrackId.current = track.id;
    }

    if (isPlaying) {
      audio.play().catch((err) => {
        if (err.name !== "AbortError") {
          console.error("[Player] Ошибка воспроизведения:", err);
        }
      });
    } else {
      audio.pause();
    }
  }, [track, isPlaying, audioRef]);

  return (
    <>
      <audio
        ref={audioRef}
        onEnded={() => { isFinishedRef.current = true; nextTrack(); }}
        onLoadedMetadata={(e) => { durationRef.current = e.target.duration; }}
        onTimeUpdate={(e) => {
          if (e.target.currentTime > maxPositionRef.current) {
            maxPositionRef.current = e.target.currentTime;
          }
        }}
      />

      {track && (
        <div className="player">
          <div className="player-info">
            <div className="player-title">{track.title   || "Без названия"}</div>
            <div className="player-artist">{track.artist || "Неизвестный исполнитель"}</div>
          </div>

          <div className="player-controls">
            <button onClick={prevTrack} className="control-btn">⏮</button>

            <button className="play-pause-btn" onClick={() => setIsPlaying(!isPlaying)}>
              {isPlaying ? "⏸ Пауза" : "▶️ Играть"}
            </button>

            <button onClick={nextTrack} className="control-btn">⏭</button>

            <button
              onClick={() => setShuffle(!shuffle)}
              className={`control-btn ${shuffle ? "active" : ""}`}
              style={{ opacity: shuffle ? 1 : 0.5 }}
            >
              🔀
            </button>

            <button
              onClick={() => setRepeat(repeat === "none" ? "all" : repeat === "all" ? "one" : "none")}
              className="control-btn"
            >
              🔁 {repeat === "one" ? "①" : repeat === "all" ? "🔂" : ""}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
