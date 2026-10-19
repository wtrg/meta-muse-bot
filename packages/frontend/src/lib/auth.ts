import { apiKeyClient } from "@better-auth/api-key/client";
import { adminClient } from "better-auth/client/plugins";
import {
  organizationClient,
  twoFactorClient,
} from "better-auth/client/plugins";
import { createAuthClient } from "better-auth/react";

const resolveAuthBaseURL = () => {
  const envUrl = import.meta.env.VITE_AUTH_BASE_URL;
  if (envUrl && (envUrl.startsWith("http://") || envUrl.startsWith("https://"))) {
    return envUrl;
  }
  if (typeof window !== "undefined") {
    const path = envUrl ? (envUrl.startsWith("/") ? envUrl : `/${envUrl}`) : "/api/auth";
    return `${window.location.origin}${path}`;
  }
  return "http://127.0.0.1:5173/api/auth";
};

export const authClient = createAuthClient({
  baseURL: resolveAuthBaseURL(),
  plugins: [
    apiKeyClient(),
    organizationClient(),
    twoFactorClient(),
    adminClient(),
  ],
});

export type AuthSession = typeof authClient.$Infer.Session;
export type AuthUser = AuthSession["user"];
