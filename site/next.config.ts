import type { NextConfig } from "next";

// Production: plain HTML/CSS/JS in out/, served by the API Worker next to /api (docs/decisions.md,
// 2026-10-16). Development: Next refuses rewrites in export mode, so `next dev` runs as a normal
// app and forwards /api to the local FastAPI (scripts/dev_api.py), same as the old Vite proxy.
const dev = process.env.NODE_ENV === "development";
const API_DEV = process.env.KARIO_API_DEV ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  ...(dev
    ? { rewrites: async () => [{ source: "/api/:path*", destination: `${API_DEV}/api/:path*` }] }
    : { output: "export" as const }),
  // cacheComponents / partialPrefetching (template defaults) need a server; Next refuses them with export.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
