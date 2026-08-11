import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// PWA First: offline shell now; offline inventory sync comes in Sprint 5.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "Grêmio do 2º CGEO",
        short_name: "Grêmio 2º CGEO",
        description: "Agenda e administração de patrimônio do Grêmio do 2º CGEO",
        theme_color: "#0f172a",
        background_color: "#0f172a",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "/logo_gremio.jpeg", sizes: "764x754", type: "image/jpeg", purpose: "any" },
        ],
      },
    }),
  ],
  server: {
    host: true,
    port: 5173,
    // Bind-mount no Docker/Windows não propaga eventos de FS: usa polling p/ HMR.
    watch: { usePolling: true },
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
