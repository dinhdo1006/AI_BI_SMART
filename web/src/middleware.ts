import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Auth proxy:
 * - Nếu browser đã gửi X-API-Key / Authorization (sau login tenant) → giữ nguyên.
 * - Không thì inject BACKEND_API_KEY / API_KEY từ server env.
 */
export function middleware(request: NextRequest) {
  if (!request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  const incomingKey = (
    request.headers.get("x-api-key") ||
    (request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "") ||
    ""
  ).trim();

  const serverKey = (
    process.env.BACKEND_API_KEY ||
    process.env.API_KEY ||
    ""
  ).trim();

  if (incomingKey || !serverKey) {
    return NextResponse.next();
  }

  const headers = new Headers(request.headers);
  headers.set("X-API-Key", serverKey);
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: ["/api/:path*"],
};
