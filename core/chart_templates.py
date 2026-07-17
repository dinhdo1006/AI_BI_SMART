"""Chart templates cố định cho domain tài chính (CP) — map câu hỏi → chart + shape kỳ vọng."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

ChartType = Literal[
    "bar",
    "pie",
    "line",
    "area",
    "combo",
    "candlestick",
    "heatmap",
    "scatter",
    "treemap",
    "radar",
    "waterfall",
    "table",
]

ShapeKind = Literal[
    "price_ohlc",
    "price_timeseries",
    "multi_ticker_price",
    "valuation_snapshot",
    "ranking",
    "constituents",
    "generic",
]


@dataclass(frozen=True)
class ChartTemplate:
    id: str
    name: str
    chart_type: ChartType
    shape: ShapeKind
    patterns: tuple[re.Pattern[str], ...]
    required_cols: tuple[str, ...] = ()
    preferred_cols: tuple[str, ...] = ()
    drop_cols_for_chart: tuple[str, ...] = ()
    description: str = ""


def _norm(text: str) -> str:
    lowered = (text or "").lower()
    nfd = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


_TEMPLATES: tuple[ChartTemplate, ...] = (
    ChartTemplate(
        id="candlestick_volume",
        name="Nến + khối lượng",
        chart_type="candlestick",
        shape="price_ohlc",
        patterns=(
            re.compile(r"(bieu\s*do\s*)?(nen|candle|ohlc|candlestick)", re.I),
            re.compile(r"(gia\s*)?(mo|cao|thap|dong).{0,40}(khoi\s*luong|volume)", re.I),
        ),
        required_cols=("open_price", "high_price", "low_price", "close_price"),
        preferred_cols=("trade_date", "volume", "ticker"),
        drop_cols_for_chart=("company_name", "short_name"),
        description="OHLC 1 mã theo phiên",
    ),
    ChartTemplate(
        id="stock_price_line",
        name="Giá theo thời gian",
        chart_type="line",
        shape="price_timeseries",
        patterns=(
            re.compile(
                r"(dien\s*bien|xu\s*huong|gia\s*(dong\s*cua|dieu\s*chinh)?|"
                r"close\s*price|phien\s*gan|n\s*phien|theo\s*(ngay|thoi\s*gian))",
                re.I,
            ),
        ),
        required_cols=("close_price",),
        preferred_cols=("trade_date", "ticker", "volume", "change_percent"),
        drop_cols_for_chart=("company_name", "short_name"),
        description="Chuỗi giá 1 hoặc nhiều mã",
    ),
    ChartTemplate(
        id="valuation_snapshot",
        name="So sánh định giá",
        chart_type="radar",
        shape="valuation_snapshot",
        patterns=(
            re.compile(
                r"(so\s*sanh).{0,40}(p/?e|p/?b|roe|roa|eps)|(p/?e|p/?b|roe).{0,30}(so\s*sanh|cua)",
                re.I,
            ),
            re.compile(r"(dinh\s*gia|valuation|chi\s*so\s*tai\s*chinh)", re.I),
        ),
        required_cols=("pe_ratio",),
        preferred_cols=("ticker", "pb_ratio", "roe", "roa", "calc_date"),
        drop_cols_for_chart=("company_name",),
        description="P/E P/B ROE snapshot — 1 dòng/mã",
    ),
    ChartTemplate(
        id="ranking_bar",
        name="Xếp hạng / Top N",
        chart_type="bar",
        shape="ranking",
        patterns=(
            re.compile(r"\btop\s*\d*\b|\bxep\s*hang\b|\bvon\s*hoa\b|\bgtgd\b", re.I),
            re.compile(r"(lon\s*nhat|cao\s*nhat|nhieu\s*nhat)", re.I),
        ),
        preferred_cols=("ticker", "market_cap", "volume", "close_price"),
        description="Xếp hạng theo metric",
    ),
    ChartTemplate(
        id="vn30_constituents",
        name="Thành phần chỉ số",
        chart_type="table",
        shape="constituents",
        patterns=(
            re.compile(r"(thanh\s*phan|constituent).{0,20}(vn30|vnindex|chi\s*so)", re.I),
            re.compile(r"\bvn30\b", re.I),
        ),
        preferred_cols=("ticker", "group_code", "company_name"),
        description="Danh sách thành phần chỉ số",
    ),
)


def list_templates() -> list[ChartTemplate]:
    return list(_TEMPLATES)


def match_chart_template(
    user_query: str,
    *,
    domain_id: str = "",
) -> ChartTemplate | None:
    """
    Khớp template CP theo keyword câu hỏi.
    Chỉ áp dụng domain finance; domain khác → None.
    """
    if domain_id and domain_id not in ("finance_vnfdata", "finance"):
        return None
    q = _norm(user_query)
    if not q.strip():
        return None

    best: ChartTemplate | None = None
    best_score = 0
    for tpl in _TEMPLATES:
        score = 0
        for pat in tpl.patterns:
            if pat.search(q):
                score += 1
        if score > best_score:
            best_score = score
            best = tpl
    return best if best_score > 0 else None


def template_to_dict(tpl: ChartTemplate | None) -> dict[str, Any] | None:
    if tpl is None:
        return None
    return {
        "id": tpl.id,
        "name": tpl.name,
        "chart_type": tpl.chart_type,
        "shape": tpl.shape,
        "description": tpl.description,
    }
