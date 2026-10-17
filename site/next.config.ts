import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Plain HTML/CSS/JS in out/, served by the existing Worker next to /api (docs/decisions.md, 2026-10-16).
  output: "export",
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
