export type ChartType =
  | "bar"
  | "pie"
  | "line"
  | "area"
  | "combo"
  | "candlestick"
  | "heatmap"
  | "scatter"
  | "treemap"
  | "radar"
  | "waterfall"
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

export type ForecastPoint = {
  date: string;
  value: number;
};

export type Forecast = {
  metric: string;
  metric_label?: string;
  date_col?: string;
  date_col_label?: string;
  method?: string;
  lookback_points?: number;
  horizon: number;
  direction: "up" | "down" | "flat" | string;
  slope?: number;
  history_end_date?: string;
  history_end_value?: number;
  pct_change_to_horizon?: number | null;
  points: ForecastPoint[];
  disclaimer?: string;
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
  /** exact | semantic — cách khớp cache (nếu from_cache) */
  cache_match?: "exact" | "semantic" | string;
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
  /** Dự báo tuyến tính ngắn hạn */
  forecast?: Forecast | null;
  /** Template CP khớp câu hỏi (Tier 4) */
  chart_template?: {
    id: string;
    name: string;
    chart_type: ChartType;
    shape?: string;
    description?: string;
  } | null;
  /** Metadata tin cậy: nguồn giá, shape notes… */
  trust_meta?: {
    sql_source?: string | null;
    chart_template?: string | null;
    chart_template_name?: string | null;
    shape_kind?: string | null;
    shape_notes?: string[];
    price_sources?: string[];
    has_price_source?: boolean;
  } | null;
  shape_notes?: string[];
  error?: string;
};

export type ArticleFactCheck = {
  ok: boolean;
  checked: number;
  matched: number;
  unmatched?: {
    raw: string;
    value: number;
    unit?: string;
    context?: string;
  }[];
  warnings?: string[];
  source_count?: number;
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
  template_id?: string;
  template_name?: string;
  generated_at?: string;
  fact_check?: ArticleFactCheck | null;
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
  period_comparison?: PeriodComparison | null;
  forecast?: Forecast | null;
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

export type AlertOperator = "gt" | "gte" | "lt" | "lte" | "eq";

export type AlertMetric = {
  key: string;
  label: string;
  unit: string;
  needs_target: boolean;
  target_label: string;
  target_placeholder?: string;
  description?: string;
  kind?: "threshold" | "anomaly" | string;
  default_threshold?: number | null;
  default_operator?: AlertOperator;
};

export type AlertRule = {
  id: string;
  domain_id: string;
  name: string;
  metric_key: string;
  operator: AlertOperator;
  threshold: number;
  target: string | null;
  enabled: boolean;
  created_at: string;
  last_checked_at?: string | null;
  last_value?: number | null;
  last_triggered?: boolean;
};

export type AlertEvent = {
  id: string;
  rule_id: string;
  rule_name: string;
  domain_id: string;
  triggered_at: string;
  value: number;
  message: string;
  metric_key: string;
  operator: string;
  threshold: number;
  target: string | null;
};

export type AlertRunResult = {
  checked: number;
  triggered_count: number;
  new_event_count?: number;
  error_count: number;
  results: Array<{
    rule_id: string;
    rule_name?: string;
    status: string;
    triggered: boolean;
    message?: string;
    new_event?: boolean;
  }>;
};

export type AlertSchedulerStatus = {
  enabled: boolean;
  interval_minutes: number;
  running: boolean;
  last_run_at?: string | null;
  last_result?: {
    checked: number;
    triggered_count: number;
    new_event_count?: number;
    error_count: number;
  } | null;
  last_error?: string | null;
  thread_alive?: boolean;
};

export type AutoArticle = {
  id: string;
  template_id: string;
  template_name: string;
  data_date: string;
  domain_id: string;
  question: string;
  trigger: string;
  article_markdown: string;
  word_count: number;
  generated_at: string;
  created_at?: string;
  outline?: Record<string, unknown>;
};

export type AutoArticleNotifyStatus = {
  enabled: boolean;
  channels: string[];
  triggers?: string[] | null;
};

export type AutoArticleSchedulerStatus = {
  enabled: boolean;
  interval_minutes: number;
  running: boolean;
  daily_enabled?: boolean;
  weekly_enabled?: boolean;
  /** true = viết lại khi fingerprint DB đổi trong cùng ngày/kỳ */
  intraday_enabled?: boolean;
  daily_time?: string;
  weekly_time?: string;
  last_run_at?: string | null;
  last_result?: {
    checked: number;
    ok_count: number;
    skipped_count: number;
    error_count: number;
  } | null;
  last_error?: string | null;
  thread_alive?: boolean;
  notify?: AutoArticleNotifyStatus;
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
