import { useState } from "react";
import { register } from "../api/auth";

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleRegister = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    try {
      await register(email, password);
      setSuccess("Регистрация успешна! Теперь войдите.");
    } catch (err) {
      setError("Ошибка: возможно, email уже зарегистрирован");
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
        {success && <div className="auth-success">{success}</div>}

        <button type="submit">Создать аккаунт</button>
      </form>

      <p>
        Уже есть аккаунт?{" "}
        <a href="/login">Войти</a>
      </p>
    </div>
  );
}
