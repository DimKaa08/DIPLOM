import { AuthProvider } from "./context/AuthContext";
import { PlayerProvider } from "./context/PlayerContext";
import Home from "./pages/Home";
import Login from "./pages/Login";

export default function App() {
  return (
    <AuthProvider>
      <PlayerProvider>
        <Home />
      </PlayerProvider>
    </AuthProvider>
  );
}
