"""Giao diện Streamlit — Conversational BI + Dynamic Dashboard (Enterprise)."""

from __future__ import annotations

import os
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
from dotenv import load_dotenv

from core.viz_advisor import (
    is_viz_only_request,
    should_use_horizontal_bar,
    should_use_stacked_100_percent,
)
from utils.report_export import (
    create_article_word,
    create_word_report,
    is_kaleido_available,
    split_article_markdown,
)

InsightRenderKind = Literal["success", "warning", "info"]

load_dotenv(Path(__file__).resolve().parent / ".env")
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000").rstrip("/")
CHAT_URL = f"{API_BASE}/api/v1/chat"
ARTICLE_URL = f"{API_BASE}/api/v1/generate_article"
DOMAINS_URL = f"{API_BASE}/api/v1/domains"
_API_TIMEOUT_SEC = 300  # LLM local có thể mất 2–3 phút với câu hỏi phức tạp
_ARTICLE_TIMEOUT_SEC = 420  # Narrative Planner: 3 bước LLM
_API_KEY = os.getenv("API_KEY", "").strip()


def _api_headers() -> dict[str, str]:
    """Gửi X-API-Key khi backend bật auth."""
    if not _API_KEY:
        return {}
    return {"X-API-Key": _API_KEY}

# Fallback khi API chưa chạy
_FALLBACK_DOMAINS: dict[str, str] = {
    "finance_vnfdata": "VNFDATA — Tài chính",
}

_MAX_HISTORY_MESSAGES = 5
_CHART_OPTIONS = {
    "bar": "Cột (Bar)",
    "area": "Miền / Vùng (Area)",
    "line": "Đường (Line)",
    "combo": "Kết hợp (Combo)",
    "pie": "Tròn (Pie)",
    "table": "Chỉ bảng",
}

# Plotly: bật nút tải PNG, ẩn các nút thừa
_PLOTLY_CONFIG: dict[str, Any] = {
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "lasso2d",
        "select2d",
        "autoScale2d",
        "toggleSpikelines",
    ],
    "toImageButtonOptions": {
        "format": "png",
        "filename": "ai_bi_chart",
        "height": 720,
        "width": 1280,
        "scale": 2,
    },
}

# Palette Power BI — xanh dương + tím đậm
_COLOR_SEQ = ["#0078D4", "#5C2D91", "#107C10", "#8764B8", "#004E8C", "#881798"]
_KPI_ACCENTS = ["#0078D4", "#5C2D91", "#107C10", "#8764B8"]

_FALLBACK_LABELS: dict[str, str] = {
    "ma_cp": "Mã CP",
    "ten_dn": "Tên doanh nghiệp",
    "san_giao_dich": "Sàn GD",
    "nganh": "Ngành",
    "von_hoa": "Vốn hóa (tỷ)",
    "gia_dong_cua": "Giá đóng cửa",
    "khoi_luong_gd": "Khối lượng GD",
    "doanh_thu_thuan": "Doanh thu thuần (tỷ)",
    "ln_sau_thue": "LN sau thuế (tỷ)",
    "eps": "EPS (VND)",
    "pe": "P/E",
}

# Gợi ý câu hỏi theo domain — sidebar hiển thị đúng ngữ cảnh nghiệp vụ
_DOMAIN_SAMPLE_QUERIES: dict[str, list[str]] = {
    "finance_vnfdata": [
        "Top 5 mã cổ phiếu có vốn hóa lớn nhất trên sàn HoSE, vẽ biểu đồ cột",
        "Cho tôi biết doanh thu thuần và LN sau thuế của FPT qua các quý",
        "Diễn biến giá đóng cửa VCB 5 phiên gần nhất, vẽ biểu đồ đường",
        "So sánh EPS FPT, VCB, HPG",
    ],
}

# Câu viz_only khi user đổi loại biểu đồ trên dashboard
_CHART_VIZ_QUERIES: dict[str, str] = {
    "bar": "Vẽ biểu đồ cột (bar) cho tôi",
    "line": "Vẽ biểu đồ đường (line) cho tôi",
    "area": "Vẽ biểu đồ miền (area) cho tôi",
    "combo": "Vẽ biểu đồ combo kết hợp cho tôi",
    "pie": "Vẽ biểu đồ tròn (pie) cho tôi",
    "table": "Chỉ hiển thị bảng, không cần biểu đồ",
}


# ---------------------------------------------------------------------------
# Helpers: labels / columns / API
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def _load_domains() -> dict[str, str]:
    """Lấy danh sách domain từ API — fallback nếu backend chưa chạy."""
    try:
        resp = requests.get(DOMAINS_URL, headers=_api_headers(), timeout=5)
        resp.raise_for_status()
        items = resp.json().get("domains", [])
        if items and isinstance(items[0], dict):
            return {item["id"]: item.get("name", item["id"]) for item in items}
        return {d: d.replace("_", " ").title() for d in items}
    except Exception:
        return dict(_FALLBACK_DOMAINS)


def _normalize_for_match(text: str) -> str:
    """Chuẩn hóa tên cột để so khớp từ khóa (không phân biệt hoa thường, bỏ dấu)."""
    lowered = (text or "").lower().replace("đ", "d").replace("Đ", "d")
    nfd = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


_MONEY_KEYWORDS = (
    "gia", "tien", "doanh thu", "loi nhuan", "von", "chi phi",
    "tai san", "no", "gia tri",
)
_PERCENT_KEYWORDS = (
    "pct", "ty le", "phan tram", "roe", "roa", "margin", "hoan thanh",
    "progress", "grade", "tiến độ", "tien do", "ham luong",
)
_QUANTITY_KEYWORDS = ("sl", "so luong", "khoi luong", "tru luong", "tonnage")

ColumnFormatType = Literal["price", "billions", "percent", "quantity", "money", "ratio", "default"]

_DATE_KEYWORDS = ("ngay", "date", "time", "thang", "updated", "surveyed")
_PRICE_KEYWORDS = ("gia mo", "gia cao", "gia thap", "gia dong", "gia dieu", "eps")
_RATIO_KEYWORDS = ("pe", "pb", "beta", "he so")


def _column_format_type(col_name: str) -> ColumnFormatType:
    """Phân loại cột số theo từ khóa trong tên (ưu tiên cụ thể → chung)."""
    norm = _normalize_for_match(col_name)
    lower = (col_name or "").lower()

    if "%" in col_name or any(k in norm for k in _PERCENT_KEYWORDS) or "bien dong" in norm:
        return "percent"
    if "(ty)" in lower or "(tỷ)" in lower or norm.endswith(" ty") or "von hoa" in norm:
        return "billions"
    if any(k in norm for k in _QUANTITY_KEYWORDS):
        return "quantity"
    if any(k in norm for k in _PRICE_KEYWORDS):
        return "price"
    if any(k in norm for k in _RATIO_KEYWORDS):
        return "ratio"
    if any(k in norm for k in _MONEY_KEYWORDS):
        return "money"
    return "default"


def _find_col_by_keywords(columns: list[str], keywords: tuple[str, ...]) -> str | None:
    for col in columns:
        norm = _normalize_for_match(col)
        if any(k in norm for k in keywords):
            return col
    return None


def _date_column(df: pd.DataFrame, num_cols: list[str]) -> str | None:
    for col in df.columns:
        if col in num_cols:
            continue
        norm = _normalize_for_match(str(col))
        if any(k in norm for k in _DATE_KEYWORDS):
            return col
    return None


def _chart_x_column(df: pd.DataFrame, num_cols: list[str]) -> str | None:
    """Ưu tiên cột ngày cho time-series; bỏ cột phân loại có 1 giá trị (vd: Mã CP)."""
    date_col = _date_column(df, num_cols)
    if date_col:
        return date_col
    for col in df.columns:
        if col in num_cols:
            continue
        if df[col].nunique(dropna=True) > 1:
            return col
    text_cols = [c for c in df.columns if c not in num_cols]
    return text_cols[0] if text_cols else None


def _pick_chart_y_columns(
    df: pd.DataFrame,
    num_cols: list[str],
    chart_type: str,
    query: str = "",
) -> list[str]:
    """Chọn cột Y phù hợp — tránh vẽ mọi số trên cùng một trục."""
    norm_q = _normalize_for_match(query)
    date_col = _date_column(df, num_cols)

    close_col = _find_col_by_keywords(num_cols, ("gia dong", "dong cua", "dong cửa"))
    price_cols = [
        c for c in num_cols
        if _column_format_type(c) == "price"
        or any(k in _normalize_for_match(c) for k in _PRICE_KEYWORDS)
    ]
    vol_col = _find_col_by_keywords(num_cols, ("khoi luong", "khối lượng"))
    pct_col = _find_col_by_keywords(num_cols, ("bien dong", "biến động", "pct", "ty le"))

    wants_volume = any(k in norm_q for k in ("khoi luong", "khối lượng", "giao dich", "giao dịch"))

    if chart_type == "combo" and date_col:
        primary = close_col or (price_cols[0] if price_cols else None)
        secondary = vol_col
        if primary and secondary and primary != secondary:
            return [primary, secondary]
        if len(num_cols) >= 2:
            return num_cols[:2]

    if date_col and chart_type in ("line", "area", "combo"):
        primary = close_col or (price_cols[0] if price_cols else None)
        if primary:
            if wants_volume and vol_col and vol_col != primary:
                return [primary, vol_col]
            return [primary]
        if vol_col:
            return [vol_col]
        if pct_col:
            return [pct_col]
        return num_cols[:1]

    if chart_type == "pie":
        value_col = _find_col_by_keywords(
            num_cols,
            ("tong", "total", "von hoa", "doanh thu", "trữ lượng", "tru luong", "tonnage"),
        )
        return [value_col or num_cols[0]]

    # bar / default: tối đa 2–3 cột cùng đơn vị
    progress_col = _find_col_by_keywords(num_cols, ("pct", "progress", "tien do", "tiến độ"))
    if progress_col:
        return [progress_col]
    if len(num_cols) <= 2:
        return num_cols
    if price_cols:
        return price_cols[:2]
    return num_cols[:2]


def _format_kpi_number(value: float, col_name: str) -> str:
    """Định dạng số cho st.metric — có dấu phẩy hàng nghìn và hậu tố phù hợp."""
    fmt = _column_format_type(col_name)
    if fmt == "percent":
        return f"{value:,.2f}%"
    if fmt in ("price", "money"):
        return f"{value:,.0f} VNĐ"
    if fmt == "billions":
        return f"{value:,.2f} tỷ"
    if fmt == "quantity":
        return f"{value:,.0f}"
    if fmt == "ratio":
        return f"{value:,.2f}"
    return f"{value:,.1f}"


def _format_chart_label(value: Any, col_name: str) -> str:
    """Nhãn compact trên bar/line — kiểu Power BI (9.7K, 1.2M, 11.7%)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    val = float(value)
    fmt = _column_format_type(col_name)
    if fmt == "percent":
        return f"{val:.1f}%"
    abs_val = abs(val)
    if abs_val >= 1_000_000_000:
        return f"{val / 1_000_000_000:.1f}B"
    if abs_val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M"
    if abs_val >= 10_000:
        return f"{val / 1_000:.1f}K"
    if fmt in ("price", "money"):
        return f"{val:,.0f}"
    if fmt == "billions":
        return f"{val:.1f}"
    if fmt == "ratio":
        return f"{val:.1f}"
    if abs_val >= 1000:
        return f"{val:,.0f}"
    return f"{val:.1f}" if abs_val < 100 else f"{val:,.0f}"


def _build_column_config(df: pd.DataFrame) -> dict[str, Any]:
    """Sinh column_config — dùng format float để tránh cảnh báo tam giác."""
    config: dict[str, Any] = {}
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        fmt = _column_format_type(str(col))
        if fmt == "price":
            config[col] = st.column_config.NumberColumn(format="%.0f")
        elif fmt == "billions":
            config[col] = st.column_config.NumberColumn(format="%.2f")
        elif fmt == "money":
            config[col] = st.column_config.NumberColumn(format="%.2f")
        elif fmt == "percent":
            config[col] = st.column_config.NumberColumn(format="%.2f")
        elif fmt == "quantity":
            config[col] = st.column_config.NumberColumn(format="%.0f")
        elif fmt == "ratio":
            config[col] = st.column_config.NumberColumn(format="%.2f")
        else:
            config[col] = st.column_config.NumberColumn(format="%.2f")
    return config


def _friendly_name(col: str, labels: dict[str, str]) -> str:
    return labels.get(col) or _FALLBACK_LABELS.get(col) or col.replace("_", " ").title()


def _rename_df(df: pd.DataFrame, labels: dict[str, str]) -> pd.DataFrame:
    return df.rename(columns={c: _friendly_name(c, labels) for c in df.columns})


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    cols = list(df.select_dtypes(include="number").columns)
    return [c for c in cols if c.lower() != "id" and not str(c).lower().endswith("_id")]


def _label_column(df: pd.DataFrame, num_cols: list[str]) -> str | None:
    return _chart_x_column(df, num_cols)


_TOP_KEYWORDS = ("top", "cao nhat", "cao nhất", "lon nhat", "lớn nhất", "cao nhat")
_LOW_KEYWORDS = ("thap nhat", "thấp nhất", "thap", "thấp", "nho nhat", "nhỏ nhất")


def _sort_df_for_chart(
    df: pd.DataFrame,
    x_col: str | None,
    query: str = "",
    y_cols: list[str] | None = None,
    chart_type: str = "bar",
) -> pd.DataFrame:
    """Sort ASC cho time-series; DESC cho Top; ASC cho thấp nhất."""
    if not x_col or x_col not in df.columns:
        return df

    out = df.copy()
    norm_q = _normalize_for_match(query)
    num_cols = _numeric_columns(out)
    is_date = _date_column(out, num_cols) == x_col

    if is_date:
        out[x_col] = pd.to_datetime(out[x_col], errors="coerce")
        return out.sort_values(x_col, ascending=True)

    sort_col = (y_cols[0] if y_cols else None) or (
        num_cols[0] if num_cols else None
    )
    if sort_col and sort_col in out.columns:
        if any(k in norm_q for k in _LOW_KEYWORDS):
            return out.sort_values(sort_col, ascending=True)
        if any(k in norm_q for k in _TOP_KEYWORDS) or chart_type in ("bar", "pie"):
            return out.sort_values(sort_col, ascending=False)

    return out.sort_values(x_col)


def _is_percent_col(name: str) -> bool:
    return _column_format_type(name) == "percent"


def _build_api_history(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    prior = messages[:-1] if messages else []
    recent = prior[-_MAX_HISTORY_MESSAGES:]
    out: list[dict[str, str]] = []
    for msg in recent:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            out.append({"role": role, "content": content})
    return out


def _last_data_from_history(messages: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    for msg in reversed(messages[:-1] if messages else []):
        if msg.get("role") == "assistant":
            payload = msg.get("payload") or {}
            data = payload.get("data") or []
            if data:
                return data
    return None


def _error_payload(
    domain_id: str,
    query: str,
    insight: str,
    sql_query: str = "",
    *,
    failed_sql: str | None = None,
    error_detail: str | None = None,
) -> dict[str, Any]:
    return {
        "status": "error",
        "domain_id": domain_id,
        "query": query,
        "sql_query": sql_query,
        "data": [],
        "insight": insight,
        "row_count": 0,
        "chart_type": "table",
        "viz_only": False,
        "column_labels": {},
        "failed_sql": failed_sql or sql_query or None,
        "error_detail": error_detail,
    }


def _parse_api_error_detail(resp: requests.Response) -> str:
    """Đọc detail từ JSON FastAPI hoặc fallback text/HTML."""
    if not resp.content:
        return f"Mã lỗi HTTP {resp.status_code} (phản hồi rỗng)."
    try:
        body = resp.json()
        if isinstance(body, dict):
            detail = body.get("detail", body)
            if isinstance(detail, list):
                return "; ".join(str(d) for d in detail)
            return str(detail)
        return str(body)
    except ValueError:
        text = (resp.text or "").strip()
        if text:
            return text[:500]
        return f"Mã lỗi HTTP {resp.status_code} (không phải JSON)."


def _call_chat_api(
    domain_id: str,
    query: str,
    history: list[dict[str, str]],
    reuse_data: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "domain_id": domain_id,
        "query": query,
        "history": history,
    }
    if reuse_data is not None:
        body["reuse_data"] = reuse_data
    try:
        resp = requests.post(
            CHAT_URL, json=body, headers=_api_headers(), timeout=_API_TIMEOUT_SEC
        )
    except requests.exceptions.Timeout:
        return _error_payload(
            domain_id,
            query,
            (
                "Yêu cầu xử lý quá lâu (quá 5 phút). AI local đang chậm — "
                "hãy thử câu ngắn hơn, hoặc đợi vài giây rồi hỏi lại. "
                "Ví dụ: «Diễn biến giá đóng cửa VCB 5 phiên gần nhất, vẽ biểu đồ đường»."
            ),
        )
    except requests.exceptions.ConnectionError:
        return _error_payload(
            domain_id,
            query,
            "Không kết nối được Backend API. Hãy chạy: uvicorn main:app --reload --port 8000",
        )
    except requests.exceptions.RequestException as exc:
        return _error_payload(
            domain_id,
            query,
            f"Không thể gọi API lúc này. Chi tiết: {exc}",
        )

    if resp.status_code != 200:
        detail = _parse_api_error_detail(resp)
        hint = ""
        if resp.status_code == 500:
            hint = " Backend có thể đang lỗi — kiểm tra terminal uvicorn."
        elif resp.status_code in (502, 503, 504):
            hint = " Kiểm tra Ollama đã chạy chưa (ollama serve)."
        return _error_payload(
            domain_id,
            query,
            f"Không thể xử lý yêu cầu (HTTP {resp.status_code}). Chi tiết: {detail}.{hint}",
        )

    try:
        return resp.json()
    except ValueError:
        return _error_payload(
            domain_id,
            query,
            "API trả về dữ liệu không hợp lệ (không phải JSON). Kiểm tra backend.",
        )


def _call_generate_article_api(
    domain_id: str,
    question: str,
    data: list[dict[str, Any]],
    insight_summary: str = "",
) -> dict[str, Any]:
    """Gọi Narrative Planner — lập dàn ý + viết bài báo hoàn chỉnh."""
    body: dict[str, Any] = {
        "domain_id": domain_id,
        "question": question,
        "data": data,
        "insight_summary": insight_summary or "",
    }
    try:
        resp = requests.post(
            ARTICLE_URL,
            json=body,
            headers=_api_headers(),
            timeout=_ARTICLE_TIMEOUT_SEC,
        )
    except requests.exceptions.Timeout:
        return {
            "error": (
                "Viết bài báo quá lâu (Narrative Planner cần nhiều bước LLM). "
                "Hãy thử lại hoặc kiểm tra Ollama (qwen2.5:14b)."
            )
        }
    except requests.exceptions.ConnectionError:
        return {
            "error": (
                "Không kết nối được Backend API. "
                "Hãy chạy: uvicorn main:app --reload --port 2004"
            )
        }
    except requests.exceptions.RequestException as exc:
        return {"error": f"Không thể gọi API viết bài: {exc}"}

    if resp.status_code != 200:
        detail = _parse_api_error_detail(resp)
        return {
            "error": f"Không viết được bài báo (HTTP {resp.status_code}): {detail}"
        }

    try:
        return resp.json()
    except ValueError:
        return {"error": "API trả về JSON không hợp lệ khi viết bài báo."}


def _query_cache_key(domain_id: str, query: str) -> str:
    """Khóa cache session — khớp backend (domain + câu hỏi chuẩn hóa)."""
    return f"{domain_id}::{' '.join(query.strip().casefold().split())}"


def _get_session_query_cache() -> dict[str, str]:
    if "query_answer_cache" not in st.session_state:
        st.session_state.query_answer_cache = {}
    return st.session_state.query_answer_cache


def _fetch_chat_cached(
    domain_id: str,
    query: str,
    history: list[dict[str, str]],
    reuse_data: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Gọi /api/v1/chat; ưu tiên cache session (cùng câu hỏi trong phiên).
    Backend còn cache SQLite 30 phút — bỏ qua LLM + DB khi hỏi lại.
    """
    if reuse_data is None:
        cache = _get_session_query_cache()
        key = _query_cache_key(domain_id, query)
        if key in cache:
            return json.loads(cache[key])

    payload = _call_chat_api(domain_id, query, history, reuse_data=reuse_data)

    if (
        reuse_data is None
        and payload.get("status") in ("success", "empty")
        and not payload.get("viz_only")
    ):
        _get_session_query_cache()[_query_cache_key(domain_id, query)] = json.dumps(
            payload, ensure_ascii=False
        )
    return payload


@st.cache_data(ttl=60)
def _fetch_api_health() -> dict[str, Any]:
    """Ping backend — dùng hiển thị trạng thái sidebar."""
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=3)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {"status": "error"}


def _chart_viz_query(chart_type: str) -> str:
    return _CHART_VIZ_QUERIES.get(chart_type, f"Vẽ biểu đồ {chart_type} cho tôi")


def _sync_chart_via_api(
    payload: dict[str, Any],
    chart_type: str,
    domain_id: str,
) -> dict[str, Any]:
    """
    Đổi loại biểu đồ qua API viz_only — không sinh SQL/insight lại.
    Giữ nguyên insight & câu hỏi gốc; chỉ cập nhật chart_type từ backend.
    """
    raw_data = payload.get("data") or []
    if not raw_data or chart_type == payload.get("chart_type"):
        return payload

    new_payload = _call_chat_api(
        domain_id,
        _chart_viz_query(chart_type),
        history=[],
        reuse_data=raw_data,
    )
    merged = dict(new_payload)
    merged["query"] = payload.get("query") or merged.get("query")
    merged["domain_id"] = domain_id
    merged["column_labels"] = payload.get("column_labels") or merged.get("column_labels") or {}
    merged["sql_query"] = payload.get("sql_query") or merged.get("sql_query")
    if payload.get("insight"):
        merged["insight"] = payload["insight"]
    if new_payload.get("status") == "success":
        merged["chart_type"] = new_payload.get("chart_type") or chart_type
    else:
        merged["chart_type"] = chart_type
    return merged


def _render_domain_suggestions(domain_id: str) -> None:
    """Gợi ý câu hỏi theo domain đang chọn."""
    samples = _DOMAIN_SAMPLE_QUERIES.get(domain_id) or _DOMAIN_SAMPLE_QUERIES.get(
        "finance_vnfdata", []
    )
    st.markdown("**Gợi ý hỏi:**")
    for sample in samples:
        st.markdown(f"- *{sample}*")


def _render_sidebar_health(domain_id: str) -> None:
    """Trạng thái API + DB domain hiện tại."""
    health = _fetch_api_health()
    if health.get("status") == "ok":
        st.caption("🟢 API backend: hoạt động")
    else:
        st.caption("🔴 API backend: không kết nối được")
    try:
        resp = requests.get(f"{API_BASE}/api/v1/health/domains", timeout=5)
        if resp.status_code == 200:
            domains_health = resp.json().get("domains", {})
            info = domains_health.get(domain_id, {})
            if info.get("db_ok"):
                st.caption(f"🟢 DB `{domain_id}`: kết nối OK")
            else:
                st.caption(f"🔴 DB `{domain_id}`: {info.get('detail', 'lỗi')}")
    except Exception:
        st.caption("⚠️ Không kiểm tra được DB domain")


def _handle_domain_switch(domain_id: str, domains: dict[str, str]) -> None:
    """Cảnh báo và xóa báo cáo cũ khi user đổi domain."""
    prev = st.session_state.get("active_domain_id")
    if prev is None:
        st.session_state.active_domain_id = domain_id
        return
    if domain_id == prev:
        return
    old_name = domains.get(prev, prev)
    new_name = domains.get(domain_id, domain_id)
    st.session_state.active_domain_id = domain_id
    st.session_state.latest_report = None
    st.warning(
        f"Đã chuyển từ **{old_name}** sang **{new_name}**. "
        "Báo cáo trước đó đã được xóa — hãy hỏi lại với domain mới."
    )


def _render_report_status_badges(payload: dict[str, Any]) -> None:
    """Hiển thị nguồn kết quả: cache, viz_only, fast-path."""
    badges: list[str] = []
    if payload.get("from_cache"):
        badges.append("⚡ Cache (không gọi LLM/DB)")
    if payload.get("viz_only"):
        badges.append("📊 Chỉ đổi biểu đồ")
    sql = payload.get("sql_query") or ""
    if sql.startswith("(giữ nguyên"):
        badges.append("↻ Tái dùng dữ liệu")
    if badges:
        st.caption(" · ".join(badges))


def _spinner_message(
    domain_id: str,
    user_query: str,
    *,
    reuse_data: list[dict[str, Any]] | None = None,
) -> str:
    """Thông báo tiến trình rõ hơn cho user."""
    cache_key = _query_cache_key(domain_id, user_query)
    if reuse_data is not None:
        return "📊 Đang đổi loại biểu đồ (viz_only — không truy vấn DB lại)..."
    if cache_key in _get_session_query_cache():
        return "⚡ Đang lấy kết quả đã lưu trong phiên..."
    if is_viz_only_request(user_query):
        return "📊 Đang áp dụng loại biểu đồ mới trên dữ liệu hiện có..."
    return (
        "🔄 **Bước 1/2:** Sinh SQL & truy vấn DB → "
        "**Bước 2/2:** AI viết insight (có thể mất 1–3 phút)..."
    )


def _kpi_short_label(col_name: str, labels: dict[str, str] | None = None) -> str:
    """Nhãn KPI ngắn gọn — ưu tiên column_labels từ API."""
    if labels:
        for raw, display in labels.items():
            if raw == col_name or display == col_name:
                short = display.split("(")[0].strip()
                return short if len(short) <= 24 else short[:21] + "…"
    if col_name in _FALLBACK_LABELS:
        short = _FALLBACK_LABELS[col_name].split("(")[0].strip()
        return short if len(short) <= 24 else short[:21] + "…"
    return col_name if len(col_name) <= 20 else col_name[:17] + "…"


def _has_visual_data(payload: dict[str, Any]) -> bool:
    """True khi có dữ liệu hợp lệ để render KPI, bảng và biểu đồ."""
    status = payload.get("status", "success")
    data = payload.get("data") or []
    return status == "success" and len(data) > 0


# ---------------------------------------------------------------------------
# Insight parsing & display (Phase 1 — đủ 7 mục báo cáo LLM)
# ---------------------------------------------------------------------------

# Chỉ tách tại tiêu đề mục đầu dòng — tránh cắt nhầm "xu hướng" trong câu văn
_INSIGHT_SECTION_TITLES = (
    r"Phân tích chi tiết",
    r"Điểm nổi bật",
    r"Xu hướng\s*(?:&|và)\s*biến động",
    r"Phát hiện bất thường",
    r"Rủi ro\s*(?:&|và)\s*giới hạn(?:\s*dữ liệu)?",
    r"Gợi ý theo dõi",
    r"Tóm tắt",
)
_INSIGHT_TITLES_ALT = "|".join(_INSIGHT_SECTION_TITLES)
_INSIGHT_HEADER_SPLIT = re.compile(
    rf"(?:^|\n)\s*(?:\*\*)?\s*"
    rf"({_INSIGHT_TITLES_ALT})"
    r"\s*(?:\*\*)?\s*[:：\-–]+\s*",
    re.IGNORECASE | re.MULTILINE,
)


def _clean_insight_body(text: str) -> str:
    """Bỏ markdown ** thừa và tiêu đề mục lặp trong nội dung."""
    lines: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        stripped = re.sub(
            r"^(?:[-*•]\s*)?(?:\*\*)?\s*"
            r"(?:Phân tích chi tiết|Điểm nổi bật|"
            r"Xu hướng\s*(?:&|và)\s*biến động|Phát hiện bất thường|"
            r"Rủi ro\s*(?:&|và)\s*giới hạn(?:\s*dữ liệu)?|"
            r"Gợi ý theo dõi|Tóm tắt)"
            r"\s*(?:\*\*)?\s*[:：\-–]?\s*",
            "",
            stripped,
            flags=re.IGNORECASE,
        )
        stripped = re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped)
        stripped = stripped.replace("**", "")
        lines.append(stripped)
    return "\n".join(lines).strip()


def _merge_insight_sections(
    sections: list[tuple[str, str, InsightRenderKind]],
) -> list[tuple[str, str, InsightRenderKind]]:
    """Gộp mục trùng nhãn liên tiếp (phòng parser tách đôi)."""
    merged: list[tuple[str, str, InsightRenderKind]] = []
    for label, body, kind in sections:
        clean_body = _clean_insight_body(body)
        if not clean_body:
            continue
        if merged and merged[-1][0] == label:
            prev_label, prev_body, prev_kind = merged[-1]
            merged[-1] = (prev_label, f"{prev_body} {clean_body}".strip(), prev_kind)
        else:
            merged.append((label, clean_body, kind))
    return merged


def _insight_section_meta(title_raw: str) -> tuple[str, InsightRenderKind]:
    """Map tiêu đề mục insight → nhãn hiển thị + kiểu khối Streamlit."""
    norm = _normalize_for_match(title_raw)
    if norm.startswith("tom tat"):
        return "💡 Tóm tắt", "success"
    if "rui ro" in norm or "gioi han" in norm:
        return "⚠️ Rủi ro & giới hạn dữ liệu", "warning"
    if "bat thuong" in norm:
        return "🔍 Phát hiện bất thường", "warning"
    if "diem noi bat" in norm:
        return "⭐ Điểm nổi bật", "info"
    if "phan tich chi tiet" in norm:
        return "📊 Phân tích chi tiết", "info"
    if "xu huong" in norm and "bien dong" in norm:
        return "📈 Xu hướng & biến động", "info"
    if "goi y" in norm:
        return "🎯 Gợi ý theo dõi", "info"
    return f"📌 {title_raw.strip()}", "info"


def _parse_insight_sections(text: str) -> list[tuple[str, str, InsightRenderKind]]:
    """
    Tách insight LLM thành tối đa 7 mục (Tóm tắt → Gợi ý theo dõi).
    Trả về (nhãn có icon, nội dung, kiểu render).
    """
    raw = (text or "").strip()
    if not raw:
        return []

    matches = list(_INSIGHT_HEADER_SPLIT.finditer(raw))
    if not matches:
        return [("📋 Báo cáo phân tích", _clean_insight_body(raw), "info")]

    sections: list[tuple[str, str, InsightRenderKind]] = []
    preamble = raw[: matches[0].start()].strip()
    if preamble and not re.match(
        r"^(báo cáo|bao cao)\s*(phân tích|phan tich)",
        preamble,
        re.IGNORECASE,
    ):
        sections.append(("📋 Tổng quan", preamble, "info"))

    for idx, match in enumerate(matches):
        title_raw = match.group(1).strip()
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw)
        body = raw[body_start:body_end].strip()
        if not body:
            continue
        label, kind = _insight_section_meta(title_raw)
        sections.append((label, body, kind))

    return _merge_insight_sections(sections) or [
        ("📋 Báo cáo phân tích", _clean_insight_body(raw), "info")
    ]


def _render_insight_block(label: str, body: str, kind: InsightRenderKind) -> None:
    """Render một mục insight với màu phù hợp."""
    body = _clean_insight_body(body)
    content = f"**{label}**\n\n{body}"
    if kind == "success":
        st.success(content)
    elif kind == "warning":
        st.warning(content)
    else:
        st.info(content)


def _render_insight(insight: str) -> None:
    """
    Executive Summary — một khối container gọn, mục Tóm tắt nổi bật,
    các mục còn lại trong expander (thay vì 5–7 alert rời).
    """
    sections = _parse_insight_sections(insight)
    if not sections:
        st.info("_Không có insight._")
        return
    if len(sections) == 1 and sections[0][0].startswith("📋"):
        with st.container(border=True):
            st.markdown(_clean_insight_body(insight) or "_Không có insight._")
        return

    primary_idx = 0
    for idx, (label, _, _) in enumerate(sections):
        norm = _normalize_for_match(label)
        if "tom tat" in norm:
            primary_idx = idx
            break

    primary_label, primary_body, primary_kind = sections[primary_idx]
    other_sections = [s for i, s in enumerate(sections) if i != primary_idx]

    with st.container(border=True):
        st.markdown(f"**{primary_label}**")
        body_clean = _clean_insight_body(primary_body)
        if primary_kind == "warning":
            st.warning(body_clean)
        elif primary_kind == "success":
            st.success(body_clean)
        else:
            st.markdown(body_clean)

        if other_sections:
            st.markdown("")
            for label, body, kind in other_sections:
                expanded = kind == "warning" or "bất thường" in label.lower()
                with st.expander(label, expanded=expanded):
                    body_clean = _clean_insight_body(body)
                    if kind == "warning":
                        st.warning(body_clean)
                    elif kind == "success":
                        st.success(body_clean)
                    else:
                        st.markdown(body_clean)


def _render_query_failure(payload: dict[str, Any]) -> None:
    """Phase 2: UX rõ ràng khi SQL lỗi hoặc 0 dòng — kèm failed_sql + error_detail."""
    status = payload.get("status", "success")
    insight = payload.get("insight") or ""
    sql_query = payload.get("sql_query") or ""
    failed_sql = payload.get("failed_sql") or sql_query
    error_detail = payload.get("error_detail") or ""

    if status == "error":
        st.error(
            "Không thể lấy dữ liệu từ câu hỏi này. "
            "AI có thể đã sinh SQL sai (JOIN nhầm bảng, alias hoặc cột không tồn tại)."
        )
        st.warning(
            insight
            or "Hãy thử hỏi ngắn gọn hơn, nêu rõ metric/domain, hoặc dùng câu trong gợi ý sidebar."
        )
        if failed_sql or error_detail:
            with st.expander("🛠️ Xem chi tiết lỗi SQL", expanded=False):
                if error_detail:
                    st.markdown("**Thông báo lỗi từ database / guardrail:**")
                    st.code(error_detail, language="text")
                if failed_sql:
                    st.markdown("**SQL cuối cùng (thất bại):**")
                    st.code(failed_sql, language="sql")
                st.caption(
                    "Gợi ý: tách câu hỏi, bỏ bớt điều kiện, hoặc thử mẫu fast-path "
                    "(vd: «Top 5 vốn hóa HoSE», «So sánh EPS FPT, VCB, HPG»)."
                )
        return

    if status == "empty":
        st.info(insight or "_Truy vấn thành công nhưng không có dữ liệu khớp._")
        if sql_query:
            with st.expander("🔧 SQL đã chạy (0 dòng kết quả)", expanded=False):
                st.code(sql_query, language="sql")
                st.caption(
                    "SQL hợp lệ nhưng không có bản ghi — thử đổi kỳ thời gian, "
                    "điều kiện lọc hoặc mã chứng khoán."
                )


# ---------------------------------------------------------------------------
# Plotly charts (enterprise glow-up — Phase A)
# ---------------------------------------------------------------------------

def _format_x_label(value: Any, x_col: str) -> str:
    """Định dạng trục X — ưu tiên DD/MM/YYYY cho ngày."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if _date_column(pd.DataFrame({x_col: [value]}), []) == x_col:
        try:
            dt = pd.to_datetime(value, errors="coerce")
            if pd.notna(dt):
                return dt.strftime("%d/%m/%Y")
        except (TypeError, ValueError):
            pass
    return str(value)


def _format_hover_value(value: Any, col_name: str) -> str:
    """Giá trị đầy đủ cho tooltip — có dấu phẩy và hậu tố."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    num = float(value)
    fmt = _column_format_type(col_name)
    if fmt == "percent":
        return f"{num:,.2f}%"
    if fmt in ("price", "money"):
        return f"{num:,.0f} VNĐ"
    if fmt == "billions":
        return f"{num:,.2f} tỷ"
    if fmt == "quantity":
        return f"{num:,.0f}"
    if fmt == "ratio":
        return f"{num:,.2f}"
    if abs(num) >= 1_000_000_000:
        return f"{num:,.0f} VNĐ"
    if abs(num) >= 1_000_000:
        return f"{num:,.0f}"
    return f"{num:,.2f}"


def _hovertemplate(y_col: str, x_col: str, is_date_x: bool) -> str:
    """Tooltip sạch — chỉ X và Y, ẩn trace/variable."""
    fmt = _column_format_type(y_col)
    if fmt == "percent":
        y_fmt = "%{y:,.2f}%"
    elif fmt in ("price", "money"):
        y_fmt = "%{y:,.0f} VNĐ"
    elif fmt == "billions":
        y_fmt = "%{y:,.2f} tỷ"
    elif fmt == "quantity":
        y_fmt = "%{y:,.0f}"
    else:
        y_fmt = "%{y:,.2f}"
    x_label = x_col
    if is_date_x:
        return (
            f"<b>{x_label}</b>: %{{x|%d/%m/%Y}}<br>"
            f"<b>{y_col}</b>: {y_fmt}<extra></extra>"
        )
    return f"<b>{x_label}</b>: %{{x}}<br><b>{y_col}</b>: {y_fmt}<extra></extra>"


def _yaxis_tick_settings(
    col_name: str,
    series: pd.Series,
    *,
    zero_base: bool = False,
) -> dict[str, Any]:
    """Cấu hình trục Y: K/M/G hoặc % hoặc tỷ."""
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return {"tickformat": ",.0f", **({"rangemode": "tozero"} if zero_base else {})}

    max_val = float(clean.abs().max())
    fmt_type = _column_format_type(col_name)
    zero_opt: dict[str, Any] = {"rangemode": "tozero"} if zero_base else {}

    if fmt_type == "percent":
        ymax = max(100.0, max_val * 1.05)
        return {"tickformat": ".1f", "ticksuffix": "%", "range": [0, ymax]}
    if fmt_type == "billions":
        return {"tickformat": ",.0f", "ticksuffix": " tỷ", **zero_opt}
    if fmt_type in ("price", "money"):
        if max_val >= 1_000_000:
            return {"tickformat": ".2s", **zero_opt}
        return {"tickformat": ",.0f", "ticksuffix": " VNĐ", **zero_opt}
    if fmt_type == "quantity":
        if max_val >= 1_000_000:
            return {"tickformat": ".2s", **zero_opt}
        return {"tickformat": ",.0f", **zero_opt}
    if max_val >= 1_000_000:
        return {"tickformat": ".2s", **zero_opt}
    return {"tickformat": ",.0f", **zero_opt}


def _bar_text_auto(y_cols: list[str]) -> str | bool:
    """Định dạng nhãn bar — .2s cho số lớn; False nếu cần ghi đè % thủ công."""
    if not y_cols:
        return ".2s"
    if _column_format_type(y_cols[0]) == "percent":
        return False
    return ".2s"


def _apply_trace_hover(fig: go.Figure, x_col: str, is_date_x: bool) -> None:
    """Gắn hovertemplate cho từng trace."""
    for trace in fig.data:
        y_name = trace.name or ""
        if hasattr(trace, "y") and y_name:
            trace.hovertemplate = _hovertemplate(y_name, x_col, is_date_x)


def _apply_yaxis_format(
    fig: go.Figure,
    y_cols: list[str],
    plot_df: pd.DataFrame,
    secondary_y: bool = False,
    *,
    zero_base: bool = False,
) -> None:
    """Áp dụng format trục Y chính và phụ."""
    if y_cols:
        primary = y_cols[0]
        if primary in plot_df.columns:
            settings = _yaxis_tick_settings(
                primary, plot_df[primary], zero_base=zero_base
            )
            fig.update_yaxes(title_text=primary, secondary_y=False, **settings)

    if secondary_y and len(y_cols) > 1:
        secondary = y_cols[1]
        if secondary in plot_df.columns:
            settings = _yaxis_tick_settings(
                secondary, plot_df[secondary], zero_base=zero_base
            )
            fig.update_yaxes(title_text=secondary, secondary_y=True, **settings)


def _style_figure(fig: go.Figure, title: str) -> go.Figure:
    """Layout chung — phong cách Power BI (nền trong suốt, legend trên, grid nhẹ)."""
    fig.update_layout(
        title=dict(text=title, x=0.0, xanchor="left", font=dict(size=15, color="#0F172A")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=16, r=16, t=48, b=64),
        font=dict(family="Segoe UI, system-ui, sans-serif", size=12, color="#334155"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(size=11, color="#334155"),
        ),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor="#0078D4",
            font=dict(size=13, color="#0F172A", family="Segoe UI, system-ui, sans-serif"),
        ),
        bargap=0.2,
        bargroupgap=0.06,
        colorway=_COLOR_SEQ,
    )
    return fig


def _apply_axis_polish(fig: go.Figure, *, horizontal: bool = False, n_categories: int = 0) -> None:
    """Trục X ẩn lưới; trục giá trị lưới nhạt — giống Power BI."""
    grid = dict(showgrid=True, gridcolor="rgba(0,0,0,0.05)", zeroline=False, showline=False)
    no_grid = dict(showgrid=False, zeroline=False, showline=False)

    if horizontal:
        fig.update_yaxes(tickfont=dict(size=11), **no_grid)
        fig.update_xaxes(tickfont=dict(size=11), **grid)
    else:
        tick_angle = -35 if n_categories > 5 else 0
        fig.update_xaxes(
            tickangle=tick_angle,
            tickfont=dict(size=11),
            **no_grid,
        )
        fig.update_yaxes(tickfont=dict(size=11), **grid)


def _apply_bar_labels(
    fig: go.Figure,
    plot_df: pd.DataFrame,
    y_cols: list[str],
    *,
    horizontal: bool = False,
    max_labels: int = 12,
) -> None:
    """Tinh chỉnh nhãn bar — text_auto từ px.bar + vị trí outside/inside."""
    if plot_df.empty or len(plot_df) > max_labels:
        return

    for trace in fig.data:
        if getattr(trace, "type", None) != "bar":
            continue
        col_name = str(trace.name or (y_cols[0] if y_cols else ""))
        fmt = _column_format_type(col_name)
        textposition = "inside" if horizontal else "outside"
        updates: dict[str, Any] = dict(
            textposition=textposition,
            textfont=dict(size=10, color="#475569"),
            cliponaxis=False,
            marker=dict(cornerradius=4),
        )
        # Cột %: ghi đè text_auto để hiện đúng định dạng phần trăm
        if fmt == "percent":
            vals = trace.x if horizontal else trace.y
            raw_values = list(vals) if vals is not None else []
            updates["text"] = [_format_chart_label(v, col_name) for v in raw_values]
        trace.update(**updates)


def _apply_line_polish(fig: go.Figure) -> None:
    """Line/area — marker tròn, viền trắng nổi bật trên nền."""
    for trace in fig.data:
        trace_type = getattr(trace, "type", None)
        if trace_type == "scatter" and trace.mode and "lines" in trace.mode:
            trace.update(
                mode="lines+markers",
                line=dict(width=2.5),
                marker=dict(size=7, line=dict(color="white", width=2)),
            )


def _identify_combo_cols(
    y_cols: list[str],
) -> tuple[str, str, bool]:
    """
    Trả về (price_col, volume_col, volume_is_bar).
    volume_is_bar=True khi cột thứ 2 là khối lượng / quantity.
    """
    if len(y_cols) < 2:
        return y_cols[0], y_cols[0], False

    price_kw = ("gia", "dong", "price", "eps", "dieuchinh", "dieu chinh")
    vol_kw = ("khoi luong", "khối lượng", "volume", "sl gd")

    def _is_vol(name: str) -> bool:
        norm = _normalize_for_match(name)
        return _column_format_type(name) == "quantity" or any(k in norm for k in vol_kw)

    def _is_price(name: str) -> bool:
        norm = _normalize_for_match(name)
        ft = _column_format_type(name)
        return ft in ("price", "money") or any(k in norm for k in price_kw)

    c0, c1 = y_cols[0], y_cols[1]
    if _is_price(c0) and _is_vol(c1):
        return c0, c1, True
    if _is_price(c1) and _is_vol(c0):
        return c1, c0, True
    if _is_vol(c1):
        return c0, c1, True
    return c0, c1, False


def _build_combo_figure(
    df: pd.DataFrame,
    x_col: str,
    price_col: str,
    volume_col: str,
    title: str,
    volume_as_bar: bool = True,
) -> go.Figure:
    """
    Combo Chart (US2): Giá = Line (trục Y trái), Khối lượng = Bar (trục Y phải).
    """
    is_date_x = _date_column(df, _numeric_columns(df)) == x_col
    plot_x = df[x_col]
    if is_date_x:
        plot_x = pd.to_datetime(df[x_col], errors="coerce")

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=plot_x,
            y=df[price_col],
            name=price_col,
            mode="lines+markers",
            line=dict(color=_COLOR_SEQ[0], width=2.5),
            marker=dict(size=8, color=_COLOR_SEQ[0], line=dict(color="white", width=2)),
            hovertemplate=_hovertemplate(price_col, x_col, is_date_x),
        ),
        secondary_y=False,
    )

    if volume_as_bar:
        fig.add_trace(
            go.Bar(
                x=plot_x,
                y=df[volume_col],
                name=volume_col,
                marker=dict(color=_COLOR_SEQ[2], opacity=0.55, cornerradius=3),
                text=[_format_chart_label(v, volume_col) for v in df[volume_col]],
                textposition="outside",
                textfont=dict(size=9, color="#475569"),
                hovertemplate=_hovertemplate(volume_col, x_col, is_date_x),
            ),
            secondary_y=True,
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=plot_x,
                y=df[volume_col],
                name=volume_col,
                mode="lines+markers",
                line=dict(color=_COLOR_SEQ[2], width=2, dash="dot"),
                marker=dict(size=6, line=dict(color="white", width=2)),
                hovertemplate=_hovertemplate(volume_col, x_col, is_date_x),
            ),
            secondary_y=True,
        )

    if is_date_x:
        fig.update_xaxes(title_text=x_col, tickformat="%d/%m/%Y")
    else:
        fig.update_xaxes(title_text=x_col)

    _apply_yaxis_format(fig, [price_col, volume_col], df, secondary_y=True)
    fig.update_layout(barmode="overlay")
    _apply_axis_polish(fig, horizontal=False, n_categories=len(df))
    return _style_figure(fig, title)


def _build_dual_axis_line_figure(
    df: pd.DataFrame,
    x_col: str,
    primary_col: str,
    secondary_col: str,
    title: str,
) -> go.Figure:
    """Line 2 trục Y khi không dùng combo bar."""
    is_date_x = _date_column(df, _numeric_columns(df)) == x_col
    plot_x = pd.to_datetime(df[x_col], errors="coerce") if is_date_x else df[x_col]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=plot_x,
            y=df[primary_col],
            name=primary_col,
            mode="lines+markers",
            line=dict(color=_COLOR_SEQ[0], width=2.5),
            marker=dict(size=7, line=dict(color="white", width=2)),
            hovertemplate=_hovertemplate(primary_col, x_col, is_date_x),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=plot_x,
            y=df[secondary_col],
            name=secondary_col,
            mode="lines+markers",
            line=dict(color=_COLOR_SEQ[2], width=2, dash="dot"),
            marker=dict(size=6, line=dict(color="white", width=2)),
            hovertemplate=_hovertemplate(secondary_col, x_col, is_date_x),
        ),
        secondary_y=True,
    )
    if is_date_x:
        fig.update_xaxes(title_text=x_col, tickformat="%d/%m/%Y")
    else:
        fig.update_xaxes(title_text=x_col)
    _apply_yaxis_format(fig, [primary_col, secondary_col], df, secondary_y=True)
    _apply_axis_polish(fig, horizontal=False, n_categories=len(df))
    return _style_figure(fig, title)


def _build_figure(
    df: pd.DataFrame,
    chart_type: str,
    title: str = "",
    query: str = "",
) -> go.Figure | None:
    num_cols = _numeric_columns(df)
    if not num_cols and chart_type != "table":
        return None

    x_col = _chart_x_column(df, num_cols)
    y_cols = _pick_chart_y_columns(df, num_cols, chart_type, query=query)
    chart_title = title or "Biểu đồ phân tích"
    plot_df = _sort_df_for_chart(df, x_col, query=query, y_cols=y_cols, chart_type=chart_type)
    is_date_x = bool(x_col and _date_column(plot_df, num_cols) == x_col)

    fig: go.Figure | None = None

    # --- Combo: Line giá + Bar khối lượng ---
    if chart_type == "combo" and x_col and len(y_cols) >= 2:
        price_col, vol_col, vol_is_bar = _identify_combo_cols(y_cols)
        return _build_combo_figure(
            plot_df, x_col, price_col, vol_col, chart_title, volume_as_bar=vol_is_bar
        )

    # --- Fallback combo khi line/area + 2 cột lệch đơn vị ---
    if chart_type in ("line", "area") and x_col and len(y_cols) == 2:
        p_fmt = _column_format_type(y_cols[0])
        s_fmt = _column_format_type(y_cols[1])
        price_col, vol_col, vol_is_bar = _identify_combo_cols(y_cols)
        if vol_is_bar:
            return _build_combo_figure(
                plot_df, x_col, price_col, vol_col, chart_title, volume_as_bar=True
            )
        if p_fmt != s_fmt:
            return _build_dual_axis_line_figure(
                plot_df, x_col, y_cols[0], y_cols[1], chart_title
            )

    if chart_type == "pie" and x_col and y_cols:
        # Unpivot 2 cột số trên 1 dòng → pie (cơ cấu tài sản)
        if len(y_cols) >= 2 and plot_df[x_col].nunique(dropna=True) == 1:
            row = plot_df.iloc[0]
            pie_labels = y_cols
            pie_values = [row[c] for c in y_cols]
            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=pie_labels,
                        values=pie_values,
                        hole=0.55,
                        marker=dict(colors=_COLOR_SEQ, line=dict(color="#FFFFFF", width=2)),
                        textinfo="label+percent",
                        textposition="inside",
                        textfont=dict(size=11, color="#FFFFFF"),
                        hovertemplate="<b>%{label}</b><br>%{value:,.2f}<br>%{percent}<extra></extra>",
                    )
                ]
            )
        else:
            fig = px.pie(
                plot_df,
                names=x_col,
                values=y_cols[0],
                hole=0.55,
                color_discrete_sequence=_COLOR_SEQ,
            )
            fig.update_traces(
                textinfo="label+percent",
                textposition="inside",
                textfont=dict(size=11, color="#FFFFFF"),
                marker=dict(line=dict(color="#FFFFFF", width=2)),
                hovertemplate="<b>%{label}</b><br>%{value:,.2f}<br>%{percent}<extra></extra>",
            )
    elif chart_type == "line" and x_col and y_cols:
        fig = px.line(
            plot_df,
            x=x_col,
            y=y_cols,
            markers=True,
            color_discrete_sequence=_COLOR_SEQ,
        )
        if is_date_x:
            fig.update_xaxes(tickformat="%d/%m/%Y")
        _apply_trace_hover(fig, x_col, is_date_x)
        _apply_yaxis_format(fig, y_cols, plot_df)
        _apply_line_polish(fig)
        _apply_axis_polish(fig, horizontal=False, n_categories=len(plot_df))
    elif chart_type == "area" and x_col and y_cols:
        fig = px.area(
            plot_df,
            x=x_col,
            y=y_cols,
            color_discrete_sequence=_COLOR_SEQ,
        )
        if is_date_x:
            fig.update_xaxes(tickformat="%d/%m/%Y")
        _apply_trace_hover(fig, x_col, is_date_x)
        _apply_yaxis_format(fig, y_cols, plot_df)
        _apply_line_polish(fig)
        fig.update_traces(fillcolor="rgba(0,120,212,0.12)")
        _apply_axis_polish(fig, horizontal=False, n_categories=len(plot_df))
    elif chart_type == "bar" and num_cols:
        data_rows = plot_df.to_dict("records")
        use_stacked = (
            x_col
            and len(y_cols) == 2
            and should_use_stacked_100_percent(data_rows, query, y_cols, x_col)
        )
        use_horizontal = (
            x_col
            and not use_stacked
            and should_use_horizontal_bar(data_rows, x_col)
        )

        if use_stacked and x_col:
            # Cột chồng 100% — so sánh tỷ trọng 2 thành phần (Power BI style)
            melt_df = plot_df.melt(
                id_vars=[x_col],
                value_vars=y_cols,
                var_name="_series",
                value_name="_value",
            )
            fig = px.bar(
                melt_df,
                y=x_col,
                x="_value",
                color="_series",
                orientation="h",
                barmode="stack",
                barnorm="percent",
                text_auto=".1%",
                color_discrete_sequence=_COLOR_SEQ,
            )
            fig.update_traces(textposition="inside", marker=dict(cornerradius=3))
            fig.update_layout(xaxis_tickformat=".0%")
            _apply_axis_polish(fig, horizontal=True, n_categories=len(plot_df))
        elif use_horizontal and x_col:
            fig = px.bar(
                plot_df,
                y=x_col,
                x=y_cols if len(y_cols) > 1 else y_cols[0],
                orientation="h",
                barmode="group" if len(y_cols) > 1 else "relative",
                text_auto=_bar_text_auto(y_cols),
                color_discrete_sequence=_COLOR_SEQ,
            )
            _apply_trace_hover(fig, x_col, False)
            _apply_bar_labels(fig, plot_df, y_cols, horizontal=True)
            if len(y_cols) == 1 and y_cols[0] in plot_df.columns:
                _apply_yaxis_format(fig, y_cols, plot_df, zero_base=True)
            _apply_axis_polish(fig, horizontal=True, n_categories=len(plot_df))
        elif x_col:
            fig = px.bar(
                plot_df,
                x=x_col,
                y=y_cols,
                barmode="group",
                text_auto=_bar_text_auto(y_cols),
                color_discrete_sequence=_COLOR_SEQ,
            )
            _apply_trace_hover(fig, x_col, False)
            _apply_bar_labels(fig, plot_df, y_cols, horizontal=False)
            _apply_yaxis_format(fig, y_cols, plot_df, zero_base=True)
            _apply_axis_polish(fig, horizontal=False, n_categories=len(plot_df))
        else:
            fig = px.bar(
                plot_df,
                y=y_cols,
                text_auto=_bar_text_auto(y_cols),
                color_discrete_sequence=_COLOR_SEQ,
            )
            _apply_trace_hover(fig, x_col or "", False)
            _apply_bar_labels(fig, plot_df, y_cols, horizontal=False)
            _apply_yaxis_format(fig, y_cols, plot_df, zero_base=True)

    if fig is None:
        return None

    fig.update_xaxes(title_text=x_col or "")
    return _style_figure(fig, chart_title)


def _figure_for_word_export(
    df: pd.DataFrame,
    chart_type: str,
    query: str,
    payload: dict[str, Any],
    display_fig: go.Figure | None,
) -> go.Figure | None:
    """
    Figure dùng cho Word — ưu tiên chart đang hiển thị;
    nếu None (table / lỗi build) thì thử bar → line → chart_type gốc từ API.
    """
    if display_fig is not None:
        return display_fig

    fallback_types: list[str] = []
    if chart_type != "table":
        fallback_types.append(chart_type)
    api_chart = payload.get("chart_type") or "bar"
    if api_chart not in fallback_types and api_chart != "table":
        fallback_types.append(api_chart)
    for alt in ("bar", "line", "pie", "area", "combo"):
        if alt not in fallback_types:
            fallback_types.append(alt)

    for ctype in fallback_types:
        fig = _build_figure(
            df,
            ctype,
            title=_CHART_OPTIONS.get(ctype, "Biểu đồ phân tích"),
            query=query,
        )
        if fig is not None:
            return fig
    return None


# ---------------------------------------------------------------------------
# KPI + Dashboard render
# ---------------------------------------------------------------------------

def _render_kpi_card(label: str, value: str, accent: str = "#0078D4") -> None:
    """Thẻ KPI kiểu Power BI — nhãn xám trên, số đậm to dưới."""
    safe_label = label.replace("<", "&lt;").replace(">", "&gt;")
    safe_value = value.replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f"""
        <div style="
            border: 1px solid #E2E8F0;
            border-left: 4px solid {accent};
            border-radius: 8px;
            padding: 14px 16px;
            background: #FFFFFF;
            min-height: 90px;
            box-shadow: 0 1px 2px rgba(15,23,42,0.04);
        ">
            <div style="color:#64748B;font-size:0.8rem;font-weight:500;
                        margin-bottom:8px;line-height:1.3;">
                {safe_label}
            </div>
            <div style="color:#0F172A;font-size:1.5rem;font-weight:700;
                        line-height:1.15;font-family:'Segoe UI',system-ui,sans-serif;">
                {safe_value}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpi_row(items: list[tuple[str, str]]) -> None:
    """Hiển thị tối đa 4 KPI trên một hàng."""
    cols = st.columns(min(4, len(items)))
    for idx, (label, value) in enumerate(items[:4]):
        with cols[idx]:
            _render_kpi_card(label, value, _KPI_ACCENTS[idx % len(_KPI_ACCENTS)])


def _render_kpis(
    df: pd.DataFrame,
    query: str = "",
    column_labels: dict[str, str] | None = None,
) -> None:
    labels = column_labels or {}
    num_cols = _numeric_columns(df)
    if not num_cols:
        _render_kpi_row([
            ("Số dòng", f"{len(df):,}"),
            ("Số cột", f"{len(df.columns):,}"),
        ])
        return

    date_col = _date_column(df, num_cols)
    close_col = _find_col_by_keywords(num_cols, ("gia dong", "dong cua", "dong cửa"))
    vol_col = _find_col_by_keywords(num_cols, ("khoi luong", "khối lượng"))
    pct_col = _find_col_by_keywords(num_cols, ("bien dong", "biến động"))

    kpi_items: list[tuple[str, str]] = [("Số bản ghi", f"{len(df):,}")]

    # Time-series chứng khoán / theo ngày
    if date_col and close_col:
        close = pd.to_numeric(df[close_col], errors="coerce").dropna()
        if not close.empty:
            kpi_items.append(
                ("Giá đóng TB", _format_kpi_number(float(close.mean()), close_col))
            )
            kpi_items.append(
                ("Giá đóng cao nhất", _format_kpi_number(float(close.max()), close_col))
            )
            if pct_col:
                pct_series = pd.to_numeric(df[pct_col], errors="coerce").dropna()
                latest_pct = float(pct_series.iloc[-1]) if not pct_series.empty else 0.0
                kpi_items.append(
                    ("Biến động phiên cuối", _format_kpi_number(latest_pct, pct_col))
                )
            elif vol_col:
                vol = pd.to_numeric(df[vol_col], errors="coerce").dropna()
                kpi_items.append(
                    ("KL GD TB", _format_kpi_number(float(vol.mean()), vol_col))
                )
            else:
                kpi_items.append(
                    ("Giá đóng thấp nhất", _format_kpi_number(float(close.min()), close_col))
                )
            _render_kpi_row(kpi_items)
            return

    # Cột % / tiến độ
    pct_cols = [c for c in num_cols if _is_percent_col(c)]
    if pct_cols:
        primary = pct_cols[0]
        series = pd.to_numeric(df[primary], errors="coerce").dropna()
        if not series.empty:
            lbl = _kpi_short_label(primary, labels)
            kpi_items.extend([
                (f"TB · {lbl}", _format_kpi_number(float(series.mean()), primary)),
                (f"Cao nhất · {lbl}", _format_kpi_number(float(series.max()), primary)),
                (f"Thấp nhất · {lbl}", _format_kpi_number(float(series.min()), primary)),
            ])
            _render_kpi_row(kpi_items)
            return

    # Bảng tổng hợp (mỗi dòng một đối tượng)
    primary = num_cols[0]
    series = pd.to_numeric(df[primary], errors="coerce").dropna()
    if series.empty:
        return

    lbl = _kpi_short_label(primary, labels)
    fmt = _column_format_type(primary)
    if fmt in ("quantity", "billions", "money") and len(df) > 1:
        kpi_items.extend([
            (f"Tổng · {lbl}", _format_kpi_number(float(series.sum()), primary)),
            (f"TB · {lbl}", _format_kpi_number(float(series.mean()), primary)),
            (f"Cao nhất · {lbl}", _format_kpi_number(float(series.max()), primary)),
        ])
    else:
        kpi_items.extend([
            (f"TB · {lbl}", _format_kpi_number(float(series.mean()), primary)),
            (f"Cao nhất · {lbl}", _format_kpi_number(float(series.max()), primary)),
            (f"Thấp nhất · {lbl}", _format_kpi_number(float(series.min()), primary)),
        ])
    _render_kpi_row(kpi_items)


def _render_dashboard(
    payload: dict[str, Any],
    key_prefix: str = "dash",
    domain_id: str = "",
    message_index: int | None = None,
) -> None:
    """
    Dynamic Dashboard: Insight → KPI → (Bảng | Biểu đồ) side-by-side.
    Chạy NGOÀI st.chat_message để layout cột ổn định.
    message_index: cập nhật payload trong messages khi đổi biểu đồ (giữ lịch sử).
    """
    query = payload.get("query") or ""
    if query:
        st.caption(f"Câu hỏi: _{query}_")

    _render_report_status_badges(payload)

    status = payload.get("status", "success")
    insight = payload.get("insight") or ""
    sql_query = payload.get("sql_query") or ""

    # 1) Executive Insight / thông báo graceful
    st.markdown("#### Tóm tắt điều hành")
    if status == "error" or status == "empty" or not _has_visual_data(payload):
        _render_query_failure(payload)
        if not _has_visual_data(payload):
            return
    else:
        _render_insight(insight)

    labels: dict[str, str] = payload.get("column_labels") or {}
    df = _rename_df(pd.DataFrame(payload.get("data") or []), labels)

    # 2) KPI row
    st.markdown("#### Chỉ số nhanh")
    _render_kpis(df, query=query, column_labels=labels)
    st.markdown("")

    # 3) Chọn loại biểu đồ — đổi sẽ gọi API viz_only
    default_chart = payload.get("chart_type") or "bar"
    if default_chart not in _CHART_OPTIONS:
        default_chart = "bar"
    options = list(_CHART_OPTIONS.keys())
    default_idx = options.index(default_chart)

    chart_type = st.selectbox(
        "Loại biểu đồ",
        options=options,
        format_func=lambda k: _CHART_OPTIONS[k],
        index=default_idx,
        key=f"chart_sel_{key_prefix}",
    )

    effective_domain = domain_id or payload.get("domain_id") or ""
    if (
        chart_type != default_chart
        and status == "success"
        and payload.get("data")
        and effective_domain
    ):
        sync_key = f"chart_sync_{key_prefix}"
        if st.session_state.get(sync_key) != chart_type:
            with st.spinner("Đang đồng bộ loại biểu đồ với backend..."):
                updated = _sync_chart_via_api(payload, chart_type, effective_domain)
            resolved = updated.get("chart_type") or chart_type
            st.session_state[sync_key] = resolved
            st.session_state[f"chart_sel_{key_prefix}"] = resolved
            st.session_state.latest_report = updated
            if (
                message_index is not None
                and 0 <= message_index < len(st.session_state.messages)
            ):
                st.session_state.messages[message_index]["payload"] = updated
            st.rerun()
    elif chart_type == default_chart:
        st.session_state.pop(f"chart_sync_{key_prefix}", None)

    fig: go.Figure | None = None
    if chart_type != "table":
        fig = _build_figure(
            df,
            chart_type,
            title=_CHART_OPTIONS[chart_type],
            query=query,
        )

    # 4) Bảng | Biểu đồ — side by side (4:6)
    col_table, col_chart = st.columns([4, 6], gap="large")

    with col_table:
        st.markdown("#### Dữ liệu")
        column_config = _build_column_config(df)
        df_kwargs: dict[str, Any] = {
            "use_container_width": True,
            "height": 360,
        }
        if column_config:
            df_kwargs["column_config"] = column_config
        st.dataframe(df, **df_kwargs)
        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
        btn_csv, btn_word = st.columns(2)
        with btn_csv:
            st.download_button(
                label="⬇️ Tải CSV",
                data=csv_bytes,
                file_name="bi_export.csv",
                mime="text/csv",
                key=f"csv_{key_prefix}",
                use_container_width=True,
            )
        with btn_word:
            if payload.get("status") == "success":
                try:
                    export_fig = _figure_for_word_export(
                        df, chart_type, query, payload, fig
                    )
                    word_bytes, chart_in_word = create_word_report(
                        query=query,
                        insight_text=insight,
                        dataframe=df,
                        figure=export_fig,
                    )
                    st.download_button(
                        label="📄 Tải Báo cáo (Word)",
                        data=word_bytes,
                        file_name="bao_cao_phan_tich.docx",
                        mime=(
                            "application/vnd.openxmlformats-officedocument"
                            ".wordprocessingml.document"
                        ),
                        key=f"word_{key_prefix}",
                        use_container_width=True,
                    )
                    if export_fig is None:
                        st.caption(
                            "⚠️ Word không có biểu đồ — không build được figure từ dữ liệu."
                        )
                    elif not chart_in_word:
                        if not is_kaleido_available():
                            st.caption(
                                "⚠️ Word không có ảnh chart — chạy: "
                                "`pip install -U kaleido plotly` rồi restart Streamlit."
                            )
                        else:
                            st.caption(
                                "⚠️ Word không nhúng được ảnh chart — thử đổi sang Bar/Line "
                                "hoặc restart app sau khi cài kaleido."
                            )
                    else:
                        st.caption("✅ Báo cáo Word gồm insight + biểu đồ + bảng số liệu.")
                except Exception as exc:
                    st.caption(f"Không tạo được file Word: {exc}")

    with col_chart:
        st.markdown("#### Trực quan hóa")
        if chart_type == "table":
            st.caption("Đã chọn chỉ hiển thị bảng — biểu đồ được ẩn.")
        elif fig is not None:
            with st.container(border=True):
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"plot_{key_prefix}_{chart_type}",
                    config=_PLOTLY_CONFIG,
                )
        else:
            st.warning("Không đủ cột phù hợp cho loại biểu đồ này. Thử Cột hoặc Đường.")

    # 5) SQL ẩn
    with st.expander("🔧 Xem câu lệnh SQL"):
        st.code(sql_query, language="sql")

    # 6) Narrative Planner — Viết Bài Báo (chỉ khi có dữ liệu thành công)
    if status == "success" and payload.get("data"):
        st.markdown("---")
        st.markdown("#### 📰 Viết bài báo phân tích")
        st.caption(
            "Narrative Planner (Qwen): lập dàn ý → viết từng mục → hoàn thiện bài báo. "
            "Chỉ chạy khi bạn bấm nút — không làm chậm luồng xem dashboard."
        )
        article_key = f"article_{key_prefix}"
        gen_col, clear_col = st.columns([3, 1])
        with gen_col:
            write_clicked = st.button(
                "📝 Viết Bài Báo",
                key=f"btn_write_article_{key_prefix}",
                use_container_width=True,
                type="primary",
            )
        with clear_col:
            if st.button(
                "Xóa bài",
                key=f"btn_clear_article_{key_prefix}",
                use_container_width=True,
            ):
                st.session_state.pop(article_key, None)
                st.rerun()

        if write_clicked:
            with st.spinner(
                "Đang lập dàn ý và viết bài báo (có thể mất 1–3 phút)..."
            ):
                article_resp = _call_generate_article_api(
                    domain_id=effective_domain or payload.get("domain_id") or "",
                    question=query,
                    data=list(payload.get("data") or []),
                    insight_summary=insight,
                )
            if article_resp.get("error"):
                st.warning(article_resp["error"])
            else:
                st.session_state[article_key] = article_resp
                st.rerun()

        article_payload = st.session_state.get(article_key)
        if article_payload and not article_payload.get("error"):
            md = article_payload.get("article_markdown") or ""
            wc = article_payload.get("word_count") or 0
            outline = article_payload.get("outline") or {}
            style = outline.get("style") or article_payload.get("style") or "bi"
            parts = split_article_markdown(md)
            st.success(
                f"Đã viết xong · ~{wc} từ"
                + (" · kiểu Vietstock" if style == "vietstock" else "")
                + (
                    f" · góc bài: {outline.get('angle')}"
                    if outline.get("angle")
                    else ""
                )
            )
            with st.expander("📋 Dàn ý (Narrative Planner)", expanded=False):
                st.json(outline)

            # Tiêu đề + lead
            if parts["title"]:
                st.markdown(f"# {parts['title']}")
            if parts["lead"]:
                st.markdown(parts["lead"])

            # Biểu đồ xen giữa lead và body (như Vietstock)
            export_fig = _figure_for_word_export(
                df, chart_type, query, payload, fig
            )
            if export_fig is not None:
                st.markdown("#### Biểu đồ")
                with st.container(border=True):
                    st.plotly_chart(
                        export_fig,
                        use_container_width=True,
                        key=f"article_plot_{key_prefix}",
                        config=_PLOTLY_CONFIG,
                    )
                st.caption("Biểu đồ đính kèm bài báo (cùng dữ liệu dashboard).")
            else:
                st.caption(
                    "Không có biểu đồ để chèn vào bài — thử chọn Bar/Line trên dashboard."
                )

            if parts["body"]:
                st.markdown(parts["body"])
            elif not parts["lead"] and not parts["title"]:
                st.markdown(md)

            dl_md, dl_word = st.columns(2)
            with dl_md:
                st.download_button(
                    label="⬇️ Tải Markdown",
                    data=md.encode("utf-8"),
                    file_name="bai_bao_phan_tich.md",
                    mime="text/markdown",
                    key=f"md_article_{key_prefix}",
                    use_container_width=True,
                )
            with dl_word:
                try:
                    word_bytes, chart_in_word = create_article_word(
                        query=query,
                        article_markdown=md,
                        dataframe=df,
                        figure=export_fig,
                        outline=outline,
                        chart_caption="Biểu đồ phân tích từ dữ liệu truy vấn",
                    )
                    st.download_button(
                        label="📄 Tải Bài báo (Word)",
                        data=word_bytes,
                        file_name="bai_bao_phan_tich.docx",
                        mime=(
                            "application/vnd.openxmlformats-officedocument"
                            ".wordprocessingml.document"
                        ),
                        key=f"word_article_{key_prefix}",
                        use_container_width=True,
                    )
                    if chart_in_word:
                        st.caption("✅ Word gồm lead + biểu đồ + nội dung + bảng.")
                    elif not is_kaleido_available():
                        st.caption(
                            "⚠️ Word chưa có ảnh — `pip install -U kaleido plotly` rồi restart."
                        )
                    else:
                        st.caption("⚠️ Word chưa nhúng được ảnh biểu đồ.")
                except Exception as exc:
                    st.caption(f"Không tạo được Word từ bài báo: {exc}")


def _render_feature_highlight(
    icon: str,
    title: str,
    description: str,
    accent: str,
) -> None:
    """Thẻ giới thiệu tính năng — đồng bộ phong cách KPI Enterprise."""
    safe_title = title.replace("<", "&lt;").replace(">", "&gt;")
    safe_desc = description.replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f"""
        <div style="
            border: 1px solid #E2E8F0;
            border-top: 3px solid {accent};
            border-radius: 10px;
            padding: 20px 18px;
            background: linear-gradient(180deg, #F8FAFC 0%, #FFFFFF 100%);
            min-height: 148px;
            height: 100%;
            box-shadow: 0 1px 3px rgba(15,23,42,0.05);
        ">
            <div style="font-size:1.75rem;margin-bottom:10px;line-height:1;">
                {icon}
            </div>
            <div style="color:#0F172A;font-size:1rem;font-weight:600;
                        margin-bottom:8px;line-height:1.35;">
                {safe_title}
            </div>
            <div style="color:#64748B;font-size:0.875rem;line-height:1.55;">
                {safe_desc}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_empty_dashboard_hero() -> None:
    """Hero section khi chưa có báo cáo — Empty State kiểu Enterprise Dashboard."""
    with st.container(border=True):
        st.markdown("## 🤖 Chào mừng đến với AI BI Smart Workspace")
        st.caption(
            "Trợ lý phân tích dữ liệu tự động. Vui lòng nhập yêu cầu vào ô chat bên dưới để bắt đầu."
        )
        st.markdown("")

        col_speed, col_chart, col_export = st.columns(3, gap="medium")
        with col_speed:
            _render_feature_highlight(
                "⚡",
                "Xử lý Tốc độ",
                "Fast-path + Router Qwen + SQLCoder — chuyển câu hỏi thành SQL và truy xuất dữ liệu.",
                "#2563EB",
            )
        with col_chart:
            _render_feature_highlight(
                "📈",
                "Biểu đồ Thông minh",
                "Tự động nhận diện dữ liệu và vẽ biểu đồ đa chiều Plotly.",
                "#7C3AED",
            )
        with col_export:
            _render_feature_highlight(
                "📰",
                "Viết Bài Báo",
                "Narrative Planner lập dàn ý và viết bài phân tích hoàn chỉnh (Markdown/Word).",
                "#059669",
            )


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI BI Smart",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("AI BI Smart")
st.caption("Conversational Analytics · Dynamic Dashboard chuẩn doanh nghiệp")

with st.sidebar:
    st.header("Cấu hình")
    domains = _load_domains()
    domain_id = st.selectbox(
        "Domain",
        options=list(domains.keys()),
        format_func=lambda k: f"{domains[k]} ({k})",
    )
    _handle_domain_switch(domain_id, domains)
    if st.button("Xóa lịch sử & dashboard", use_container_width=True):
        st.session_state.messages = []
        st.session_state.latest_report = None
        st.session_state.query_answer_cache = {}
        # Xóa bài báo Narrative Planner đã cache trong session
        for k in list(st.session_state.keys()):
            if str(k).startswith("article_"):
                del st.session_state[k]
        st.rerun()
    _render_domain_suggestions(domain_id)
    st.divider()
    _render_sidebar_health(domain_id)
    st.caption(f"API: `{API_BASE}`")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "latest_report" not in st.session_state:
    st.session_state.latest_report = None

# ----- Hội thoại: mỗi câu giữ báo cáo/biểu đồ riêng (không ghi đè) -----
st.markdown("### 💬 Hội thoại & báo cáo")
if not st.session_state.messages:
    _render_empty_dashboard_hero()
else:
    report_n = 0
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg.get("content") or "")
        if msg.get("role") == "assistant" and msg.get("payload"):
            report_n += 1
            with st.container(border=True):
                st.markdown(f"##### 📊 Báo cáo #{report_n}")
                _render_dashboard(
                    msg["payload"],
                    key_prefix=f"turn_{idx}",
                    domain_id=domain_id,
                    message_index=idx,
                )

# ----- Chat input -----
if user_query := st.chat_input("Nhập câu hỏi phân tích dữ liệu..."):
    st.session_state.messages.append({"role": "user", "content": user_query})

    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        history = _build_api_history(st.session_state.messages)
        reuse = None
        if is_viz_only_request(user_query):
            reuse = _last_data_from_history(st.session_state.messages)
        spinner_msg = _spinner_message(domain_id, user_query, reuse_data=reuse)
        with st.spinner(spinner_msg):
            payload = _fetch_chat_cached(domain_id, user_query, history, reuse_data=reuse)
            payload["query"] = user_query
            payload["domain_id"] = domain_id

            status = payload.get("status", "success")
            if status == "error":
                brief = (
                    "⚠️ Không thể tạo báo cáo. Xem chi tiết lỗi SQL "
                    "trong **Báo cáo** ngay dưới tin nhắn này."
                )
            elif status == "empty":
                brief = (
                    "ℹ️ Truy vấn thành công nhưng không có dữ liệu. "
                    "Xem chi tiết trong **Báo cáo** bên dưới."
                )
            else:
                brief = (
                    "✅ Đã tạo báo cáo bên dưới (câu trước vẫn giữ nguyên). "
                    "Bạn có thể tải **CSV**, **Word**, đổi biểu đồ, "
                    "hoặc bấm **Viết Bài Báo**."
                )

            if payload.get("from_cache"):
                brief = f"⚡ **Kết quả lưu** — không cần đọc DB/AI lại. {brief}"
            if payload.get("viz_only"):
                brief = f"📊 **Đổi biểu đồ** — {brief}"

            st.markdown(brief)
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": brief,
                    "payload": payload,
                }
            )
            st.session_state.latest_report = payload
            st.rerun()
