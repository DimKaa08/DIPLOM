import { createContext, useState, useEffect } from "react";

export const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);

  // Загружаем токен при старте
  useEffect(() => {
    const savedToken = localStorage.getItem("token");
    const savedUser = localStorage.getItem("user");

    if (savedToken) setToken(savedToken);
    if (savedUser) setUser(JSON.parse(savedUser));
  }, []);

  const saveToken = (token) => {
    localStorage.setItem("token", token);
    setToken(token);
  };

  const saveUser = (user) => {
    localStorage.setItem("user", JSON.stringify(user));
    setUser(user);
  };

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setToken(null);
    setUser(null);
  };


  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        setToken: saveToken,
        setUser: saveUser,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
