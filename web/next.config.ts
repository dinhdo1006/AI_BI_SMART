import type { NextConfig } from "next";

/** Backend FastAPI — chỉ dùng phía server (rewrite), không lộ ra browser. */
const BACKEND_URL = (
  process.env.BACKEND_URL ||
  process.env.API_BASE ||
  "http://127.0.0.1:2004"
).replace(/\/$/, "");

const nextConfig: NextConfig = {
  // Rewrite proxy mặc định ~30–60s — tăng để LLM dài (Ollama) không bị 500.
  // generate_article còn có Route Handler riêng (timeout 5 phút) ưu tiên hơn rewrite.
  experimental: {
    // Unsupported in public types on some Next versions; still read at runtime.
    proxyTimeout: 300_000,
  } as NextConfig["experimental"],
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
