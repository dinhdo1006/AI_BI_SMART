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
    r"pie|bar|line|area|combo|heatmap|scatter|treemap|nhiệt|nhiet|phân\s*tán|phan\s*tan|cây|cay)",
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


def suggest_chart_from_data(
    data: list[dict[str, Any]],
    user_query: str = "",
) -> ChartType:
    """
    Gợi ý chart theo data khi user không chỉ định.
    Ưu tiên combo (giá+KL), line (time-series), bar, pie (≤8 category).
    """
    if not data:
        return "table"

    if _is_list_only_query(user_query):
        return "table"

    numeric, date_like, categorical = _analyze_columns(data)

    if not numeric:
        return "table"

    # Time-series + giá/KL lệch độ lớn → combo
    if date_like and should_use_combo_chart(data, user_query):
        return "combo"

    if date_like and numeric:
        return "line"

    q_lower = user_query.lower()

    # Tương quan / phân tán
    if any(
        k in q_lower
        for k in ("tương quan", "tuong quan", "phân tán", "phan tan", "scatter")
    ):
        if len(numeric) >= 2:
            return "scatter"

    # Ma trận / heatmap
    if any(k in q_lower for k in ("heatmap", "nhiệt", "nhiet", "ma trận", "ma tran")):
        if (len(categorical) >= 2 or (categorical and date_like)) and numeric:
            return "heatmap"
        if categorical and len(numeric) >= 2:
            return "heatmap"

    # Cơ cấu / tỷ trọng: ít nhãn → pie, nhiều → treemap
    if any(
        k in q_lower
        for k in ("cơ cấu", "co cau", "tỷ trọng", "ty trong", "cấu trúc", "cau truc", "treemap")
    ):
        if categorical and numeric:
            return "pie" if len(data) <= 8 else "treemap"

    # 2 chỉ số cùng 1 dòng (vd: tổng TS + vốn CSH) → pie
    if len(numeric) == 2 and len(data) == 1 and not date_like:
        return "pie"

    # Nhiều entity + nhiều metric → heatmap ma trận
    if categorical and len(numeric) >= 3 and len(data) >= 3 and not date_like:
        return "heatmap"

    # 2+ metric số, so sánh ngang hàng → scatter
    if len(numeric) >= 2 and not date_like and len(data) >= 5:
        if any(k in q_lower for k in ("so sánh", "so sanh", "vs", "với", "voi")):
            return "scatter"

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
    """Ưu tiên: yêu cầu tường minh → history gần → suy từ data."""
    explicit = detect_chart_from_text(user_query)
    if explicit:
        return explicit

    if history:
        for msg in reversed(history):
            if msg.get("role") == "user":
                prev = detect_chart_from_text(msg.get("content") or "")
                if prev:
                    return prev
                break

    rows = data or []
    # Gợi ý combo từ data ngay cả khi user không nói tường minh
    if should_use_combo_chart(rows, user_query):
        return "combo"

    return suggest_chart_from_data(rows, user_query)
