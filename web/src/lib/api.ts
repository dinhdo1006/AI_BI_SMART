import type {
  AlertEvent,
  AlertMetric,
  AlertOperator,
  AlertRule,
  AlertRunResult,
  AlertSchedulerStatus,
  ArticleResponse,
  AutoArticle,
  AutoArticleSchedulerStatus,
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

/** Gắn X-API-Key từ localStorage (sau login tenant) nếu có. */
export async function apiFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const headers = new Headers(init?.headers || {});
  if (typeof window !== "undefined") {
    const key = window.localStorage.getItem("abi_api_key");
    if (
      key &&
      !headers.has("X-API-Key") &&
      !headers.has("Authorization")
    ) {
      headers.set("X-API-Key", key);
    }
  }
  return fetch(apiUrl(path), { ...init, headers });
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
    const res = await apiFetch("/api/v1/domains", { cache: "no-store" });
    if (!res.ok) throw new Error(await parseError(res));
    const data = await res.json();
    return (data.domains || []) as DomainItem[];
  } catch {
    return [{ id: "finance_vnfdata", name: "VNFDATA — Tài chính" }];
  }
}

export async function fetchDomainsHealth(): Promise<DomainsHealth | null> {
  try {
    const res = await apiFetch("/api/v1/health/domains", {
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

export async function postUploadAnalyze(params: {
  domainId: string;
  question: string;
  file: File;
}): Promise<ChatResponse> {
  const body = new FormData();
  body.append("domain_id", params.domainId);
  body.append("question", params.question || "");
  body.append("file", params.file);

  const res = await apiFetch("/api/v1/analyze_upload", {
    method: "POST",
    body,
  });
  if (!res.ok) {
    const err = await parseError(res);
    return {
      status: "error",
      domain_id: params.domainId,
      query: params.question || params.file.name,
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

export async function fetchTenantBranding(): Promise<{
  tenant_id?: string | null;
  tenant_name?: string;
  branding: {
    product_name?: string;
    primary_color?: string;
    logo_url?: string;
  };
} | null> {
  try {
    const res = await apiFetch("/api/v1/tenant/branding", {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as {
      tenant_id?: string | null;
      tenant_name?: string;
      branding: {
        product_name?: string;
        primary_color?: string;
        logo_url?: string;
      };
    };
  } catch {
    return null;
  }
}

export async function postLogin(params: {
  email: string;
  password: string;
}): Promise<{
  ok: boolean;
  api_key?: string;
  role?: string;
  error?: string;
  tenant?: { id?: string; name?: string; branding?: Record<string, string> };
}> {
  try {
    const res = await apiFetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!res.ok) {
      return { ok: false, error: await parseError(res) };
    }
    return (await res.json()) as {
      ok: boolean;
      api_key?: string;
      role?: string;
      tenant?: { id?: string; name?: string; branding?: Record<string, string> };
    };
  } catch (e) {
    return {
      ok: false,
      error: e instanceof Error ? e.message : "Login failed",
    };
  }
}

export async function postChat(params: {
  domainId: string;
  query: string;
  history: HistoryMessage[];
  reuseData?: Record<string, unknown>[] | null;
  previousInsight?: string;
}): Promise<ChatResponse> {
  const res = await apiFetch("/api/v1/chat", {
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
    const res = await apiFetch("/api/v1/chat/stream", {
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
  sqlSource?: string | null;
  artifactId?: string | null;
  onProgress?: (step: string) => void;
}): Promise<ArticleResponse> {
  // Ưu tiên SSE để hiện progress; fallback POST cũ nếu stream lỗi
  try {
    const streamed = await postArticleStream(params);
    if (streamed) return streamed;
  } catch {
    /* fallback below */
  }

  const res = await apiFetch("/api/v1/generate_article", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      domain_id: params.domainId,
      question: params.question,
      data: params.data,
      insight_summary: params.insightSummary || "",
      sql_source: params.sqlSource ?? null,
      artifact_id: params.artifactId ?? null,
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

export async function reviseArticle(params: {
  domainId: string;
  question: string;
  articleMarkdown: string;
  instruction: string;
  insightSummary?: string;
  data?: Record<string, unknown>[];
  sqlSource?: string | null;
  artifactId?: string | null;
}): Promise<ArticleResponse> {
  const res = await apiFetch("/api/v1/revise_article", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      domain_id: params.domainId,
      question: params.question,
      article_markdown: params.articleMarkdown,
      instruction: params.instruction,
      insight_summary: params.insightSummary || "",
      data: params.data || [],
      sql_source: params.sqlSource ?? null,
      artifact_id: params.artifactId ?? null,
    }),
  });
  if (!res.ok) {
    const detail = await parseError(res);
    return {
      article_markdown: params.articleMarkdown,
      outline: {},
      word_count: params.articleMarkdown.split(/\s+/).filter(Boolean).length,
      domain_id: params.domainId,
      question: params.question,
      error:
        detail ||
        (res.status === 502 || res.status === 504
          ? "Ollama timeout hoặc chưa chạy — kiểm tra model INSIGHT_MODEL"
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
  sqlSource?: string | null;
  artifactId?: string | null;
  onProgress?: (step: string) => void;
}): Promise<ArticleResponse | null> {
  const res = await apiFetch("/api/v1/generate_article/stream", {
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
      sql_source: params.sqlSource ?? null,
      artifact_id: params.artifactId ?? null,
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
  const res = await apiFetch("/api/v1/export/word", {
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

export async function exportPptx(params: {
  title?: string;
  domainId: string;
  reports: Array<{
    query: string;
    insight?: string;
    data?: Record<string, unknown>[];
  }>;
}): Promise<void> {
  const res = await apiFetch("/api/v1/export/pptx", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: params.title || "Báo cáo BI",
      domain_id: params.domainId,
      reports: params.reports,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "bao-cao-bi.pptx";
  a.click();
  URL.revokeObjectURL(url);
}

export async function exportPdf(params: {
  title?: string;
  domainId: string;
  reports: Array<{
    query: string;
    insight?: string;
    data?: Record<string, unknown>[];
  }>;
}): Promise<void> {
  const res = await apiFetch("/api/v1/export/pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: params.title || "Báo cáo BI",
      domain_id: params.domainId,
      reports: params.reports,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const cd = res.headers.get("content-disposition") || "";
  const fname = cd.includes(".html") ? "bao-cao-bi.html" : "bao-cao-bi.pdf";
  a.download = fname;
  a.click();
  URL.revokeObjectURL(url);
}

export async function saveDashboard(params: {
  title: string;
  domainId: string;
  reports: DashboardPayload["reports"];
  isPublic?: boolean;
}): Promise<{ id: string; is_public?: boolean }> {
  const res = await apiFetch("/api/v1/dashboards", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: params.title,
      domain_id: params.domainId,
      reports: params.reports,
      is_public: params.isPublic ?? false,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as { id: string; is_public?: boolean };
}

export type DashboardListItem = {
  id: string;
  title: string;
  domain_id: string;
  created_at: string;
  is_public: boolean;
  report_count: number;
};

export async function fetchDashboards(
  domainId?: string,
): Promise<DashboardListItem[]> {
  const q = domainId
    ? `?domain_id=${encodeURIComponent(domainId)}`
    : "";
  try {
    const res = await apiFetch(`/api/v1/dashboards${q}`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = (await res.json()) as { dashboards?: DashboardListItem[] };
    return data.dashboards || [];
  } catch {
    return [];
  }
}

export async function deleteDashboard(id: string): Promise<boolean> {
  try {
    const res = await apiFetch(`/api/v1/dashboards/${id}`, { method: "DELETE" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function setDashboardPublic(
  id: string,
  isPublic: boolean,
): Promise<{ id: string; is_public: boolean }> {
  const res = await apiFetch(`/api/v1/dashboards/${id}/public`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_public: isPublic }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as { id: string; is_public: boolean };
}

export async function fetchDashboard(
  id: string,
): Promise<DashboardPayload | null> {
  try {
    const res = await apiFetch(`/api/v1/dashboards/${id}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as DashboardPayload;
  } catch {
    return null;
  }
}

export async function fetchMonitoringMetrics(
  hours = 24,
  domainId?: string,
): Promise<{
  total_requests: number;
  hours: number;
  success_rate: number;
  error_rate: number;
  cache_hit_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  sql_source_breakdown: Record<string, number>;
  intent_breakdown: Record<string, number>;
  requests_by_hour: Record<string, number>;
  top_queries: Array<{ query: string; count: number }>;
} | null> {
  try {
    const q = new URLSearchParams({ hours: String(hours) });
    if (domainId) q.set("domain_id", domainId);
    const res = await apiFetch(`/api/v1/monitoring/metrics?${q}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchDataQuality(
  domainId = "finance_vnfdata",
): Promise<{
  last_checked: string | null;
  summary: Record<string, number>;
  top_divergent_tickers: Array<{
    ticker: string;
    company_name: string;
    days_divergent: number;
    avg_diff_pct: number | null;
    max_diff_pct: number | null;
    latest_date: string;
  }>;
  divergent_by_date: Array<{
    trade_date: string;
    divergent_count: number;
    max_diff_pct: number | null;
  }>;
} | null> {
  try {
    const res = await apiFetch(
      `/api/v1/data-quality?domain_id=${encodeURIComponent(domainId)}`,
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    return await res.json();
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
  artifactId?: string | null;
}): Promise<boolean> {
  try {
    const res = await apiFetch("/api/v1/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domain_id: params.domainId,
        query: params.query,
        vote: params.vote,
        sql_query: params.sqlQuery || "",
        sql_source: params.sqlSource ?? null,
        status: params.status ?? null,
        artifact_id: params.artifactId ?? null,
      }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function fetchAlertMetrics(
  domainId: string,
): Promise<AlertMetric[]> {
  const res = await fetch(
    apiUrl(`/api/v1/alerts/metrics?domain_id=${encodeURIComponent(domainId)}`),
    { cache: "no-store" },
  );
  if (!res.ok) return [];
  const data = await res.json();
  return (data.metrics || []) as AlertMetric[];
}

export async function fetchAlertRules(
  domainId: string,
): Promise<AlertRule[]> {
  const res = await fetch(
    apiUrl(`/api/v1/alerts/rules?domain_id=${encodeURIComponent(domainId)}`),
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  return (data.rules || []) as AlertRule[];
}

export async function createAlertRule(params: {
  domainId: string;
  name: string;
  metricKey: string;
  operator: AlertOperator;
  threshold: number;
  target?: string;
}): Promise<AlertRule> {
  const res = await apiFetch("/api/v1/alerts/rules", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      domain_id: params.domainId,
      name: params.name,
      metric_key: params.metricKey,
      operator: params.operator,
      threshold: params.threshold,
      target: params.target || null,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as AlertRule;
}

export async function patchAlertRule(
  ruleId: string,
  body: { enabled?: boolean; name?: string; threshold?: number },
): Promise<AlertRule> {
  const res = await apiFetch(`/api/v1/alerts/rules/${ruleId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as AlertRule;
}

export async function deleteAlertRule(ruleId: string): Promise<boolean> {
  const res = await apiFetch(`/api/v1/alerts/rules/${ruleId}`, {
    method: "DELETE",
  });
  return res.ok;
}

export async function runAlerts(
  domainId?: string,
): Promise<AlertRunResult> {
  const q = domainId
    ? `?domain_id=${encodeURIComponent(domainId)}`
    : "";
  const res = await apiFetch(`/api/v1/alerts/run${q}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as AlertRunResult;
}

export async function fetchAlertScheduler(): Promise<AlertSchedulerStatus | null> {
  try {
    const res = await apiFetch("/api/v1/alerts/scheduler", {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as AlertSchedulerStatus;
  } catch {
    return null;
  }
}

export async function fetchAlertEvents(
  domainId?: string | null,
  limit = 20,
): Promise<AlertEvent[]> {
  const q = new URLSearchParams();
  if (domainId) q.set("domain_id", domainId);
  q.set("limit", String(limit));
  try {
    const res = await apiFetch(`/api/v1/alerts/events?${q}`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.events || []) as AlertEvent[];
  } catch {
    return [];
  }
}

export async function fetchAutoArticles(
  domainId?: string,
  limit = 20,
): Promise<AutoArticle[]> {
  const q = new URLSearchParams();
  if (domainId) q.set("domain_id", domainId);
  q.set("limit", String(limit));
  try {
    const res = await apiFetch(`/api/v1/auto_articles?${q}`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.articles || []) as AutoArticle[];
  } catch {
    return [];
  }
}

export async function fetchAutoArticle(
  articleId: string,
): Promise<AutoArticle | null> {
  try {
    const res = await fetch(
      apiUrl(`/api/v1/auto_articles/${encodeURIComponent(articleId)}`),
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    return (await res.json()) as AutoArticle;
  } catch {
    return null;
  }
}

export async function fetchAutoArticleScheduler(): Promise<AutoArticleSchedulerStatus | null> {
  try {
    const res = await apiFetch("/api/v1/auto_articles/scheduler", {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as AutoArticleSchedulerStatus;
  } catch {
    return null;
  }
}

export async function runAutoArticleChecks(): Promise<{
  checked: number;
  ok_count: number;
  skipped_count: number;
  error_count: number;
  jobs?: Array<Record<string, unknown>>;
}> {
  const res = await apiFetch("/api/v1/auto_articles/run_checks", {
    method: "POST",
  });
  if (!res.ok) throw new Error(await parseError(res));
  return await res.json();
}

export async function runAutoArticleJob(params: {
  templateId: string;
  dataDate: string;
  domainId?: string;
  force?: boolean;
}): Promise<{
  status: string;
  article?: AutoArticle;
  message?: string;
  notify?: {
    enabled?: boolean;
    skipped?: boolean;
    reason?: string;
    ok_count?: number;
    error_count?: number;
    results?: Array<{ channel: string; status: string; message?: string }>;
  };
}> {
  const res = await apiFetch("/api/v1/auto_articles/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      template_id: params.templateId,
      data_date: params.dataDate,
      domain_id: params.domainId || "finance_vnfdata",
      force: params.force ?? false,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return await res.json();
}
