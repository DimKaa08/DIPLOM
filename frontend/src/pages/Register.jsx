// frontend/src/pages/Register.jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { register } from "../api/auth";

export default function Register() {
  const navigate = useNavigate();
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState("");
  const [loading,  setLoading]  = useState(false);

  const handleRegister = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await register(email, password);
      // Помечаем что новый пользователь — нужно показать онбординг после входа
      localStorage.setItem("show_onboarding", "true");
      // Переходим на логин с подсказкой
      navigate("/login", { state: { message: "Аккаунт создан! Войди чтобы начать." } });
    } catch (err) {
      setError("Ошибка: возможно, email уже зарегистрирован");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <h2>Регистрация</h2>

      <form onSubmit={handleRegister} className="auth-form">
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
          {loading ? "Создаю аккаунт..." : "Создать аккаунт"}
        </button>
      </form>

      <p>
        Уже есть аккаунт?{" "}
        <a href="/login">Войти</a>
      </p>
    </div>
  );
}