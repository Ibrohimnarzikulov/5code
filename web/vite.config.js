import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const BACKEND = "http://127.0.0.1:1221";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 1991,
    strictPort: true,
    // Backend boshqa portda — /api va /a shu yerga yo'naltiriladi
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
      "/a": { target: BACKEND, changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
