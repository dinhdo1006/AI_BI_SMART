export type ChartType =
  | "bar"
  | "pie"
  | "line"
  | "area"
  | "combo"
  | "candlestick"
  | "table";

export type ResponseStatus = "success" | "error" | "empty";

export type HistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

export type PeriodComparison = {
  metric: string;
  date_col?: string;
  mode: "MoM" | "QoQ" | "YoY" | "half_split" | string;
  previous_period: string;
  current_period: string;
  previous_mean: number;
  current_mean: number;
  pct_change: number | null;
  direction: "up" | "down" | "flat" | string;
};

export type ChatResponse = {
  status: ResponseStatus;
  domain_id: string;
  query: string;
  sql_query: string;
  data: Record<string, unknown>[];
  insight: string;
  row_count: number;
  chart_type: ChartType;
  viz_only?: boolean;
  from_cache?: boolean;
  column_labels?: Record<string, string>;
  failed_sql?: string | null;
  error_detail?: string | null;
  intent?: string | null;
  /** Nguồn SQL: fast_path | llm | repair | cache | … */
  sql_source?: string | null;
  /** Ngày mới nhất trong kết quả (YYYY-MM-DD) */
  data_as_of?: string | null;
  /** So sánh kỳ MoM/QoQ/YoY */
  period_comparison?: PeriodComparison | null;
  error?: string;
};

export type ArticleResponse = {
  article_markdown: string;
  outline: Record<string, unknown>;
  word_count: number;
  sections_written?: number;
  domain_id: string;
  question: string;
  chart_image_embedded?: boolean;
  /** Ảnh chart chỉ lưu client-side — không gửi API (tránh 500 body lớn) */
  chart_preview_base64?: string | null;
  error?: string;
};

export type DashboardReport = {
  query: string;
  insight?: string;
  data: Record<string, unknown>[];
  chart_type: ChartType;
  column_labels?: Record<string, string>;
  chart_image_base64?: string;
  article_markdown?: string;
};

export type DashboardPayload = {
  id: string;
  title: string;
  domain_id: string;
  created_at: string;
  reports: DashboardReport[];
};

export type DomainItem = { id: string; name: string };

export type DomainExploreColumn = {
  name: string;
  label: string;
  description: string;
};

export type DomainExploreTable = {
  name: string;
  description: string;
  columns: DomainExploreColumn[];
};

export type DomainExplore = {
  domain_id: string;
  domain_name: string;
  table_count: number;
  tables: DomainExploreTable[];
  sample_questions: string[];
};

export type DomainsHealth = {
  schema_rag_enabled?: boolean;
  domains: Record<
    string,
    { db_ok?: boolean; dialect?: string; detail?: string }
  >;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  payload?: ChatResponse;
  article?: ArticleResponse | null;
  /** Feedback đã gửi: up | down */
  feedback?: "up" | "down" | null;
};
