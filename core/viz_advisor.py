"""Nhận diện loại biểu đồ từ câu hỏi / ngữ cảnh / hình dạng dữ liệu."""

from __future__ import annotations

import re
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

# Ưu tiên: area/line/bar trước pie — tránh "miền" bị nhầm hoặc auto-pie
_CHART_PATTERNS: list[tuple[ChartType, re.Pattern[str]]] = [
    (
        "candlestick",
        re.compile(
            r"(biểu\s*đồ|bieu\s*do).{0,30}(nến|nen|candle)|"
            r"candlestick|ohlc|đồ\s*thị\s*nến|do\s*thi\s*nen",
            re.IGNORECASE,
        ),
    ),
    (
        "waterfall",
        re.compile(
            r"(biểu\s*đồ|bieu\s*do).{0,30}(thác|thac|waterfall)|"
            r"waterfall|bridge\s*chart|đóng\s*góp|dong\s*gop",
            re.IGNORECASE,
        ),
    ),
    (
        "radar",
        re.compile(
            r"(biểu\s*đồ|bieu\s*do).{0,30}(radar|mạng\s*nhện|mang\s*nhen|spider)|"
            r"radar\s*chart|spider\s*chart",
            re.IGNORECASE,
        ),
    ),
    (
        "heatmap",
        re.compile(
            r"(biểu\s*đồ|bieu\s*do).{0,30}(nhiệt|nhiet|heatmap)|"
            r"heatmap|heat\s*map|ma\s*trận|ma\s*tran",
            re.IGNORECASE,
        ),
    ),
    (
        "scatter",
        re.compile(
            r"(biểu\s*đồ|bieu\s*do).{0,30}(phân\s*tán|phan\s*tan|scatter)|"
            r"scatter|tương\s*quan|tuong\s*quan|xy\s*plot",
            re.IGNORECASE,
        ),
    ),
    (
        "treemap",
        re.compile(
            r"(biểu\s*đồ|bieu\s*do).{0,30}(cây|cay|treemap|khối|khoi)|"
            r"treemap|tree\s*map|ô\s*vuông|o\s*vuong",
            re.IGNORECASE,
        ),
    ),
    (
        "area",
        re.compile(
            r"(biểu\s*đồ|bieu\s*do).{0,30}(miền|mien|vùng|vung|area)|"
            r"area\s*chart|dạng\s*miền|dang\s*mien",
            re.IGNORECASE,
        ),
    ),
    (
        "line",
        re.compile(
            r"(biểu\s*đồ|bieu\s*do).{0,30}(đường|duong|line)|"
            r"line\s*chart|xu\s*hướng|xu\s*huong|theo\s*(thời\s*gian|thoi\s*gian|ngày|ngay)|"
            r"trend|dự\s*báo|du\s*bao|forecast",
            re.IGNORECASE,
        ),
    ),
    (
        "combo",
        re.compile(
            r"(combo|kết\s*hợp|ket\s*hop|giá\s*và\s*khối\s*lượng|"
            r"gia\s*va\s*khoi\s*luong|price\s*and\s*volume)",
            re.IGNORECASE,
        ),
    ),
    (
        "bar",
        re.compile(
            r"(biểu\s*đồ|bieu\s*do).{0,30}(cột|cot|bar)|"
            r"bar\s*chart|cột\s*đứng|cot\s*dung",
            re.IGNORECASE,
        ),
    ),
    (
        "pie",
        re.compile(
            r"(biểu\s*đồ|bieu\s*do).{0,30}(tròn|tron|pie|bánh|banh)|"
            r"pie\s*chart|dạng\s*tròn|dang\s*tron|hình\s*tròn|hinh\s*tron|"
            r"cơ\s*cấu|co\s*cau|tỷ\s*trọng|ty\s*trong",
            re.IGNORECASE,
        ),
    ),
    (
        "table",
        re.compile(
            r"(chỉ\s*(hiển\s*thị\s*)?bảng|chi\s*bang|table\s*only|"
            r"không\s*(cần\s*)?biểu\s*đồ|khong\s*(can\s*)?bieu\s*do|"
            r"danh\s*sách|danh\s*sach)",
            re.IGNORECASE,
        ),
    ),
]

_VIZ_ONLY: re.Pattern[str] = re.compile(
    r"(làm|lam|vẽ|ve|đổi|doi|chuyển|chuyen|cho\s+tôi|cho\s+toi|tạo|tao|hiển\s*thị|hien\s*thi|"
    r"xem).{0,60}"
    r"(biểu\s*đồ|bieu\s*do|chart|tròn|tron|cột|cot|đường|duong|miền|mien|vùng|vung|"
    r"pie|bar|line|area|combo|heatmap|scatter|treemap|radar|waterfall|nhiệt|nhiet|phân\s*tán|phan\s*tan|cây|cay)",
    re.IGNORECASE,
)

_DATA_ASK: re.Pattern[str] = re.compile(
    r"(liệt\s*kê|liet\s*ke|tổng|tong|trung\s*bình|trung\s*binh|theo\s*từng|theo\s*tung|"
    r"dự\s*án|du\s*an|mỏ|mo|trữ\s*lượng|tru\s*luong|phân\s*tích|phan\s*tich|"
    r"so\s*sánh|so\s*sanh|bao\s*nhiêu|bao\s*nhieu|top|dien\s*bien|diễn\s*biến)",
    re.IGNORECASE,
)

_LIST_ONLY: re.Pattern[str] = re.compile(
    r"(danh\s*sách|danh\s*sach|liệt\s*kê|liet\s*ke)\b",
    re.IGNORECASE,
)

_COMPARE_OR_CHART: re.Pattern[str] = re.compile(
    r"(so\s*sánh|so\s*sanh|top|trung\s*bình|trung\s*binh|biểu\s*đồ|bieu\s*do|"
    r"vẽ|ve|chart|tỷ\s*trọng|ty\s*trong|cơ\s*cấu|co\s*cau|xu\s*hướng|xu\s*huong|"
    r"heatmap|scatter|treemap|nhiệt|nhiet|phân\s*tán|phan\s*tan)",
    re.IGNORECASE,
)

_PRICE_COL: re.Pattern[str] = re.compile(
    r"(gia|price|dong\s*cua|đóng\s*cửa|eps)",
    re.IGNORECASE,
)

_VOLUME_COL: re.Pattern[str] = re.compile(
    r"(khoi\s*luong|khối\s*lượng|volume|sl\s*gd)",
    re.IGNORECASE,
)

_MAGNITUDE_RATIO_THRESHOLD = 100.0

# Heuristic: chuyển bar dọc → ngang khi nhãn dài hoặc nhiều category
_MAX_CATEGORIES_VERTICAL = 7
_MAX_CATEGORY_LABEL_LEN = 12

_STACKED_100_KEYWORDS: re.Pattern[str] = re.compile(
    r"(tỷ\s*trọng|ty\s*trong|cơ\s*cấu|co\s*cau|new\s*vs|repeat|"
    r"phần\s*trăm|phan\s*tram|100\s*%|stacked|chồng|chong|tỉ\s*lệ|ti\s*le|"
    r"so\s*sánh\s*tỷ|so\s*sanh\s*ty)",
    re.IGNORECASE,
)


def is_viz_only_request(user_query: str) -> bool:
    """True nếu user chủ yếu yêu cầu đổi loại biểu đồ."""
    q = user_query.strip()
    if len(q) > 120:
        return False
    chart = detect_chart_from_text(q)
    has_data_ask = bool(_DATA_ASK.search(q))
    if chart and not has_data_ask:
        return True
    return bool(_VIZ_ONLY.search(q)) and not has_data_ask


def detect_chart_from_text(text: str) -> ChartType | None:
    """Bắt keyword loại chart trong câu hỏi người dùng."""
    for chart, pattern in _CHART_PATTERNS:
        if pattern.search(text):
            return chart
    return None


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _analyze_columns(data: list[dict[str, Any]]) -> tuple[list[str], list[str], list[str]]:
    """Phân loại cột: numeric, date_like, categorical từ mẫu data."""
    if not data:
        return [], [], []

    cols = list(data[0].keys())
    sample = data[: min(20, len(data))]
    numeric: list[str] = []
    date_like: list[str] = []
    categorical: list[str] = []

    for c in cols:
        values = [row.get(c) for row in sample if row.get(c) is not None]
        if not values:
            continue
        lower = c.lower()
        if all(_is_number(v) for v in values):
            if lower in {"id"} or lower.endswith("_id"):
                continue
            numeric.append(c)
        elif any(k in lower for k in ("ngay", "date", "time", "thang", "updated", "surveyed")):
            date_like.append(c)
        else:
            categorical.append(c)

    return numeric, date_like, categorical


def _column_max_abs(data: list[dict[str, Any]], col: str) -> float:
    vals = [
        abs(float(row[col]))
        for row in data
        if row.get(col) is not None and _is_number(row[col])
    ]
    return max(vals) if vals else 0.0


def magnitude_ratio(data: list[dict[str, Any]], col_a: str, col_b: str) -> float:
    """Tỷ lệ độ lớn giữa 2 cột số (max / min)."""
    max_a = _column_max_abs(data, col_a)
    max_b = _column_max_abs(data, col_b)
    lo, hi = min(max_a, max_b), max(max_a, max_b)
    if lo <= 0:
        return hi if hi > 0 else 1.0
    return hi / lo


def _pick_price_volume_cols(numeric: list[str]) -> tuple[str | None, str | None]:
    price = next((c for c in numeric if _PRICE_COL.search(c)), None)
    volume = next((c for c in numeric if _VOLUME_COL.search(c)), None)
    return price, volume


def should_use_combo_chart(data: list[dict[str, Any]], user_query: str = "") -> bool:
    """
    Combo khi: có cột thời gian + 2 cột số lệch độ lớn ≥100x,
    hoặc câu hỏi/cột gợi ý giá + khối lượng.
    """
    if not data:
        return False

    numeric, date_like, _ = _analyze_columns(data)
    if not date_like or len(numeric) < 2:
        return False

    price_col, vol_col = _pick_price_volume_cols(numeric)
    if price_col and vol_col:
        return True

    q = user_query.lower()
    if any(k in q for k in ("khoi luong", "khối lượng", "gia va", "giá và")):
        if len(numeric) >= 2:
            return True

    # So sánh 2 cột số đầu tiên có ý nghĩa
    candidates = numeric[:3]
    for i, col_a in enumerate(candidates):
        for col_b in candidates[i + 1 :]:
            if magnitude_ratio(data, col_a, col_b) >= _MAGNITUDE_RATIO_THRESHOLD:
                return True
    return False


def _is_list_only_query(user_query: str) -> bool:
    """Danh sách thuần — không so sánh / không yêu cầu chart."""
    if not user_query.strip():
        return False
    if detect_chart_from_text(user_query):
        return detect_chart_from_text(user_query) == "table"
    if _LIST_ONLY.search(user_query) and not _COMPARE_OR_CHART.search(user_query):
        return True
    return False


def _unique_count(data: list[dict[str, Any]], col: str) -> int:
    return len({str(row.get(col, "")) for row in data})


def _detect_ohlc_cols(data: list[dict[str, Any]]) -> dict[str, str] | None:
    """Tìm cột OHLC theo tên — không hardcode mã CP."""
    if not data:
        return None
    cols = list(data[0].keys())

    def _find(*parts: str) -> str | None:
        for c in cols:
            low = c.lower()
            if any(p in low for p in parts):
                return c
        return None

    open_c = _find("open_price", "open", "gia_mo")
    high_c = _find("high_price", "high", "gia_cao")
    low_c = _find("low_price", "low", "gia_thap")
    close_c = _find("close_price", "adjusted_price", "close", "gia_dong")
    if open_c and high_c and low_c and close_c:
        date_c = _find("trade_date", "calc_date", "ngay", "date")
        return {
            "open": open_c,
            "high": high_c,
            "low": low_c,
            "close": close_c,
            **({"date": date_c} if date_c else {}),
        }
    return None


def _entity_col(categorical: list[str]) -> str | None:
    entity_names = {
        "ticker",
        "symbol",
        "ma_cp",
        "company_name",
        "short_name",
        "sector",
        "industry",
        "group_code",
    }
    for c in categorical:
        if c.lower() in entity_names or c.lower().replace(" ", "_") in entity_names:
            return c
    return categorical[0] if categorical else None


def compatible_charts(data: list[dict[str, Any]]) -> list[ChartType]:
    """
    Các loại chart render được với shape data hiện tại.
    Dùng để UI disable option không phù hợp — suy từ data, không whitelist câu hỏi.
    """
    if not data:
        return ["table"]

    numeric, date_like, categorical = _analyze_columns(data)
    out: list[ChartType] = ["table"]

    if not numeric:
        return out

    out.append("bar")
    if date_like:
        out.extend(["line", "area"])
    if len(numeric) >= 2 and date_like:
        out.append("combo")
    if _detect_ohlc_cols(data):
        out.append("candlestick")

    entity = _entity_col(categorical)
    # Heatmap: entity×date×value hoặc entity×nhiều metric
    heat_ok = False
    if entity and date_like and numeric:
        if _unique_count(data, entity) >= 2 and _unique_count(data, date_like[0]) >= 2:
            heat_ok = True
    if entity and len(numeric) >= 2:
        heat_ok = True
    if len(categorical) >= 2 and numeric:
        heat_ok = True
    if heat_ok:
        out.append("heatmap")

    if len(numeric) >= 2 and len(data) >= 3:
        out.append("scatter")

    if categorical and numeric and len(data) >= 2:
        if len(data) <= 12:
            out.append("pie")
        out.append("treemap")

    # Radar: nhiều metric so sánh giữa vài entity
    if entity and len(numeric) >= 3 and 2 <= len(data) <= 12:
        out.append("radar")

    # Waterfall: 1 metric + category (đóng góp / thay đổi)
    if categorical and len(numeric) >= 1 and 3 <= len(data) <= 20 and not date_like:
        out.append("waterfall")

    # Dedupe giữ thứ tự
    seen: set[str] = set()
    ordered: list[ChartType] = []
    for c in out:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def suggest_chart_from_data(
    data: list[dict[str, Any]],
    user_query: str = "",
) -> ChartType:
    """
    Gợi ý chart theo hình dạng dữ liệu (ưu tiên shape, không map từng câu hỏi).
    """
    if not data:
        return "table"

    if _is_list_only_query(user_query):
        return "table"

    numeric, date_like, categorical = _analyze_columns(data)
    if not numeric:
        return "table"

    # OHLC đủ → nến (kể cả khi chưa nói "nến")
    if _detect_ohlc_cols(data) and (date_like or len(data) >= 3):
        return "candlestick"

    # Time-series + giá/KL lệch scale → combo
    if date_like and should_use_combo_chart(data, user_query):
        return "combo"

    # Chuỗi thời gian → đường
    if date_like and numeric:
        return "line"

    entity = _entity_col(categorical)
    date_col = date_like[0] if date_like else None

    # Long format: nhiều mã × nhiều ngày → đường (multi-series)
    if entity and date_col and numeric:
        entities = len({row.get(entity) for row in data if row.get(entity) is not None})
        dates = len({row.get(date_col) for row in data if row.get(date_col) is not None})
        if entities >= 2 and dates >= 2 and len(data) / max(entities, 1) >= 1.5:
            return "line"

    # Stacked 100% khi user hỏi tỷ trọng/cơ cấu và có 2 metric
    if entity and len(numeric) == 2 and categorical and not date_like:
        x_col = entity or categorical[0]
        if should_use_stacked_100_percent(data, user_query, numeric, x_col):
            return "bar"

    # Ma trận mã × ngày × 1 metric → heatmap (chỉ pivot thật)
    if entity and date_col and len(numeric) >= 1:
        entities = len({row.get(entity) for row in data if row.get(entity) is not None})
        dates = len({row.get(date_col) for row in data if row.get(date_col) is not None})
        if entities >= 2 and dates >= 3 and len(data) >= 6:
            if re.search(r"heatmap|nhiệt|nhiet|ma\s*trận|ma\s*tran", user_query or "", re.I):
                return "heatmap"

    # Nhiều metric × vài mã (snapshot) → radar hoặc cột nhóm, không heatmap
    if entity and len(numeric) >= 3 and not date_like:
        unique_entities = len({row.get(entity) for row in data if row.get(entity) is not None})
        if unique_entities <= 8:
            return "radar"
        return "bar"

    # 2+ cột số, nhiều điểm → scatter (tương quan)
    if len(numeric) >= 2 and len(data) >= 5 and not date_like:
        return "scatter"

    # 2 chỉ số trên 1 dòng → pie
    if len(numeric) == 2 and len(data) == 1 and not date_like:
        return "pie"

    # Nhiều danh mục + 1 metric: ít → pie/bar, nhiều → treemap
    if categorical and numeric and not date_like:
        n = len(data)
        if n > 12:
            return "treemap"
        if n <= 8 and n >= 3:
            # Giá trị dương thống trị → pie cơ cấu; ngược lại bar xếp hạng
            sample_col = numeric[0]
            positives = sum(
                1
                for row in data
                if _is_number(row.get(sample_col)) and float(row[sample_col]) > 0  # type: ignore[arg-type]
            )
            if positives >= max(1, int(n * 0.8)):
                return "pie"
        return "bar"

    if numeric:
        return "bar"
    return "table"


def _category_labels(data: list[dict[str, Any]], category_col: str) -> list[str]:
    return [
        str(row.get(category_col, ""))
        for row in data
        if row.get(category_col) is not None
    ]


def should_use_horizontal_bar(
    data: list[dict[str, Any]],
    category_col: str | None,
) -> bool:
    """
    Bar ngang khi >7 category hoặc nhãn trục X quá dài — tránh text đè (Power BI style).
    """
    if not data or not category_col:
        return False
    labels = _category_labels(data, category_col)
    if not labels:
        return False
    if len(labels) > _MAX_CATEGORIES_VERTICAL:
        return True
    return max(len(label) for label in labels) > _MAX_CATEGORY_LABEL_LEN


def should_use_stacked_100_percent(
    data: list[dict[str, Any]],
    user_query: str,
    y_cols: list[str],
    category_col: str | None,
) -> bool:
    """
    Stacked 100% khi user yêu cầu tỷ trọng/cơ cấu và có 2 cột số + 1 nhóm.
    """
    if not data or not category_col or len(y_cols) != 2:
        return False
    return bool(_STACKED_100_KEYWORDS.search(user_query or ""))


def resolve_chart_type(
    user_query: str,
    history: list[dict[str, str]] | None = None,
    data: list[dict[str, Any]] | None = None,
) -> ChartType:
    """Ưu tiên: yêu cầu tường minh (nếu data cho phép) → history → suy từ shape data."""
    rows = data or []
    allowed = set(compatible_charts(rows)) if rows else set()

    explicit = detect_chart_from_text(user_query)
    if explicit:
        if not rows or explicit in allowed or explicit == "table":
            return explicit
        # User xin loại không vẽ được → fallback theo shape
        return suggest_chart_from_data(rows, user_query)

    if history:
        for msg in reversed(history):
            if msg.get("role") == "user":
                prev = detect_chart_from_text(msg.get("content") or "")
                if prev and (not rows or prev in allowed or prev == "table"):
                    return prev
                break

    if should_use_combo_chart(rows, user_query):
        return "combo"

    return suggest_chart_from_data(rows, user_query)
