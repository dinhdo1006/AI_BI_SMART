import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy dài hạn cho luồng AI sửa bài.
 * LLM có thể mất 1-3 phút khi biên tập lại markdown dài.
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
    const upstream = await fetch(`${BACKEND_URL}/api/v1/revise_article`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      signal: controller.signal,
      cache: "no-store",
    });

    const text = await upstream.text();
    const contentType =
      upstream.headers.get("content-type") || "application/json";

    return new NextResponse(text, {
      status: upstream.status,
      headers: { "Content-Type": contentType },
    });
  } catch (err) {
    const aborted =
      err instanceof Error &&
      (err.name === "AbortError" || /aborted/i.test(err.message));
    return NextResponse.json(
      {
        detail: aborted
          ? "Sửa bài quá lâu (timeout 5 phút) — kiểm tra Ollama và model INSIGHT_MODEL"
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
