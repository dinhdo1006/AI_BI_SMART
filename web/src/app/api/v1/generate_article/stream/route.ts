import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy SSE dài hạn cho Narrative Planner (progress + result).
 */
export const dynamic = "force-dynamic";
export const maxDuration = 300;

const BACKEND_URL = (
  process.env.BACKEND_URL ||
  process.env.API_BASE ||
  "http://127.0.0.1:2004"
).replace(/\/$/, "");

const ARTICLE_TIMEOUT_MS = 300_000;

export async function POST(req: NextRequest) {
  let body: string;
  try {
    body = await req.text();
  } catch {
    return NextResponse.json(
      { detail: "Không đọc được body request" },
      { status: 400 },
    );
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ARTICLE_TIMEOUT_MS);

  try {
    const upstream = await fetch(
      `${BACKEND_URL}/api/v1/generate_article/stream`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body,
        signal: controller.signal,
        cache: "no-store",
      },
    );

    if (!upstream.ok || !upstream.body) {
      const text = await upstream.text();
      return new NextResponse(text || upstream.statusText, {
        status: upstream.status || 502,
        headers: { "Content-Type": "application/json" },
      });
    }

    return new NextResponse(upstream.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (err) {
    const aborted =
      err instanceof Error &&
      (err.name === "AbortError" || /aborted/i.test(err.message));
    return NextResponse.json(
      {
        detail: aborted
          ? "Viết bài quá lâu (timeout 5 phút) — kiểm tra Ollama và model INSIGHT_MODEL"
          : `Không kết nối được backend FastAPI (${BACKEND_URL}): ${
              err instanceof Error ? err.message : String(err)
            }`,
      },
      { status: aborted ? 504 : 502 },
    );
  } finally {
    clearTimeout(timer);
  }
}
