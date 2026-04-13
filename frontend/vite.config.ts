import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  envDir: path.resolve(__dirname, ".."),
  plugins: [
    react(),
  ],
  server: {
    host: "localhost",
    port: 5173,
    proxy: {
      // 127.0.0.1 avoids localhost → ::1 vs 127.0.0.1 mismatches with the API listener
      "/api": { target: "http://127.0.0.1:5050", changeOrigin: true, secure: false },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "client", "src"),
    },
  },
  root: path.resolve(__dirname, "client"),
  build: {
    outDir: path.resolve(__dirname, "dist"),
    emptyOutDir: true,
  },
});
