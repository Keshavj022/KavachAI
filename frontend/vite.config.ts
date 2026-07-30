import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on 5173 (matches FRONTEND_ORIGIN default in the backend CORS
// config). API/WS base URLs are read from VITE_* env at runtime.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
});
