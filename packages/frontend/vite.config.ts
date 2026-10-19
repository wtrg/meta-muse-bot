import path from "path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, import.meta.dirname, "");
  const backendProxyTarget =
    env.BACKEND_PROXY_TARGET ?? "http://127.0.0.1:8787";

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(import.meta.dirname, "./src"),
      },
    },
    server: {
      allowedHosts: true,
      fs: {
        allow: [
          path.resolve(import.meta.dirname),
          path.resolve(import.meta.dirname, "../contracts"),
          path.resolve(import.meta.dirname, "../../node_modules"),
        ],
        deny: ["**/.env", "**/.env.*", "**/.dev.vars", "**/*.{crt,pem}", "**/.git/**", "**/scripts/**", "**/muse_accounts.txt", "**/muse_session*.csv", "**/muse_session*.xlsx", "**/bin/**"],
      },
      proxy: {
        "/api/bot": {
          target: env.BOT_PROXY_TARGET ?? "http://127.0.0.1:8790",
          changeOrigin: true,
          // Public OTP tunnels must not expose local bot controls or sessions.
          bypass(req) {
            try {
              const host = new URL(`http://${req.headers.host ?? ""}`).hostname;
              if (!["127.0.0.1", "localhost", "[::1]"].includes(host)) return false;
            } catch {
              return false;
            }
          },
        },
        "/api": {
          target: backendProxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
