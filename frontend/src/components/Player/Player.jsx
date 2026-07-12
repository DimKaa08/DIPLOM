// frontend/src/components/Player/Player.jsx
import { useContext, useEffect, useRef, useState } from "react";
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

  const lastLoadedId  = useRef(null);
  const maxPosRef     = useRef(0);
  const durationRef   = useRef(0);
  const isFinishedRef = useRef(false);
  const repeatRef     = useRef(repeat);

  const [progress,  setProgress]  = useState(0);   // 0–100
  const [currentTime, setCurrentTime] = useState(0);
  const [duration,  setDuration]  = useState(0);

  useEffect(() => { repeatRef.current = repeat; }, [repeat]);

  const fmt = (s) => {
    if (!s || isNaN(s)) return "0:00";
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60).toString().padStart(2, "0");
    return `${m}:${sec}`;
  };

  const sendLog = async (trackId, stats) => {
    const token = localStorage.getItem("token");
    if (!token || !trackId) return;
    try {
      await client.post("/activity/log", {
        track_id:        trackId,
        listen_duration: parseInt(Math.round(stats.listenDuration), 10),
        completion_rate: parseFloat(stats.completionRate.toFixed(4)),
        is_finished:     stats.isFinished,
        is_looped:       stats.isLooped,
        was_skipped:     stats.wasSkipped,
        skip_position:   stats.wasSkipped ? Math.round(stats.skipPosition) : null,
        skip_type:       stats.skipType,
      });
    } catch (err) {
      console.error("[AI Logger]", err);
    }
  };

  useEffect(() => {
    if (!track) return;
    const id = track.id;
    return () => {
      if (!id) return;
      const dur      = durationRef.current || 1;
      const pos      = maxPosRef.current;
      const finished = isFinishedRef.current;
      sendLog(id, {
        listenDuration: pos,
        completionRate: Math.min(pos / dur, 1.0),
        isFinished:     finished,
        isLooped:       repeatRef.current === "one",
        wasSkipped:     !finished,
        skipPosition:   pos,
        skipType:       !finished ? (pos < 10 ? "immediate" : "partial") : "none",
      });
      maxPosRef.current     = 0;
      durationRef.current   = 0;
      isFinishedRef.current = false;
    };
  }, [track?.id]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (!track) { audio.pause(); audio.src = ""; lastLoadedId.current = null; return; }

    const params = new URLSearchParams({
      source: track.source || "youtube",
      title:  track.title  || "",
      artist: track.artist || "",
    });
    const src = `${API_BASE}/stream/${encodeURIComponent(track.id)}?${params}`;

    if (lastLoadedId.current !== track.id) {
      audio.src = src;
      audio.load();
      lastLoadedId.current = track.id;
    }

    isPlaying
      ? audio.play().catch(e => { if (e.name !== "AbortError") console.error(e); })
      : audio.pause();
  }, [track, isPlaying, audioRef]);

  const seekTo = (e) => {
    const audio = audioRef.current;
    if (!audio || !durationRef.current) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    audio.currentTime = ratio * durationRef.current;
  };

  if (!track) return (
    <audio
      ref={audioRef}
      onEnded={() => { isFinishedRef.current = true; nextTrack(); }}
      onLoadedMetadata={e => { durationRef.current = e.target.duration; setDuration(e.target.duration); }}
      onTimeUpdate={e => {
        const t = e.target.currentTime;
        if (t > maxPosRef.current) maxPosRef.current = t;
        setCurrentTime(t);
        setProgress(durationRef.current ? (t / durationRef.current) * 100 : 0);
      }}
    />
  );

  return (
    <>
      <audio
        ref={audioRef}
        onEnded={() => { isFinishedRef.current = true; nextTrack(); }}
        onLoadedMetadata={e => { durationRef.current = e.target.duration; setDuration(e.target.duration); }}
        onTimeUpdate={e => {
          const t = e.target.currentTime;
          if (t > maxPosRef.current) maxPosRef.current = t;
          setCurrentTime(t);
          setProgress(durationRef.current ? (t / durationRef.current) * 100 : 0);
        }}
      />

      <div className="player">

        {/* ── Левая: обложка + инфо ── */}
        <div className="player-info">
          <div className="player-thumb">
            {track.thumbnail_url
              ? <img src={track.thumbnail_url} alt="" />
              : <span style={{ fontSize: 20, opacity: 0.4 }}>♪</span>
            }
          </div>
          <div className="player-text">
            <div className="player-title">{track.title  || "Без названия"}</div>
            <div className="player-artist">{track.artist || "Неизвестный артист"}</div>
          </div>
        </div>

        {/* ── Центр: кнопки + прогресс ── */}
        <div className="player-center">
          <div className="player-controls">
            <button
              className={`control-btn${shuffle ? " active" : ""}`}
              onClick={() => setShuffle(!shuffle)}
              title="Перемешать"
            >
              ⇄
            </button>

            <button className="control-btn" onClick={prevTrack} title="Предыдущий">
              ⏮
            </button>

            <button
              className="play-pause-btn"
              onClick={() => setIsPlaying(!isPlaying)}
              title={isPlaying ? "Пауза" : "Играть"}
            >
              {isPlaying ? "⏸" : "▶"}
            </button>

            <button className="control-btn" onClick={nextTrack} title="Следующий">
              ⏭
            </button>

            <button
              className={`control-btn${repeat !== "none" ? " active" : ""}`}
              onClick={() => setRepeat(repeat === "none" ? "all" : repeat === "all" ? "one" : "none")}
              title="Повтор"
            >
              {repeat === "one" ? "↺¹" : "↺"}
            </button>
          </div>

          {/* Прогресс-бар */}
          <div className="player-progress">
            <span className="progress-time">{fmt(currentTime)}</span>
            <div className="progress-track" onClick={seekTo}>
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <span className="progress-time right">{fmt(duration)}</span>
          </div>
        </div>

        {/* ── Правая: громкость ── */}
        <div className="player-right">
          <span className="volume-icon">♪</span>
          <div className="volume-track">
            <div className="volume-fill" />
          </div>
        </div>

      </div>
    </>
  );
}