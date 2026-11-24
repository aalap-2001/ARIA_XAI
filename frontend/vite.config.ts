import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const api = "http://127.0.0.1:8700";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5190,
    proxy: { "/api": api, "/v1": api, "/widget.js": api, "/healthz": api },
  },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 900 },
});
