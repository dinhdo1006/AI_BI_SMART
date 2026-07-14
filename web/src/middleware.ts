import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Inject API key vào request tới /api/* trước khi rewrite sang FastAPI.
 * Key chỉ ở server env (BACKEND_API_KEY hoặc API_KEY) — không lộ ra browser.
 */
export function middleware(request: NextRequest) {
  const apiKey = (
    process.env.BACKEND_API_KEY ||
    process.env.API_KEY ||
    ""
  ).trim();

  if (!apiKey || !request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  const headers = new Headers(request.headers);
  headers.set("X-API-Key", apiKey);
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: ["/api/:path*"],
};
