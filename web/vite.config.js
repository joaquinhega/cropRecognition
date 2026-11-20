import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    watch: { usePolling: true },
    proxy: {
      "/api": {
        target: process.env.API_URL,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/raster": {
        target: process.env.RASTER_URL,
        rewrite: (path) => path.replace(/^\/raster/, ""),
      },
    },
  },
});
