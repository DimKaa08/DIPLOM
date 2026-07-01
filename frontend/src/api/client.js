// frontend/src/api/client.js
import axios from "axios";

// Vite подставляет значение из .env при сборке.
// Если переменная не задана — fallback на localhost для разработки.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const client = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

// Интерцептор запросов: автоматически добавляет токен к каждому запросу.
// Теперь не нужно передавать token как параметр в каждую API-функцию.
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Интерцептор ответов: глобальная обработка 401.
// Если токен протух — разлогиниваем пользователя автоматически.
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// Базовый URL как строка — нужен для stream URL в <audio src="...">
export const API_BASE = API_URL;

export default client;