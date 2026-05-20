import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,       // важно для Windows
    port: 5173,       // фиксируем порт
    strictPort: true, // если порт занят — покажет ошибку
  },
});
