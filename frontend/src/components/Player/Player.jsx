// frontend/src/components/Player/Player.jsx
import { useContext, useEffect, useRef, useState, useCallback } from "react";
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
    toggleFavorite, isTrackFavorite,
    dislikeTrack,
  } = useContext(PlayerContext);

  const track = queue[currentIndex] || null;

  const lastLoadedId  = useRef(null);
  const maxPosRef     = useRef(0);
  const durationRef   = useRef(0);
  const isFinishedRef = useRef(false);
  const repeatRef     = useRef(repeat);

  const [progress,    setProgress]    = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration,    setDuration]    = useState(0);

  // ── ГРОМКОСТЬ ─────────────────────────────────────────────────────────────
  const [volume,   setVolume]   = useState(0.7);
  const [isMuted,  setIsMuted]  = useState(false);
  const prevVolRef  = useRef(0.7);
  const isDragging  = useRef(false);
  const volBarRef   = useRef(null);

  useEffect(() => { repeatRef.current = repeat; }, [repeat]);

  // Синхронизируем volume с аудиоэлементом
  useEffect(() => {
    if (audioRef.current)
      audioRef.current.volume = isMuted ? 0 : volume;
  }, [volume, isMuted, audioRef]);

  // ── Плавная регулировка громкости (drag) ─────────────────────────────────
  const applyVolumeFromEvent = useCallback((e) => {
    const bar = volBarRef.current;
    if (!bar) return;
    const rect  = bar.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    setVolume(ratio);
    prevVolRef.current = ratio;
    if (isMuted && ratio > 0) setIsMuted(false);
  }, [isMuted]);

  const handleVolMouseDown = useCallback((e) => {
    isDragging.current = true;
    applyVolumeFromEvent(e);
  }, [applyVolumeFromEvent]);

  useEffect(() => {
    const onMove = (e) => { if (isDragging.current) applyVolumeFromEvent(e); };
    const onUp   = () => { isDragging.current = false; };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup",   onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup",   onUp);
    };
  }, [applyVolumeFromEvent]);

  const toggleMute = () => {
    if (!isMuted) { prevVolRef.current = volume; setIsMuted(true); }
    else { setIsMuted(false); setVolume(prevVolRef.current || 0.5); }
  };

  // ── ТЕЛЕМЕТРИЯ ───────────────────────────────────────────────────────────
  const sendLog = async (trackId, stats) => {
    if (!localStorage.getItem("token") || !trackId) return;
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
    } catch {}
  };

  useEffect(() => {
    if (!track) return;
    const id = track.id;
    return () => {
      if (!id) return;
      const dur = durationRef.current || 1;
      const pos = maxPosRef.current;
      const fin = isFinishedRef.current;
      sendLog(id, {
        listenDuration: pos,
        completionRate: Math.min(pos / dur, 1.0),
        isFinished:     fin,
        isLooped:       repeatRef.current === "one",
        wasSkipped:     !fin,
        skipPosition:   pos,
        skipType:       !fin ? (pos < 10 ? "immediate" : "partial") : "none",
      });
      maxPosRef.current = 0; durationRef.current = 0; isFinishedRef.current = false;
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
      audio.src    = src;
      audio.volume = isMuted ? 0 : volume;
      audio.load();
      lastLoadedId.current = track.id;
    }
    isPlaying
      ? audio.play().catch(e => { if (e.name !== "AbortError") setIsPlaying(false); })
      : audio.pause();
  }, [track, isPlaying, audioRef]);

  const seekTo = (e) => {
    const audio = audioRef.current;
    if (!audio || !durationRef.current) return;
    const rect  = e.currentTarget.getBoundingClientRect();
    audio.currentTime = ((e.clientX - rect.left) / rect.width) * durationRef.current;
  };

  const fmt = (s) => {
    if (!s || isNaN(s)) return "0:00";
    return `${Math.floor(s / 60)}:${Math.floor(s % 60).toString().padStart(2, "0")}`;
  };

  const audioProps = {
    ref: audioRef,
    onEnded: () => { isFinishedRef.current = true; nextTrack(); },
    onLoadedMetadata: e => { durationRef.current = e.target.duration; setDuration(e.target.duration); },
    onTimeUpdate: e => {
      const t = e.target.currentTime;
      if (t > maxPosRef.current) maxPosRef.current = t;
      setCurrentTime(t);
      setProgress(durationRef.current ? (t / durationRef.current) * 100 : 0);
    },
  };

  const effectiveVol = isMuted ? 0 : volume;
  const volIcon = effectiveVol === 0 ? "🔇" : effectiveVol < 0.4 ? "🔈" : effectiveVol < 0.7 ? "🔉" : "🔊";
  const isFav   = isTrackFavorite(track?.id);

  if (!track) return <audio {...audioProps} />;

  return (
    <>
      <audio {...audioProps} />

      <div className="player">

        {/* ── Левая: обложка + инфо + избранное + дизлайк ── */}
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

          {/* Добавить в избранное */}
          <button
            onClick={() => toggleFavorite(track)}
            title={isFav ? "Убрать из избранного" : "Добавить в избранное"}
            style={{
              background: "transparent", border: "none", cursor: "pointer",
              fontSize: 18, padding: "0 6px", lineHeight: 1,
              color: isFav ? "#fbbf24" : "var(--text-3)",
              transition: "color .15s, transform .1s",
            }}
            onMouseEnter={e => e.currentTarget.style.transform = "scale(1.2)"}
            onMouseLeave={e => e.currentTarget.style.transform = "scale(1)"}
          >
            {isFav ? "♥" : "♡"}
          </button>

          {/* Дизлайк — убрать из очереди, нейросеть запомнит */}
          <button
            onClick={() => dislikeTrack(track)}
            title="Не нравится — убрать из очереди (нейросеть запомнит)"
            style={{
              background: "transparent", border: "none", cursor: "pointer",
              fontSize: 16, padding: "0 4px", lineHeight: 1,
              color: "var(--text-4)", transition: "color .15s, transform .1s",
            }}
            onMouseEnter={e => { e.currentTarget.style.color = "#ef4444"; e.currentTarget.style.transform = "scale(1.2)"; }}
            onMouseLeave={e => { e.currentTarget.style.color = "var(--text-4)"; e.currentTarget.style.transform = "scale(1)"; }}
          >
            👎
          </button>
        </div>

        {/* ── Центр: кнопки + прогресс ── */}
        <div className="player-center">
          <div className="player-controls">
            <button className={`control-btn${shuffle ? " active" : ""}`}
              onClick={() => setShuffle(!shuffle)} title="Перемешать">⇄</button>
            <button className="control-btn" onClick={prevTrack} title="Предыдущий">⏮</button>
            <button className="play-pause-btn" onClick={() => setIsPlaying(!isPlaying)}>
              {isPlaying ? "⏸" : "▶"}
            </button>
            <button className="control-btn" onClick={nextTrack} title="Следующий">⏭</button>
            <button className={`control-btn${repeat !== "none" ? " active" : ""}`}
              onClick={() => setRepeat(repeat === "none" ? "all" : repeat === "all" ? "one" : "none")}>
              {repeat === "one" ? "↺¹" : "↺"}
            </button>
          </div>

          <div className="player-progress">
            <span className="progress-time">{fmt(currentTime)}</span>
            <div className="progress-track" onClick={seekTo}>
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <span className="progress-time right">{fmt(duration)}</span>
          </div>
        </div>

        {/* ── Правая: громкость с перетаскиванием ── */}
        <div className="player-right">
          <span
            className="volume-icon"
            onClick={toggleMute}
            title={isMuted ? "Включить звук" : "Выключить звук"}
            style={{ cursor: "pointer", userSelect: "none", fontSize: 15 }}
          >
            {volIcon}
          </span>

          {/* Ползунок: onMouseDown → drag → onMouseUp (через document) */}
          <div
            ref={volBarRef}
            className="volume-track"
            onMouseDown={handleVolMouseDown}
            title={`Громкость: ${Math.round(effectiveVol * 100)}%`}
            style={{ cursor: "ew-resize" }}
          >
            <div
              className="volume-fill"
              style={{
                width: `${effectiveVol * 100}%`,
                transition: isDragging.current ? "none" : "width .08s",
              }}
            />
            {/* Кружок-ручка */}
            <div style={{
              position: "absolute", top: "50%", left: `${effectiveVol * 100}%`,
              width: 10, height: 10, borderRadius: "50%",
              background: "var(--accent)", transform: "translate(-50%, -50%)",
              boxShadow: "0 0 0 2px var(--surface-2)",
              pointerEvents: "none",
            }} />
          </div>

          <span style={{
            fontSize: 10, color: "var(--text-4)",
            minWidth: 26, textAlign: "right", fontVariantNumeric: "tabular-nums",
          }}>
            {Math.round(effectiveVol * 100)}%
          </span>
        </div>

      </div>
    </>
  );
}