// frontend/src/components/Onboarding/Onboarding.jsx
import { useState, useRef } from "react";
import client from "../../api/client";

const GENRES = [
  { id: "pop",         label: "Поп",          emoji: "🎤" },
  { id: "rock",        label: "Рок",          emoji: "🎸" },
  { id: "electronic",  label: "Электронная",  emoji: "🎛️" },
  { id: "hip-hop",     label: "Хип-хоп",      emoji: "🎧" },
  { id: "jazz",        label: "Джаз",         emoji: "🎷" },
  { id: "classical",   label: "Классика",     emoji: "🎻" },
  { id: "r&b",         label: "R&B / Soul",   emoji: "🎵" },
  { id: "metal",       label: "Метал",        emoji: "🤘" },
  { id: "indie",       label: "Инди",         emoji: "🌿" },
  { id: "chill",       label: "Chill",        emoji: "😌" },
];

export default function Onboarding({ onComplete }) {
  const [step, setStep] = useState("genres");       // "genres" | "cookies" | "done"
  const [selectedGenres, setSelectedGenres] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [cookieResult, setCookieResult] = useState(null);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  const toggleGenre = (id) => {
    setSelectedGenres((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const saveGenres = async () => {
    if (selectedGenres.size === 0) {
      setError("Выбери хотя бы один жанр");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await client.post("/onboarding/genres", {
        genres: Array.from(selectedGenres),
      });
      setStep("cookies");
    } catch (e) {
      setError("Ошибка сохранения. Попробуй снова.");
    } finally {
      setLoading(false);
    }
  };

  const uploadCookies = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await client.post("/onboarding/upload-cookies", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setCookieResult(data);
    } catch (e) {
      setError("Не удалось прочитать файл cookies. Убедись что это Netscape-формат.");
    } finally {
      setLoading(false);
    }
  };

  const skip = () => onComplete();

  const S = {
    overlay: {
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 999, backdropFilter: "blur(4px)",
    },
    modal: {
      background: "var(--surface-1)", borderRadius: 16, padding: "32px 36px",
      width: "min(560px, 95vw)", maxHeight: "90vh", overflowY: "auto",
      border: "0.5px solid var(--border-2)",
    },
    title: { fontSize: 22, fontWeight: 600, color: "var(--text-1)", margin: "0 0 6px" },
    sub:   { fontSize: 13, color: "var(--text-3)", margin: "0 0 24px", lineHeight: 1.5 },
    genres: { display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 24 },
    genre: (sel) => ({
      padding: "10px 16px", borderRadius: 10, cursor: "pointer", fontSize: 13,
      border: `1.5px solid ${sel ? "var(--accent)" : "var(--border-2)"}`,
      background: sel ? "var(--accent-dim)" : "var(--surface-2)",
      color: sel ? "var(--accent)" : "var(--text-2)",
      display: "flex", alignItems: "center", gap: 7, transition: "all .15s",
    }),
    btn: (primary) => ({
      padding: "10px 24px", borderRadius: 8, fontSize: 14, fontWeight: 500,
      border: "none", cursor: "pointer", fontFamily: "var(--sans)",
      background: primary ? "var(--accent)" : "var(--surface-2)",
      color: primary ? "#fff" : "var(--text-2)",
      transition: "background .15s",
    }),
    row: { display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 8 },
    step: { fontSize: 11, color: "var(--text-4)", marginBottom: 4 },
    err: { fontSize: 12, color: "#ef4444", marginTop: 8 },
    importBox: {
      border: "1.5px dashed var(--border-2)", borderRadius: 10,
      padding: "28px 20px", textAlign: "center", marginBottom: 20, cursor: "pointer",
    },
    result: {
      background: "var(--surface-2)", borderRadius: 8, padding: "12px 16px", marginBottom: 16,
    },
  };

  return (
    <div style={S.overlay} onClick={(e) => e.target === e.currentTarget && skip()}>
      <div style={S.modal}>

        {/* ── ШАГ 1: ЖАНРЫ ── */}
        {step === "genres" && (
          <>
            <p style={S.step}>Шаг 1 из 2</p>
            <h2 style={S.title}>Какую музыку ты слушаешь?</h2>
            <p style={S.sub}>Выбери жанры, которые тебе нравятся — мы сразу подберём что-то подходящее</p>

            <div style={S.genres}>
              {GENRES.map(({ id, label, emoji }) => (
                <div
                  key={id}
                  style={S.genre(selectedGenres.has(id))}
                  onClick={() => toggleGenre(id)}
                >
                  <span>{emoji}</span> {label}
                </div>
              ))}
            </div>

            {error && <p style={S.err}>{error}</p>}

            <div style={S.row}>
              <button style={S.btn(false)} onClick={skip}>Пропустить</button>
              <button
                style={S.btn(true)}
                onClick={saveGenres}
                disabled={loading}
              >
                {loading ? "Сохраняю..." : "Далее →"}
              </button>
            </div>
          </>
        )}

        {/* ── ШАГ 2: COOKIES ── */}
        {step === "cookies" && !cookieResult && (
          <>
            <p style={S.step}>Шаг 2 из 2 (необязательно)</p>
            <h2 style={S.title}>Импорт из YouTube</h2>
            <p style={S.sub}>
              Загрузи файл <strong>cookies.txt</strong> из YouTube — мы прочитаем твои
              «Понравившиеся видео» и сразу создадим персональные рекомендации.
              <br /><br />
              <strong>Как получить файл:</strong><br />
              1. Установи расширение <em>«Get cookies.txt LOCALLY»</em> в Chrome<br />
              2. Зайди на <em>youtube.com</em> (должен быть авторизован)<br />
              3. Нажми на расширение → Export → сохрани <em>cookies.txt</em>
            </p>

            <div
              style={S.importBox}
              onClick={() => fileRef.current?.click()}
            >
              <div style={{ fontSize: 32, marginBottom: 8 }}>🍪</div>
              <div style={{ fontSize: 14, color: "var(--text-2)", marginBottom: 4 }}>
                Нажми чтобы выбрать cookies.txt
              </div>
              <div style={{ fontSize: 11, color: "var(--text-4)" }}>
                Файл используется только для чтения истории — мы не храним пароли
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".txt"
                style={{ display: "none" }}
                onChange={uploadCookies}
              />
            </div>

            {loading && (
              <p style={{ textAlign: "center", color: "var(--text-3)", fontSize: 13, marginBottom: 16 }}>
                Читаю YouTube-историю... это займёт несколько секунд
              </p>
            )}
            {error && <p style={S.err}>{error}</p>}

            <div style={S.row}>
              <button style={S.btn(false)} onClick={skip}>Пропустить</button>
            </div>
          </>
        )}

        {/* ── РЕЗУЛЬТАТ ИМПОРТА ── */}
        {step === "cookies" && cookieResult && (
          <>
            <div style={{ textAlign: "center", marginBottom: 20 }}>
              <div style={{ fontSize: 48, marginBottom: 8 }}>✅</div>
              <h2 style={{ ...S.title, textAlign: "center" }}>Готово!</h2>
              <p style={{ ...S.sub, textAlign: "center" }}>
                {cookieResult.message}
              </p>
            </div>

            {cookieResult.tracks?.length > 0 && (
              <div style={S.result}>
                <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 8, fontWeight: 500 }}>
                  Первые импортированные треки:
                </div>
                {cookieResult.tracks.slice(0, 5).map((t, i) => (
                  <div key={i} style={{ fontSize: 12, color: "var(--text-2)", padding: "3px 0" }}>
                    {i + 1}. {t.title} — {t.artist}
                  </div>
                ))}
              </div>
            )}

            <div style={S.row}>
              <button style={S.btn(true)} onClick={skip}>
                Перейти к рекомендациям 🎵
              </button>
            </div>
          </>
        )}

      </div>
    </div>
  );
}