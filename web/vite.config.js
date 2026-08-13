import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const BACKEND = "http://127.0.0.1:1221";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 1991,
    strictPort: true,
    // Backend boshqa portda — /api va /a/{token} shu yerga yo'naltiriladi.
    // MUHIM: "/a/" (slash bilan) — "/a" bo'lsa Vite buni prefiks sifatida
    // moslashtirib, /admin va /artifacts kabi frontend route'larni ham
    // (ular ham "/a" bilan boshlanadi) noto'g'ri backend'ga proksi qilib,
    // eskirgan web/dist build'ini qaytarib yuborardi.
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
      "/a/": { target: BACKEND, changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
