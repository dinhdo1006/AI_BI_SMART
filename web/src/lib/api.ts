import type {
  ArticleResponse,
  ChatResponse,
  DashboardPayload,
  DomainExplore,
  DomainsHealth,
  DomainItem,
  HistoryMessage,
} from "./types";

/**
 * Mặc định: gọi cùng origin (`/api/...`) — Next.js rewrite tới FastAPI.
 * Chỉ set NEXT_PUBLIC_API_BASE khi muốn gọi API trực tiếp (bỏ qua proxy).
 */
export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "").replace(
  /\/$/,
  "",
);

function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${p}`;
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail
        .map((d: { msg?: string }) => d.msg || JSON.stringify(d))
        .join("; ");
    }
    return JSON.stringify(data);
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

export async function fetchDomains(): Promise<DomainItem[]> {
  try {
    const res = await fetch(apiUrl("/api/v1/domains"), { cache: "no-store" });
    if (!res.ok) throw new Error(await parseError(res));
    const data = await res.json();
    return (data.domains || []) as DomainItem[];
  } catch {
    return [
      { id: "finance_vnfdata", name: "VNFDATA — Tài chính" },
      { id: "it_deployment", name: "IT Deployment & FSI" },
      { id: "mining_geology", name: "Mining & Geology" },
    ];
  }
}

export async function fetchDomainsHealth(): Promise<DomainsHealth | null> {
  try {
    const res = await fetch(apiUrl("/api/v1/health/domains"), {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as DomainsHealth;
  } catch {
    return null;
  }
}

export async function fetchDomainExplore(
  domainId: string,
): Promise<DomainExplore | null> {
  try {
    const res = await fetch(
      apiUrl(`/api/v1/domains/${encodeURIComponent(domainId)}/explore`),
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    return (await res.json()) as DomainExplore;
  } catch {
    return null;
  }
}

export async function postChat(params: {
  domainId: string;
  query: string;
  history: HistoryMessage[];
  reuseData?: Record<string, unknown>[] | null;
  previousInsight?: string;
}): Promise<ChatResponse> {
  const res = await fetch(apiUrl("/api/v1/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      domain_id: params.domainId,
      query: params.query,
      history: params.history,
      reuse_data: params.reuseData ?? null,
      previous_insight: params.previousInsight || "",
    }),
  });
  if (!res.ok) {
    const err = await parseError(res);
    return {
      status: "error",
      domain_id: params.domainId,
      query: params.query,
      sql_query: "",
      data: [],
      insight: "",
      row_count: 0,
      chart_type: "table",
      error: err,
      error_detail: err,
    };
  }
  return (await res.json()) as ChatResponse;
}

/** SSE streaming chat — gọi onProgress khi có bước, trả ChatResponse cuối. */
export async function postChatStream(params: {
  domainId: string;
  query: string;
  history: HistoryMessage[];
  reuseData?: Record<string, unknown>[] | null;
  previousInsight?: string;
  onProgress?: (step: string) => void;
}): Promise<ChatResponse> {
  try {
    const res = await fetch(apiUrl("/api/v1/chat/stream"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({
        domain_id: params.domainId,
        query: params.query,
        history: params.history,
        reuse_data: params.reuseData ?? null,
        previous_insight: params.previousInsight || "",
      }),
    });

    if (!res.ok || !res.body) {
      // Fallback non-stream
      return postChat(params);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let result: ChatResponse | null = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) {
        const line = part
          .split("\n")
          .find((l) => l.startsWith("data: "));
        if (!line) continue;
        try {
          const json = JSON.parse(line.slice(6)) as {
            event: string;
            step?: string;
            data?: ChatResponse;
          };
          if (json.event === "progress" && json.step) {
            params.onProgress?.(json.step);
          } else if (json.event === "result" && json.data) {
            result = json.data;
          } else if (json.event === "error") {
            return {
              status: "error",
              domain_id: params.domainId,
              query: params.query,
              sql_query: "",
              data: [],
              insight: "",
              row_count: 0,
              chart_type: "table",
              error: json.step || "Lỗi stream",
              error_detail: json.step || "Lỗi stream",
            };
          }
        } catch {
          /* ignore bad chunk */
        }
      }
    }

    return result || postChat(params);
  } catch {
    return postChat(params);
  }
}

export async function postArticle(params: {
  domainId: string;
  question: string;
  data: Record<string, unknown>[];
  insightSummary?: string;
  onProgress?: (step: string) => void;
}): Promise<ArticleResponse> {
  // Ưu tiên SSE để hiện progress; fallback POST cũ nếu stream lỗi
  try {
    const streamed = await postArticleStream(params);
    if (streamed) return streamed;
  } catch {
    /* fallback below */
  }

  const res = await fetch(apiUrl("/api/v1/generate_article"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      domain_id: params.domainId,
      question: params.question,
      data: params.data,
      insight_summary: params.insightSummary || "",
    }),
  });
  if (!res.ok) {
    const detail = await parseError(res);
    return {
      article_markdown: "",
      outline: {},
      word_count: 0,
      domain_id: params.domainId,
      question: params.question,
      error:
        detail ||
        (res.status === 502 || res.status === 504
          ? "Ollama timeout hoặc chưa chạy — kiểm tra model (INSIGHT_MODEL, vd. qwen2.5:14b)"
          : res.status === 500
            ? "Proxy/server lỗi khi viết bài (thường do timeout). Thử lại hoặc restart Next.js sau khi cập nhật."
            : `HTTP ${res.status} ${res.statusText}`),
    };
  }
  return (await res.json()) as ArticleResponse;
}

/** SSE viết bài — hiện progress từ backend. */
async function postArticleStream(params: {
  domainId: string;
  question: string;
  data: Record<string, unknown>[];
  insightSummary?: string;
  onProgress?: (step: string) => void;
}): Promise<ArticleResponse | null> {
  const res = await fetch(apiUrl("/api/v1/generate_article/stream"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      domain_id: params.domainId,
      question: params.question,
      data: params.data,
      insight_summary: params.insightSummary || "",
    }),
  });

  if (!res.ok || !res.body) return null;

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: ArticleResponse | null = null;
  let streamError: string | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const line = part.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        const json = JSON.parse(line.slice(6)) as {
          event: string;
          step?: string;
          data?: ArticleResponse;
        };
        if (json.event === "progress" && json.step) {
          params.onProgress?.(json.step);
        } else if (json.event === "result" && json.data) {
          result = json.data;
        } else if (json.event === "error") {
          streamError = json.step || "Lỗi stream viết bài";
        }
      } catch {
        /* ignore bad chunk */
      }
    }
  }

  if (streamError) {
    return {
      article_markdown: "",
      outline: {},
      word_count: 0,
      domain_id: params.domainId,
      question: params.question,
      error: streamError,
    };
  }
  return result;
}

export async function exportWord(params: {
  domainId: string;
  query: string;
  insight: string;
  data: Record<string, unknown>[];
  articleMarkdown?: string;
  chartImageBase64?: string;
}): Promise<void> {
  const res = await fetch(apiUrl("/api/v1/export/word"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      domain_id: params.domainId,
      query: params.query,
      insight: params.insight,
      data: params.data,
      article_markdown: params.articleMarkdown || "",
      chart_image_base64: params.chartImageBase64 || null,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "bao-cao-bi.docx";
  a.click();
  URL.revokeObjectURL(url);
}

export async function saveDashboard(params: {
  title: string;
  domainId: string;
  reports: DashboardPayload["reports"];
}): Promise<{ id: string }> {
  const res = await fetch(apiUrl("/api/v1/dashboards"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: params.title,
      domain_id: params.domainId,
      reports: params.reports,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as { id: string };
}

export async function fetchDashboard(
  id: string,
): Promise<DashboardPayload | null> {
  try {
    const res = await fetch(apiUrl(`/api/v1/dashboards/${id}`), {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as DashboardPayload;
  } catch {
    return null;
  }
}

export async function postFeedback(params: {
  domainId: string;
  query: string;
  vote: "up" | "down";
  sqlQuery?: string;
  sqlSource?: string | null;
  status?: string | null;
}): Promise<boolean> {
  try {
    const res = await fetch(apiUrl("/api/v1/feedback"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domain_id: params.domainId,
        query: params.query,
        vote: params.vote,
        sql_query: params.sqlQuery || "",
        sql_source: params.sqlSource ?? null,
        status: params.status ?? null,
      }),
    });
    return res.ok;
  } catch {
    return false;
  }
}
