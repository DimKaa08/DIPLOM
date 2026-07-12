// frontend/src/pages/Login.jsx
import { useState, useContext } from "react";
import { useLocation } from "react-router-dom";
import { AuthContext } from "../context/AuthContext";
import { login } from "../api/auth";

export default function Login() {
  const { setToken, setUser } = useContext(AuthContext);
  const location = useLocation();

  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState("");
  const [loading,  setLoading]  = useState(false);

  // Сообщение после регистрации (передаётся через navigate state)
  const successMessage = location.state?.message;

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await login(email, password);

      // Сохраняем токен и пользователя в AuthContext + localStorage
      setToken(data.access_token);
      setUser({ id: data.user_id, email });

      // Переходим на главную — Home.jsx проверит show_onboarding сам
      window.location.href = "/";
    } catch (err) {
      setError("Неверный email или пароль");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <h2>Вход</h2>

      {successMessage && (
        <div className="auth-success" style={{
          background: "var(--accent-dim)", color: "var(--accent)",
          padding: "10px 14px", borderRadius: 8, marginBottom: 14, fontSize: 13,
        }}>
          ✓ {successMessage}
        </div>
      )}

      <form onSubmit={handleLogin} className="auth-form">
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Пароль"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        {error && <div className="auth-error">{error}</div>}

        <button type="submit" disabled={loading}>
          {loading ? "Входим..." : "Войти"}
        </button>
      </form>

      <p>
        Нет аккаунта?{" "}
        <a href="/register">Создать</a>
      </p>
    </div>
  );
}