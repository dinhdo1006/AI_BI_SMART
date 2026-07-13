export type ChartType = "bar" | "pie" | "line" | "area" | "combo" | "table";

export type ResponseStatus = "success" | "error" | "empty";

export type HistoryMessage = {
  role: "user" | "assistant";
  content: string;
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
  error?: string;
};

export type ArticleResponse = {
  article_markdown: string;
  outline: Record<string, unknown>;
  word_count: number;
  sections_written?: number;
  domain_id: string;
  question: string;
  error?: string;
};

export type DomainItem = { id: string; name: string };

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
};
