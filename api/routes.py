"""FastAPI Router — endpoint Conversational BI."""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from core.config_loader import list_available_domains, load_domain_config
from core.dashboard_store import create_dashboard, get_dashboard
from core.db_dialect import detect_dialect, dialect_label
from core.db_executor import DbQueryError, execute_query
from core.domain_explorer import build_domain_explore
from core.insight_stats import compute_insight_stats
from core.llm_agent import generate_insight, generate_sql, repair_sql
from core.logger import log_chat_event, log_feedback
from core.narrative_planner import generate_article
from core.query_cache import get_cached_response, set_cached_response
from core.router import (
    INTENT_CHITCHAT,
    INTENT_FOLLOWUP,
    INTENT_OOS,
    INTENT_SQL,
    INTENT_VIZ,
    answer_chitchat,
    classify_intent,
    out_of_scope_message,
)
from core.schema_introspection import check_db_connection
from core.schema_rag import build_rag_schema_context, is_schema_rag_enabled
from core.sql_fast_path import try_fast_sql
from core.entity_resolver import resolve_query_entities
from core.few_shot_retriever import best_few_shot_sql
from core.viz_advisor import ChartType, is_viz_only_request, resolve_chart_type
from core.chart_templates import match_chart_template, template_to_dict
from core.sql_shape_validator import (
    build_trust_meta,
    normalize_rows_for_chart,
    validate_shape,
)
from utils.report_export import create_word_report_api

import json
import pandas as pd
import queue as queue_mod
import threading

router = APIRouter(prefix="/api/v1", tags=["chat"])

ResponseStatus = Literal["success", "error", "empty"]

_INSIGHT_QUERY_ERROR = (
    "Xin lỗi, tôi chưa hiểu rõ tiêu chí truy vấn hoặc dữ liệu này có cấu trúc phức tạp. "
    "Bạn có thể diễn đạt lại câu hỏi không?"
)
_INSIGHT_EMPTY_DATA = (
    "Hệ thống đã truy vấn thành công nhưng không tìm thấy dữ liệu nào khớp với yêu cầu của bạn "
    "(ví dụ: khoảng thời gian chưa có số liệu)."
)

# Cột ngày trong kết quả → suy ra data_as_of (không query DB thêm)
_DATE_COL_HINTS = ("ngay", "date", "time", "updated", "surveyed", "start")


def _client_ip(http_request: Request | None) -> str | None:
    if http_request is None:
        return None
    forwarded = http_request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    if http_request.client:
        return http_request.client.host
    return None


def _label_period(
    period: dict[str, Any] | None,
    labels: dict[str, str],
) -> dict[str, Any] | None:
    if not period:
        return None
    out = dict(period)
    metric = out.get("metric")
    date_col = out.get("date_col")
    if metric is not None:
        out["metric"] = labels.get(str(metric), metric)
    if date_col is not None:
        out["date_col"] = labels.get(str(date_col), date_col)
    return out


def _label_forecast(
    forecast: dict[str, Any] | None,
    labels: dict[str, str],
) -> dict[str, Any] | None:
    """Giữ metric/date_col gốc (khớp cột data); thêm nhãn hiển thị."""
    if not forecast:
        return None
    out = dict(forecast)
    metric = out.get("metric")
    date_col = out.get("date_col")
    if metric is not None:
        out["metric_label"] = labels.get(str(metric), metric)
    if date_col is not None:
        out["date_col_label"] = labels.get(str(date_col), date_col)
    return out


def _infer_data_as_of(rows: list[dict[str, Any]]) -> str | None:
    """Lấy ngày mới nhất trong kết quả (YYYY-MM-DD). Không có cột ngày → None."""
    if not rows:
        return None
    keys = [
        k
        for k in rows[0]
        if any(h in str(k).lower() for h in _DATE_COL_HINTS)
    ]
    if not keys:
        return None
    best: str | None = None
    for row in rows:
        for k in keys:
            raw = row.get(k)
            if raw is None:
                continue
            s = str(raw).strip()
            if len(s) < 10 or s[4] != "-":
                continue
            day = s[:10]
            if best is None or day > best:
                best = day
    return best


def _shape_hint_for_sql(domain_id: str, query: str) -> str | None:
    """Gợi ý cột/shape cho SQLCoder từ ChartTemplate (Tier 4)."""
    tpl = match_chart_template(query, domain_id=domain_id)
    if not tpl:
        return None
    parts = [
        f"Template: {tpl.id} ({tpl.name}) → prefer chart={tpl.chart_type}.",
        f"Shape: {tpl.shape}.",
    ]
    if tpl.required_cols:
        parts.append(f"Required columns: {', '.join(tpl.required_cols)}.")
    if tpl.preferred_cols:
        parts.append(f"Preferred columns: {', '.join(tpl.preferred_cols)}.")
    if tpl.shape == "valuation_snapshot":
        parts.append(
            "Use DISTINCT ON (ticker/symbol) … ORDER BY ticker, calc_date DESC "
            "so each ticker has one latest row. Avoid duplicate calc_dates per ticker."
        )
    if tpl.shape in ("price_timeseries", "price_ohlc", "multi_ticker_price"):
        parts.append(
            "Select trade_date + prices; omit company_name unless user asked for names. "
            "ORDER BY trade_date ASC (or DESC with LIMIT for recent sessions)."
        )
    return " ".join(parts)


class HistoryMessage(BaseModel):
    """Một tin nhắn trong lịch sử chat (dùng cho ngữ cảnh LLM)."""

    role: Literal["user", "assistant"] = Field(
        ...,
        description="Vai trò: user hoặc assistant",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Nội dung tin nhắn",
    )


class ChatRequest(BaseModel):
    """Body request cho POST /api/v1/chat."""

    domain_id: str = Field(
        ...,
        description="ID domain cấu hình (vd: finance_vnfdata)",
        examples=["finance_vnfdata"],
    )
    query: str = Field(
        ...,
        min_length=1,
        description="Câu hỏi tiếng Việt của người dùng",
        examples=["Top 10 mã vốn hóa lớn nhất"],
    )
    history: list[HistoryMessage] = Field(
        default_factory=list,
        description="Lịch sử chat gần đây (role + content) để LLM hiểu ngữ cảnh",
    )
    # Cho phép frontend gửi kèm data cũ khi chỉ đổi loại biểu đồ
    reuse_data: list[dict[str, Any]] | None = Field(
        default=None,
        description="Data lần trước (khi user chỉ yêu cầu đổi chart)",
    )
    previous_insight: str = Field(
        default="",
        description="Insight báo cáo gốc — dùng lại khi viz_only để Word/UI không mất nội dung",
    )


class ChatResponse(BaseModel):
    """Response: SQL + data + insight + loại biểu đồ đề xuất."""

    status: ResponseStatus = "success"
    domain_id: str
    query: str
    sql_query: str
    data: list[dict[str, Any]]
    insight: str
    row_count: int
    chart_type: ChartType
    viz_only: bool = False
    from_cache: bool = False
    column_labels: dict[str, str] = Field(default_factory=dict)
    # Phase 2: debug SQL khi status=error — giúp user/dev chỉnh câu hỏi
    failed_sql: str | None = None
    error_detail: str | None = None
    # Router intent (sql/viz/followup/chitchat/oos)
    intent: str | None = None
    # Nguồn SQL: fast_path | llm | repair | cache | …
    sql_source: str | None = None
    # Ngày mới nhất trong kết quả (YYYY-MM-DD), suy từ data — không query thêm
    data_as_of: str | None = None
    # So sánh kỳ (MoM/QoQ/YoY) — đã tính từ data, dùng badge KPI
    period_comparison: dict[str, Any] | None = None
    # Dự báo tuyến tính ngắn hạn (line/area overlay)
    forecast: dict[str, Any] | None = None
    # Tier 4: template CP khớp câu hỏi (id/name/chart_type/shape)
    chart_template: dict[str, Any] | None = None
    # Tier 4: ghi chú shape + nguồn giá (trust)
    trust_meta: dict[str, Any] | None = None
    shape_notes: list[str] = Field(default_factory=list)


class ArticleRequest(BaseModel):
    """Body request cho POST /api/v1/generate_article."""

    domain_id: str = Field(..., description="ID domain")
    question: str = Field(..., min_length=1, description="Câu hỏi gốc")
    data: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="Dữ liệu JSON đã truy vấn (bắt buộc có ít nhất 1 dòng)",
    )
    stats: dict[str, Any] | None = Field(
        default=None,
        description="Stats đã tính sẵn (optional — backend tự tính nếu thiếu)",
    )
    insight_summary: str = Field(
        default="",
        description="Tóm tắt insight hiện có để Narrative Planner tham khảo",
    )
    chart_image_base64: str | None = Field(
        default=None,
        description="Ảnh biểu đồ PNG (data URL hoặc base64) để chèn vào bài",
    )


class ArticleResponse(BaseModel):
    """Bài báo hoàn chỉnh từ Narrative Planner."""

    article_markdown: str
    outline: dict[str, Any]
    word_count: int
    sections_written: int = 0
    domain_id: str
    question: str
    chart_image_embedded: bool = False
    template_id: str = ""
    template_name: str = ""
    generated_at: str = ""


class WordExportRequest(BaseModel):
    domain_id: str = ""
    query: str = ""
    insight: str = ""
    data: list[dict[str, Any]] = Field(default_factory=list)
    article_markdown: str = ""
    chart_image_base64: str | None = None


class DashboardCreateRequest(BaseModel):
    title: str = "Dashboard"
    domain_id: str
    reports: list[dict[str, Any]] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    """Body request cho POST /api/v1/feedback."""

    domain_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    vote: Literal["up", "down"]
    sql_query: str = ""
    sql_source: str | None = None
    status: str | None = None


class FeedbackResponse(BaseModel):
    ok: bool = True


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Lưu thumbs up/down — append JSONL để cải thiện few-shot sau này."""
    log_feedback(
        domain_id=request.domain_id,
        query=request.query,
        vote=request.vote,
        sql_query=request.sql_query or "",
        sql_source=request.sql_source,
        status=request.status,
    )
    return FeedbackResponse(ok=True)


@router.get("/domains")
def get_domains() -> dict[str, list[dict[str, str]]]:
    """Liệt kê các domain có sẵn kèm tên hiển thị."""
    items: list[dict[str, str]] = []
    for domain_id in list_available_domains():
        try:
            cfg = load_domain_config(domain_id)
            name = str(cfg.get("domain_name") or domain_id)
        except Exception:
            name = domain_id
        items.append({"id": domain_id, "name": name})
    return {"domains": items}


@router.get("/domains/{domain_id}/explore")
def explore_domain(domain_id: str) -> dict[str, Any]:
    """Schema nghiệp vụ + câu hỏi mẫu — giúp user biết domain có gì để hỏi."""
    try:
        cfg = load_domain_config(domain_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return build_domain_explore(cfg)


@router.get("/health/domains")
def get_domains_health() -> dict[str, Any]:
    """Kiểm tra kết nối DB từng domain + trạng thái RAG schema."""
    results: dict[str, Any] = {
        "schema_rag_enabled": is_schema_rag_enabled(),
        "domains": {},
    }
    for domain_id in list_available_domains():
        try:
            cfg = load_domain_config(domain_id)
            db_url = cfg["db_url"]
            ok, detail = check_db_connection(db_url)
            dialect = detect_dialect(db_url)
            results["domains"][domain_id] = {
                "db_ok": ok,
                "dialect": dialect,
                "dialect_label": dialect_label(dialect),
                "detail": detail if not ok else "connected",
            }
        except Exception as exc:
            results["domains"][domain_id] = {
                "db_ok": False,
                "detail": str(exc),
            }
    return results


@router.get("/data-quality")
def get_data_quality(domain_id: str = "finance_vnfdata") -> dict[str, Any]:
    """
    Tóm tắt chất lượng giá đóng cửa từ price_cross_check:
    - Tổng verified / divergent
    - Top mã lệch nhiều ngày nhất
    - Divergent theo ngày (30 ngày gần nhất)
    """
    try:
        cfg = load_domain_config(domain_id)
    except (FileNotFoundError, ValueError):
        domains = list_available_domains()
        if not domains:
            raise HTTPException(status_code=404, detail="No domain configured")
        cfg = load_domain_config(domains[0])

    from sqlalchemy import text as sa_text
    from core.db_engine import get_engine

    db_url = cfg["db_url"]
    try:
        engine = get_engine(db_url)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"DB unavailable: {exc}") from exc

    try:
        with engine.connect() as conn:
            summary_rows = conn.execute(sa_text(
                "SELECT status, count(*) AS cnt FROM price_cross_check GROUP BY status ORDER BY status"
            )).fetchall()

            top_rows = conn.execute(sa_text("""
                SELECT c.ticker,
                       c.company_name,
                       count(*)                                   AS days_divergent,
                       round(avg(pcc.max_diff_pct)::numeric, 2)  AS avg_diff_pct,
                       round(max(pcc.max_diff_pct)::numeric, 2)  AS max_diff_pct,
                       max(pcc.trade_date)::text                 AS latest_date
                FROM price_cross_check pcc
                JOIN companies c ON c.id = pcc.company_id
                WHERE pcc.status = 'divergent'
                GROUP BY c.ticker, c.company_name
                ORDER BY days_divergent DESC, max_diff_pct DESC
                LIMIT 20
            """)).fetchall()

            date_rows = conn.execute(sa_text("""
                SELECT trade_date::text,
                       count(*)                                  AS cnt,
                       round(max(max_diff_pct)::numeric, 2)     AS max_diff_pct
                FROM price_cross_check
                WHERE status = 'divergent'
                  AND trade_date >= current_date - 30
                GROUP BY trade_date
                ORDER BY trade_date DESC
            """)).fetchall()

            last_checked = conn.execute(sa_text(
                "SELECT max(checked_at)::text FROM price_cross_check"
            )).scalar()

        return {
            "last_checked": last_checked,
            "summary": {row[0]: row[1] for row in summary_rows},
            "top_divergent_tickers": [
                {
                    "ticker": row[0],
                    "company_name": row[1],
                    "days_divergent": row[2],
                    "avg_diff_pct": float(row[3]) if row[3] is not None else None,
                    "max_diff_pct": float(row[4]) if row[4] is not None else None,
                    "latest_date": row[5],
                }
                for row in top_rows
            ],
            "divergent_by_date": [
                {
                    "trade_date": row[0],
                    "divergent_count": row[1],
                    "max_diff_pct": float(row[2]) if row[2] is not None else None,
                }
                for row in date_rows
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/generate_article", response_model=ArticleResponse)
def generate_article_endpoint(request: ArticleRequest) -> ArticleResponse:
    """
    Narrative Planner: outline → write sections → finalize bài báo.
    Chỉ gọi khi user bấm "Viết Bài Báo" — không chạy trong luồng chat thường.
    """
    try:
        domain_config = load_domain_config(request.domain_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    domain_name = str(domain_config.get("domain_name") or request.domain_id)
    labels = domain_config.get("column_labels", {}) or {}

    # Đổi key sang nhãn tiếng Việt nếu có — bài báo dễ đọc hơn
    data_for_article = request.data
    if labels:
        data_for_article = [
            {labels.get(k, k): v for k, v in row.items()} for row in request.data
        ]

    stats = request.stats
    if not stats:
        stats = compute_insight_stats(data_for_article)

    try:
        result = generate_article(
            question=request.question,
            domain_name=domain_name,
            data=data_for_article,
            stats=stats,
            insight_summary=request.insight_summary or "",
            domain_id=request.domain_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Lỗi Narrative Planner (Ollama): {exc}",
        ) from exc

    try:
        return _build_article_response(request, result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi xử lý bài báo: {exc}",
        ) from exc


def _build_article_response(
    request: ArticleRequest,
    result: dict[str, Any],
) -> ArticleResponse:
    markdown = str(result["article_markdown"] or "")
    chart_embedded = False
    if request.chart_image_base64 and len(request.chart_image_base64) < 800_000:
        img = request.chart_image_base64.strip()
        if not img.startswith("data:"):
            img = f"data:image/png;base64,{img}"
        lines = markdown.splitlines()
        insert_at = 0
        for i, line in enumerate(lines):
            if line.lstrip().startswith("# ") and not line.lstrip().startswith("##"):
                insert_at = i + 1
                break
        # Chèn chart sau meta timestamp / dòng trống ngay sau tiêu đề
        while insert_at < len(lines):
            s = lines[insert_at].strip()
            if not s or "Thời gian tạo báo cáo:" in s:
                insert_at += 1
                continue
            break
        chart_block = [
            "",
            "![Biểu đồ phân tích](" + img + ")",
            "",
            "*Biểu đồ minh họa dữ liệu truy vấn.*",
            "",
        ]
        lines[insert_at:insert_at] = chart_block
        markdown = "\n".join(lines)
        chart_embedded = True
        result["word_count"] = len(markdown.split())

    return ArticleResponse(
        article_markdown=markdown,
        outline=result["outline"],
        word_count=int(result["word_count"]),
        sections_written=int(result.get("sections_written") or 0),
        domain_id=request.domain_id,
        question=request.question,
        chart_image_embedded=chart_embedded,
        template_id=str(result.get("template_id") or ""),
        template_name=str(result.get("template_name") or ""),
        generated_at=str(result.get("generated_at") or ""),
    )


@router.post("/generate_article/stream")
def generate_article_stream(request: ArticleRequest) -> StreamingResponse:
    """
    SSE: progress thật từ Narrative Planner + event result cuối.
    """

    def event_gen():
        q: queue_mod.Queue[tuple[str, Any]] = queue_mod.Queue()

        def emit_progress(step: str) -> None:
            q.put(("progress", step))

        def worker() -> None:
            try:
                try:
                    domain_config = load_domain_config(request.domain_id)
                except FileNotFoundError as exc:
                    q.put(("error", str(exc)))
                    return
                except ValueError as exc:
                    q.put(("error", str(exc)))
                    return

                domain_name = str(
                    domain_config.get("domain_name") or request.domain_id
                )
                labels = domain_config.get("column_labels", {}) or {}
                data_for_article = request.data
                if labels:
                    data_for_article = [
                        {labels.get(k, k): v for k, v in row.items()}
                        for row in request.data
                    ]
                stats = request.stats or compute_insight_stats(data_for_article)
                result = generate_article(
                    question=request.question,
                    domain_name=domain_name,
                    data=data_for_article,
                    stats=stats,
                    insight_summary=request.insight_summary or "",
                    domain_id=request.domain_id,
                    on_progress=emit_progress,
                )
                resp = _build_article_response(request, result)
                q.put(("result", resp))
            except Exception as exc:  # noqa: BLE001
                q.put(("error", f"Lỗi Narrative Planner: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

        while True:
            try:
                kind, payload = q.get(timeout=120)
            except queue_mod.Empty:
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "event": "progress",
                            "step": "Đang chờ model Ollama…",
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
                continue

            if kind == "progress":
                yield (
                    "data: "
                    + json.dumps(
                        {"event": "progress", "step": str(payload)},
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
                continue
            if kind == "result":
                data = payload.model_dump(mode="json")
                yield (
                    "data: "
                    + json.dumps(
                        {"event": "result", "data": data}, ensure_ascii=False
                    )
                    + "\n\n"
                )
                break
            yield (
                "data: "
                + json.dumps(
                    {"event": "error", "step": str(payload)}, ensure_ascii=False
                )
                + "\n\n"
            )
            break

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/export/word")
def export_word_endpoint(request: WordExportRequest) -> Response:
    """Xuất báo cáo / bài viết Word (.docx), nhúng ảnh ECharts nếu có."""
    df = pd.DataFrame(request.data) if request.data else None
    try:
        content, _embedded = create_word_report_api(
            query=request.query,
            insight_text=request.insight,
            dataframe=df,
            chart_image_base64=request.chart_image_base64,
            article_markdown=request.article_markdown or "",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi xuất Word: {exc}") from exc
    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={"Content-Disposition": 'attachment; filename="bao-cao-bi.docx"'},
    )


@router.post("/dashboards")
def create_dashboard_endpoint(request: DashboardCreateRequest) -> dict[str, Any]:
    """Lưu dashboard (1+ báo cáo) — trả id để share."""
    if not request.reports:
        raise HTTPException(status_code=400, detail="reports không được rỗng")
    payload = create_dashboard(
        title=request.title or "Dashboard",
        domain_id=request.domain_id,
        reports=request.reports,
    )
    return {"id": payload["id"], "title": payload["title"]}


@router.get("/dashboards/{dash_id}")
def get_dashboard_endpoint(dash_id: str) -> dict[str, Any]:
    data = get_dashboard(dash_id)
    if not data:
        raise HTTPException(status_code=404, detail="Dashboard không tồn tại")
    return data


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    http_request: Request,
) -> ChatResponse:
    """
    Luồng Text-to-SQL + Insight + Viz:
      1. Load config
      2. Nếu chỉ đổi chart + có reuse_data → bỏ qua SQL/LLM
      3. Cache → Fast-path → Router (Qwen) → SQLCoder nếu cần
      4. execute → insight → resolve_chart_type
    """
    t0 = time.perf_counter()
    latency_llm_ms = 0.0
    latency_db_ms = 0.0
    sql_source = "unknown"
    sql = ""
    intent: str | None = None
    request_id = uuid.uuid4().hex[:12]
    client_ip = _client_ip(http_request)

    history_dicts: list[dict[str, str]] = [
        {"role": m.role, "content": m.content} for m in request.history
    ]

    def _log_out(
        status: str,
        *,
        row_count: int = 0,
        viz_only: bool = False,
        error: str | None = None,
        from_cache: bool = False,
    ) -> None:
        log_chat_event(
            domain_id=request.domain_id,
            query=request.query,
            status=status,
            sql_source=sql_source,
            sql_query=sql,
            row_count=row_count,
            latency_total_ms=(time.perf_counter() - t0) * 1000,
            latency_llm_ms=latency_llm_ms or None,
            latency_db_ms=latency_db_ms or None,
            viz_only=viz_only,
            error=error,
            from_cache=from_cache,
            intent=intent,
            request_id=request_id,
            client_ip=client_ip,
        )

    # --- Nhánh nhanh: chỉ đổi loại biểu đồ, tái sử dụng data ---
    if (
        is_viz_only_request(request.query)
        and request.reuse_data
        and len(request.reuse_data) > 0
    ):
        sql_source = "viz_only"
        intent = INTENT_VIZ
        sql = "(giữ nguyên truy vấn trước — chỉ đổi loại biểu đồ)"
        chart = resolve_chart_type(
            request.query, history=history_dicts, data=request.reuse_data
        )
        chart_label = {
            "pie": "tròn (pie)",
            "bar": "cột (bar)",
            "line": "đường (line)",
            "area": "miền / vùng (area)",
            "combo": "kết hợp (combo)",
            "table": "bảng",
        }.get(chart, chart)
        # Load labels nếu có domain (không chặn khi thiếu)
        labels: dict[str, str] = {}
        try:
            labels = load_domain_config(request.domain_id).get("column_labels", {}) or {}
        except Exception:
            labels = {}
        prev = (request.previous_insight or "").strip()
        if prev:
            insight_text = (
                f"{prev}\n\n---\n\n"
                f"_Đã chuyển hiển thị sang biểu đồ **{chart_label}** "
                f"trên cùng bộ dữ liệu ({len(request.reuse_data)} dòng)._"
            )
        else:
            insight_text = (
                f"Đã chuyển hiển thị sang biểu đồ **{chart_label}** "
                f"trên cùng bộ dữ liệu ({len(request.reuse_data)} dòng)."
            )
        resp = ChatResponse(
            status="success",
            domain_id=request.domain_id,
            query=request.query,
            sql_query=sql,
            data=request.reuse_data,
            insight=insight_text,
            row_count=len(request.reuse_data),
            chart_type=chart,
            viz_only=True,
            column_labels=labels,
            intent=intent,
            sql_source=sql_source,
            data_as_of=_infer_data_as_of(request.reuse_data),
        )
        _log_out("success", row_count=len(request.reuse_data), viz_only=True)
        return resp

    # --- Cache: câu hỏi đã hỏi trước đó → trả ngay, bỏ qua LLM + DB ---
    cached = get_cached_response(request.domain_id, request.query)
    if cached:
        sql_source = str(cached.get("sql_source") or "cache")
        sql = str(cached.get("sql_query") or "")
        row_count = int(cached.get("row_count") or 0)
        resp = ChatResponse(**{**cached, "from_cache": True, "sql_source": sql_source})
        _log_out("success", row_count=row_count, from_cache=True)
        return resp

    # Bước 1: Load metadata domain
    try:
        domain_config = load_domain_config(request.domain_id)
    except FileNotFoundError as exc:
        _log_out("error", error=str(exc))
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        _log_out("error", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    labels = domain_config.get("column_labels", {}) or {}
    entities = resolve_query_entities(request.query, domain_config.get("db_url"))
    entity_hint = str(entities.get("hint") or "")

    # Bước 2: Fast-path SQL (ổn định) hoặc Router → LLM
    sql = try_fast_sql(
        request.domain_id, request.query, db_url=domain_config["db_url"]
    )
    if sql:
        sql_source = "fast_path"
        intent = INTENT_SQL
    else:
        # Router (Qwen) — phân loại intent trước khi gọi SQLCoder
        t_llm = time.perf_counter()
        intent = classify_intent(
            request.query,
            has_history=bool(history_dicts),
            has_reuse_data=bool(request.reuse_data),
            use_llm=True,
        )
        latency_llm_ms += (time.perf_counter() - t_llm) * 1000

        if intent == INTENT_CHITCHAT:
            sql_source = "router_chitchat"
            sql = "(không truy vấn — chitchat)"
            t_llm = time.perf_counter()
            insight = answer_chitchat(request.query)
            latency_llm_ms += (time.perf_counter() - t_llm) * 1000
            _log_out("success", row_count=0)
            return ChatResponse(
                status="success",
                domain_id=request.domain_id,
                query=request.query,
                sql_query=sql,
                data=[],
                insight=insight,
                row_count=0,
                chart_type="table",
                viz_only=False,
                column_labels=labels,
                intent=intent,
                sql_source=sql_source,
            )

        if intent == INTENT_OOS:
            sql_source = "router_oos"
            sql = "(ngoài phạm vi)"
            _log_out("success", row_count=0)
            return ChatResponse(
                status="success",
                domain_id=request.domain_id,
                query=request.query,
                sql_query=sql,
                data=[],
                insight=out_of_scope_message(request.query),
                row_count=0,
                chart_type="table",
                viz_only=False,
                column_labels=labels,
                intent=intent,
                sql_source=sql_source,
            )

        if intent == INTENT_VIZ and request.reuse_data:
            sql_source = "router_viz"
            sql = "(giữ nguyên truy vấn trước — chỉ đổi loại biểu đồ)"
            chart = resolve_chart_type(
                request.query, history=history_dicts, data=request.reuse_data
            )
            prev = (request.previous_insight or "").strip()
            if prev:
                insight_text = (
                    f"{prev}\n\n---\n\n"
                    f"_Đã chuyển hiển thị theo yêu cầu trên cùng bộ dữ liệu "
                    f"({len(request.reuse_data)} dòng)._"
                )
            else:
                insight_text = (
                    f"Đã chuyển hiển thị theo yêu cầu trên cùng bộ dữ liệu "
                    f"({len(request.reuse_data)} dòng)."
                )
            _log_out("success", row_count=len(request.reuse_data), viz_only=True)
            return ChatResponse(
                status="success",
                domain_id=request.domain_id,
                query=request.query,
                sql_query=sql,
                data=request.reuse_data,
                insight=insight_text,
                row_count=len(request.reuse_data),
                chart_type=chart,
                viz_only=True,
                column_labels=labels,
                intent=intent,
                sql_source=sql_source,
                data_as_of=_infer_data_as_of(request.reuse_data),
            )

        # followup / sql / viz-without-data → SQLCoder
        if intent == INTENT_FOLLOWUP:
            sql_source = "llm_followup"
        else:
            intent = INTENT_SQL
            sql_source = "llm"

        sql_config = build_rag_schema_context(domain_config, request.query)
        try:
            t_llm = time.perf_counter()
            sql = generate_sql(
                sql_config,
                request.query,
                history=history_dicts,
                entity_hint=entity_hint,
                shape_hint=_shape_hint_for_sql(request.domain_id, request.query),
            )
            latency_llm_ms += (time.perf_counter() - t_llm) * 1000
        except Exception as exc:
            _log_out("error", error=str(exc))
            raise HTTPException(
                status_code=502,
                detail=f"Lỗi khi gọi LLM sinh SQL (Ollama): {exc}",
            ) from exc

    # Phục hồi khi LLM trả SQL rỗng — repair → few-shot gần nhất (không hardcode intent)
    if not (sql or "").strip():
        sql_config = build_rag_schema_context(domain_config, request.query)
        try:
            t_llm = time.perf_counter()
            sql = repair_sql(
                sql_config,
                request.query,
                broken_sql="(empty)",
                error_message="Model returned empty SQL. Write one valid SELECT.",
                history=history_dicts,
                entity_hint=entity_hint,
            )
            latency_llm_ms += (time.perf_counter() - t_llm) * 1000
            if (sql or "").strip():
                sql_source = "repair"
        except Exception:
            pass
        if not (sql or "").strip():
            retrieved = best_few_shot_sql(
                request.query,
                domain_config.get("few_shot_examples") or [],
            )
            if retrieved:
                sql = retrieved
                sql_source = "few_shot_retrieval"

    # Bước 3: Guardrail + thực thi (nếu lỗi → sửa 1 lần → fast-path / few-shot fallback)
    rows: list[dict[str, Any]] = []
    try:
        t_db = time.perf_counter()
        rows = execute_query(domain_config["db_url"], sql)
        latency_db_ms += (time.perf_counter() - t_db) * 1000
    except DbQueryError as first_exc:
        last_db_error: DbQueryError = first_exc
        sql_config = build_rag_schema_context(domain_config, request.query)
        try:
            t_llm = time.perf_counter()
            sql = repair_sql(
                sql_config,
                request.query,
                broken_sql=sql,
                error_message=str(first_exc),
                history=history_dicts,
                entity_hint=entity_hint,
            )
            latency_llm_ms += (time.perf_counter() - t_llm) * 1000
            sql_source = "repair"
            t_db = time.perf_counter()
            rows = execute_query(domain_config["db_url"], sql)
            latency_db_ms += (time.perf_counter() - t_db) * 1000
        except DbQueryError as repair_exc:
            last_db_error = repair_exc
            fallback_sql = try_fast_sql(
                request.domain_id,
                request.query,
                db_url=domain_config["db_url"],
            )
            if not fallback_sql:
                fallback_sql = best_few_shot_sql(
                    request.query,
                    domain_config.get("few_shot_examples") or [],
                )
                if fallback_sql:
                    sql_source = "few_shot_retrieval"
            if fallback_sql:
                try:
                    sql = fallback_sql
                    if sql_source != "few_shot_retrieval":
                        sql_source = "fast_path_fallback"
                    t_db = time.perf_counter()
                    rows = execute_query(domain_config["db_url"], sql)
                    latency_db_ms += (time.perf_counter() - t_db) * 1000
                except DbQueryError as fallback_exc:
                    last_db_error = fallback_exc
            if not rows:
                _log_out("error", error=str(last_db_error))
                return ChatResponse(
                    status="error",
                    domain_id=request.domain_id,
                    query=request.query,
                    sql_query=sql,
                    data=[],
                    insight=_INSIGHT_QUERY_ERROR,
                    row_count=0,
                    chart_type="table",
                    viz_only=False,
                    column_labels=labels,
                    failed_sql=sql,
                    error_detail=str(last_db_error),
                    intent=intent,
                    sql_source=sql_source,
                )

    # Kịch bản B: truy vấn OK nhưng không có dữ liệu
    if not rows:
        _log_out("empty")
        resp = ChatResponse(
            status="empty",
            domain_id=request.domain_id,
            query=request.query,
            sql_query=sql,
            data=[],
            insight=_INSIGHT_EMPTY_DATA,
            row_count=0,
            chart_type="table",
            viz_only=False,
            column_labels=labels,
            intent=intent,
            sql_source=sql_source,
        )
        set_cached_response(
            request.domain_id, request.query, resp.model_dump(mode="json")
        )
        return resp

    # Bước 4: Insight + period comparison (chỉ khi có dữ liệu)
    stats = compute_insight_stats(rows)
    period = _label_period(stats.get("period_comparison"), labels)
    forecast = _label_forecast(stats.get("forecast"), labels)

    try:
        t_llm = time.perf_counter()
        insight = generate_insight(
            request.query,
            rows,
            column_labels=labels,
            precomputed_stats=stats,
        )
        latency_llm_ms += (time.perf_counter() - t_llm) * 1000
    except Exception:
        insight = (
            "**Tóm tắt:** Dữ liệu đã truy vấn thành công. "
            "**Chi tiết:** Xem bảng số liệu và biểu đồ phía dưới để đối chiếu chi tiết. "
            "**Gợi ý:** AI phân tích tạm thời chậm — bạn vẫn có thể tải CSV/Word."
        )

    # Bước 5: Template CP + chuẩn hóa shape + chọn biểu đồ
    tpl = match_chart_template(request.query, domain_id=request.domain_id)
    shape_notes = validate_shape(rows, tpl)
    chart_rows, normalize_actions = normalize_rows_for_chart(rows, tpl)
    if normalize_actions:
        shape_notes = [*shape_notes, *normalize_actions]
        rows = chart_rows

    chart = resolve_chart_type(
        request.query,
        history=history_dicts,
        data=rows,
        preferred=tpl.chart_type if tpl else None,
    )
    trust = build_trust_meta(
        rows,
        sql_source=sql_source,
        template=tpl,
        shape_notes=shape_notes,
    )

    _log_out("success", row_count=len(rows))
    resp = ChatResponse(
        status="success",
        domain_id=request.domain_id,
        query=request.query,
        sql_query=sql,
        data=rows,
        insight=insight,
        row_count=len(rows),
        chart_type=chart,
        viz_only=False,
        column_labels=labels,
        intent=intent,
        sql_source=sql_source,
        data_as_of=_infer_data_as_of(rows),
        period_comparison=period,
        forecast=forecast,
        chart_template=template_to_dict(tpl),
        trust_meta=trust,
        shape_notes=shape_notes,
    )
    set_cached_response(
        request.domain_id, request.query, resp.model_dump(mode="json")
    )
    return resp


_STREAM_STEPS = [
    "Đang phân loại câu hỏi (Router)…",
    "Đang tạo SQL…",
    "Đang truy vấn cơ sở dữ liệu…",
    "Đang phân tích insight…",
    "Đang chọn biểu đồ…",
]


@router.post("/chat/stream")
def chat_stream(
    request: ChatRequest,
    http_request: Request,
) -> StreamingResponse:
    """
    SSE stream: gửi progress steps trong lúc chạy /chat đồng bộ,
    rồi gửi event result với ChatResponse đầy đủ.
    """

    def event_gen():
        q: queue_mod.Queue[tuple[str, Any]] = queue_mod.Queue()

        def worker() -> None:
            try:
                result = chat(request, http_request=http_request)
                q.put(("result", result))
            except Exception as exc:  # noqa: BLE001
                q.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

        step_i = 0
        while True:
            try:
                kind, payload = q.get(timeout=1.8)
            except queue_mod.Empty:
                if step_i < len(_STREAM_STEPS):
                    yield (
                        "data: "
                        + json.dumps(
                            {"event": "progress", "step": _STREAM_STEPS[step_i]},
                            ensure_ascii=False,
                        )
                        + "\n\n"
                    )
                    step_i += 1
                continue

            if kind == "result":
                data = payload.model_dump(mode="json")
                yield (
                    "data: "
                    + json.dumps({"event": "result", "data": data}, ensure_ascii=False)
                    + "\n\n"
                )
                break
            yield (
                "data: "
                + json.dumps({"event": "error", "step": str(payload)}, ensure_ascii=False)
                + "\n\n"
            )
            break

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
