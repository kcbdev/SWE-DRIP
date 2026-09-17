import type { NextConfig } from "next";

/**
 * Dev-only API proxy for same-origin asset URLs (PBI-057).
 *
 * `<img>` tags use relative `/api/…` URLs (the QC render pattern — in
 * production Traefik routes them to the API service). The panel dev server
 * has no such routes, so images 404 locally. In development only, proxy the
 * data prefixes to the local API; `/api/auth/*` (Better Auth handlers) and
 * `/api/dev/*` (panel-local) are deliberately excluded. Production builds
 * (`NODE_ENV=production`) get no rewrites — empty, verified by build.
 */
const DEV_API_PREFIXES = [
  "agents",
  "analytics",
  "approvals",
  "audit",
  "catalog",
  "collections",
  "dashboard",
  "designs",
  "me",
  "operator-tokens",
  "research",
  "runs",
  "settings",
  "stream",
  "styles",
  "users",
  "webhooks",
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    const target = process.env.API_DEV_ORIGIN ?? "http://127.0.0.1:8001";
    return DEV_API_PREFIXES.map((prefix) => ({
      source: `/api/${prefix}/:path*`,
      destination: `${target}/api/${prefix}/:path*`,
    }));
  },
};

export default nextConfig;
