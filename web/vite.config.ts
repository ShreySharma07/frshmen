import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api goes to the local FastAPI (scripts/dev_api.py); in production the
// Worker serves both, so the page always calls same-origin /api.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
