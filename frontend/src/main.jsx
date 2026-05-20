import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./App.css";

import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext.jsx";
import { PlayerProvider } from "./context/PlayerContext.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AuthProvider>
      <PlayerProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </PlayerProvider>
    </AuthProvider>
  </React.StrictMode>
);
