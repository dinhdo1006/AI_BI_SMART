import type {
  ArticleResponse,
  ChatResponse,
  DomainsHealth,
  DomainItem,
  HistoryMessage,
} from "./types";

/**
 * Mặc định: gọi cùng origin (`/api/...`) — Next.js rewrite tới FastAPI.
 * Chỉ set NEXT_PUBLIC_API_BASE khi muốn gọi API trực tiếp (bỏ qua proxy).
 */
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/$/, "");

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

export async function postChat(params: {
  domainId: string;
  query: string;
  history: HistoryMessage[];
  reuseData?: Record<string, unknown>[] | null;
}): Promise<ChatResponse> {
  const res = await fetch(apiUrl("/api/v1/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      domain_id: params.domainId,
      query: params.query,
      history: params.history,
      reuse_data: params.reuseData ?? null,
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

export async function postArticle(params: {
  domainId: string;
  question: string;
  data: Record<string, unknown>[];
  insightSummary?: string;
}): Promise<ArticleResponse> {
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
    return {
      article_markdown: "",
      outline: {},
      word_count: 0,
      domain_id: params.domainId,
      question: params.question,
      error: await parseError(res),
    };
  }
  return (await res.json()) as ArticleResponse;
}

export { API_BASE };
