import { existsSync, readFileSync } from "fs";
import path from "path";
import type { NextConfig } from "next";

/** Load monorepo-root `.env` so LOOPFORGE_API_ORIGIN is shared with the Python backend. */
function loadRootEnv() {
  const candidates = [
    path.resolve(process.cwd(), "..", ".env"),
    path.resolve(process.cwd(), ".env"),
  ];
  for (const envPath of candidates) {
    if (!existsSync(envPath)) continue;
    for (const line of readFileSync(envPath, "utf8").split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eq = trimmed.indexOf("=");
      if (eq === -1) continue;
      const key = trimmed.slice(0, eq).trim();
      const value = trimmed.slice(eq + 1).trim();
      if (key && process.env[key] === undefined) {
        process.env[key] = value;
      }
    }
    break;
  }
}

loadRootEnv();

const API_ORIGIN = process.env.LOOPFORGE_API_ORIGIN || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_ORIGIN}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
