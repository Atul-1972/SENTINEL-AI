import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxy = {
    "/api": {
      target: env.SENTINEL_API_TARGET || "http://127.0.0.1:8001",
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ""),
    },
  };
  return {
    define: {
      __SENTINEL_API_TARGET__: JSON.stringify(
        env.SENTINEL_API_TARGET || "http://127.0.0.1:8001",
      ),
    },
    plugins: [react(), tailwindcss()],
    server: { proxy },
    preview: { proxy },
  };
});
