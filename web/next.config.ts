import type { NextConfig } from "next";

/** Backend FastAPI — chỉ dùng phía server (rewrite), không lộ ra browser. */
const BACKEND_URL = (
  process.env.BACKEND_URL ||
  process.env.API_BASE ||
  "http://127.0.0.1:2004"
).replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${BACKEND_URL}/health`,
      },
    ];
  },
};

export default nextConfig;
