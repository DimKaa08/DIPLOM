import { Routes, Route, Navigate } from "react-router-dom";
import { useContext } from "react";

import { AuthContext } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Home from "./pages/Home";

function App() {
  const { token } = useContext(AuthContext);

  return (
    <Routes>

      {/* Главная — только для авторизованных */}
      <Route
        path="/"
        element={token ? <Home /> : <Navigate to="/login" replace />}
      />

      {/* Логин */}
      <Route
        path="/login"
        element={!token ? <Login /> : <Navigate to="/" replace />}
      />

      {/* Регистрация */}
      <Route
        path="/register"
        element={!token ? <Register /> : <Navigate to="/" replace />}
      />

    </Routes>
  );
}

export default App;
