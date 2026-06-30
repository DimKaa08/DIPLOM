// src/components/Player/Player.jsx
import { useContext, useEffect, useRef } from "react";
import axios from "axios";
import { PlayerContext } from "../../context/PlayerContext"; 
import "./Player.css";

export default function Player() {
  const { 
    queue, 
    currentIndex, 
    isPlaying, 
    setIsPlaying, 
    audioRef, 
    nextTrack, 
    prevTrack, 
    shuffle, 
    setShuffle, 
    repeat, 
    setRepeat 
  } = useContext(PlayerContext);
  
  const track = queue[currentIndex] || null;

  // Хранилище для ID трека, который СЕЙЧАС загружен в аудио-элемент
  const lastLoadedTrackId = useRef(null);

  // Метрики для сбора статистики (Используем refs, чтобы не триггерить ререндеры)
  const maxPositionRef = useRef(0);    // Максимальная секунда, до которой дослушал
  const durationRef = useRef(0);       // Длительность трека
  const isFinishedRef = useRef(false);  // Дослушал ли до конца
  const repeatRef = useRef(repeat);    // Защита от старых замыканий

  // Синхронизируем значение режима повтора для функции логирования
  useEffect(() => {
    repeatRef.current = repeat;
  }, [repeat]);

  // ФУНКЦИЯ ОТПРАВКИ ЛОГОВ НА БЭКЕНД
  const sendInteractionLog = async (trackId, stats) => {
    try {
      const token = localStorage.getItem("token");
      if (!token || !trackId) return;

      console.log(`[AI Logger] Отправка метрик для трека #${trackId}:`, stats);

      await axios.post("http://localhost:8000/activity/log", {
        track_id: trackId,
        listen_duration: Math.round(stats.listenDuration),
        completion_rate: parseFloat(stats.completionRate.toFixed(4)),
        is_finished: stats.isFinished,
        is_looped: stats.isLooped,
        was_skipped: stats.wasSkipped,
        skip_position: stats.wasSkipped ? Math.round(stats.skipPosition) : null,
        skip_type: stats.skipType
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
    } catch (err) {
      // ИСПРАВЛЕНО: Заменили print() на console.error(), чтобы не вызывалась печать страницы браузера
      console.error("Ошибка отправки логов взаимодействия:", err);
    }
  };

  // ЭФФЕКТ ДЛЯ СЛЕДЖЕНИЯ ЗА СМЕНОЙ ТРЕКОВ (Сбор датасета при переключении)
  useEffect(() => {
    if (!track) return;

    // Запоминаем текущий ID трека внутри эффекта
    const currentTrackId = track.id;

    // CLEANUP-функция: Вызывается строго В МОМЕНТ СМЕНЫ трека или закрытия плеера
    return () => {
      if (!currentTrackId) return;

      const duration = durationRef.current || 1;
      const skipPos = maxPositionRef.current;
      const isFinished = isFinishedRef.current;
      const wasSkipped = !isFinished;
      
      // Определяем тип пропуска на основе ТЗ:
      // immediate (сразу < 10 секунд) или partial (немного послушал и пропустил)
      let skipType = "none";
      if (wasSkipped) {
        skipType = skipPos < 10 ? "immediate" : "partial";
      }

      const completionRate = Math.min(skipPos / duration, 1.0);

      // Собираем пакет данных для ML модели
      const statsPayload = {
        listenDuration: skipPos,
        completionRate: completionRate,
        isFinished: isFinished,
        isLooped: repeatRef.current === "one",
        wasSkipped: wasSkipped,
        skipPosition: skipPos,
        skipType: skipType
      };

      // Отправляем пакет аналитики на сервер
      sendInteractionLog(currentTrackId, statsPayload);

      // СБРАСЫВАЕМ МЕТРИКИ для следующего трека
      maxPositionRef.current = 0;
      durationRef.current = 0;
      isFinishedRef.current = false;
    };
  }, [track?.id]); // Реагирует только на физическую смену ID трека


  // ЕДИНЫЙ ЭФФЕКТ ДЛЯ УПРАВЛЕНИЯ ПЛЕЕРОМ (Play/Pause/Src)
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    if (!track) {
      audio.pause();
      audio.src = "";
      lastLoadedTrackId.current = null;
      return;
    }

    const queryParams = new URLSearchParams({
      source: track.source || 'youtube',
      title: track.title || '',
      artist: track.artist || ''
    }).toString();
    const targetSrc = `http://localhost:8000/stream/${track.id}?${queryParams}`;

    if (lastLoadedTrackId.current !== track.id) {
      audio.src = targetSrc;
      audio.load(); 
      lastLoadedTrackId.current = track.id;
    }

    if (isPlaying) {
      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch(err => {
          if (err.name === "AbortError") {
            console.log("Воспроизведение перехвачено новым треком.");
          } else {
            console.error("Критическая ошибка при воспроизведении:", err);
          }
        });
      }
    } else {
      audio.pause();
    }
  }, [track, isPlaying, audioRef]);

  return (
    <>
      {/* Слушатели HTML5 аудио собирают аналитику в реальном времени без лагов UI */}
      <audio 
        ref={audioRef} 
        onEnded={() => {
          isFinishedRef.current = true; // Выставляем флаг: трек дослушан успешно
          nextTrack();
        }} 
        onLoadedMetadata={(e) => {
          durationRef.current = e.target.duration; // Запоминаем точную длину трека в сек.
        }}
        onTimeUpdate={(e) => {
          // Фиксируем максимальную точку прогресса, до которой дошел ползунок
          if (e.target.currentTime > maxPositionRef.current) {
            maxPositionRef.current = e.target.currentTime;
          }
        }}
      />

      {track && (
        <div className="player">
          <div className="player-info">
            <div className="player-title">{track.title || "Без названия"}</div>
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