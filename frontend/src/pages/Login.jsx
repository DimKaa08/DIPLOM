import { useState, useContext } from "react";
import { AuthContext } from "../context/AuthContext";
import { login } from "../api/auth";

export default function Login() {
  const { setToken, setUser } = useContext(AuthContext);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");

    try {
      const data = await login(email, password);
      setToken(data.access_token);
      setUser({ id: data.user_id, email });

      // переход на главную
      window.location.href = "/";
    } catch (err) {
      setError("Неверный email или пароль");
    }
  };

  return (
    <div className="auth-container">
      <h2>Вход</h2>

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

        <button type="submit">Войти</button>
      </form>

      <p>
        Нет аккаунта?{" "}
        <a href="/register">Создать</a>
      </p>
    </div>
  );
}
