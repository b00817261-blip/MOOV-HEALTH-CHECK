import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vercel auto-detects Vite; no extra config needed there.
export default defineConfig({
  plugins: [react()],
});
