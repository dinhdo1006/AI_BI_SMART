"""Fact-check số liệu trong bài viết so với data/stats nguồn."""

from __future__ import annotations

import math
import re
from typing import Any

# Số trong dòng meta / ảnh / URL không phải claim nghiệp vụ
_SKIP_LINE = re.compile(
    r"(Thời gian tạo báo cáo:|data:image/|https?://|![^\]]*]\()",
    re.IGNORECASE,
)

# Token số kiểu VN/EN + đơn vị % / tỷ / triệu tùy chọn
_NUMBER_TOKEN = re.compile(
    r"(?<![\w./-])"
    r"("
    r"\d{1,3}(?:\.\d{3})+(?:,\d+)?"  # 1.234.567,89
    r"|\d{1,3}(?:,\d{3})+(?:\.\d+)?"  # 1,234,567.89
    r"|\d+[.,]\d+"  # 12,5 / 12.5
    r"|\d+"  # 15
    r")"
    r"(?:\s*(%|tỷ|ty|triệu|trieu|tr\.?))?",
    re.IGNORECASE,
)

_ABS_TOL = 0.02
_REL_TOL = 0.015  # 1.5%


def _parse_number_token(raw: str) -> float | None:
    s = (raw or "").strip()
    if not s:
        return None
    # VN: 1.234.567,89
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", s):
        s = s.replace(".", "").replace(",", ".")
    # EN: 1,234,567.89
    elif re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", s):
        s = s.replace(",", "")
    # Decimal ngắn: ưu tiên dấu phẩy VN nếu chỉ có một dấu
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def extract_claim_numbers(markdown: str) -> list[dict[str, Any]]:
    """Trích các số trong bài (bỏ meta/timestamp/ảnh)."""
    claims: list[dict[str, Any]] = []
    seen: set[tuple[float, str]] = set()
    for line in (markdown or "").splitlines():
        if _SKIP_LINE.search(line):
            continue
        for m in _NUMBER_TOKEN.finditer(line):
            raw = m.group(1)
            unit = (m.group(2) or "").strip().lower()
            value = _parse_number_token(raw)
            if value is None or not math.isfinite(value):
                continue
            # Bỏ số quá nhỏ kiểu đánh số mục (1., 2.) trừ khi có đơn vị/%
            if abs(value) < 10 and not unit and "." not in raw and "," not in raw:
                continue
            key = (round(value, 6), unit)
            if key in seen:
                continue
            seen.add(key)
            start = max(0, m.start() - 24)
            end = min(len(line), m.end() + 24)
            claims.append(
                {
                    "raw": m.group(0).strip(),
                    "value": value,
                    "unit": unit,
                    "context": line[start:end].strip(),
                }
            )
    return claims


def _walk_numbers(obj: Any, out: list[float], depth: int = 0) -> None:
    if depth > 8:
        return
    if obj is None:
        return
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        v = float(obj)
        if math.isfinite(v):
            out.append(v)
        return
    if isinstance(obj, str):
        # Chỉ parse chuỗi thuần số; bỏ text dài
        if len(obj) <= 32:
            v = _parse_number_token(obj.replace("%", "").strip())
            if v is not None and math.isfinite(v):
                out.append(v)
        return
    if isinstance(obj, dict):
        for v in obj.values():
            _walk_numbers(v, out, depth + 1)
        return
    if isinstance(obj, (list, tuple, set)):
        for v in obj:
            _walk_numbers(v, out, depth + 1)


def collect_source_numbers(
    data: list[dict[str, Any]] | None,
    stats: dict[str, Any] | None = None,
) -> list[float]:
    """Thu thập mọi số từ data rows + stats (+ biến thể % / scale thường gặp)."""
    nums: list[float] = []
    if data:
        for row in data[:500]:
            _walk_numbers(row, nums)
        nums.append(float(len(data)))
    if stats:
        _walk_numbers(stats, nums)

    expanded: list[float] = []
    for v in nums:
        if not math.isfinite(v):
            continue
        expanded.append(v)
        # Biến thể % ↔ tỷ lệ
        if abs(v) <= 1.5:
            expanded.append(v * 100.0)
        if 1 < abs(v) <= 150:
            expanded.append(v / 100.0)
        # Làm tròn thường gặp trong bài
        expanded.append(round(v, 0))
        expanded.append(round(v, 1))
        expanded.append(round(v, 2))
        expanded.append(round(v, 4))

    # Dedup gần nhau
    expanded.sort()
    uniq: list[float] = []
    for v in expanded:
        if not uniq or abs(v - uniq[-1]) > 1e-9:
            uniq.append(v)
    return uniq


def _matches_source(value: float, sources: list[float]) -> bool:
    if not sources:
        return False
    abs_v = abs(value)
    for s in sources:
        if abs(value - s) <= _ABS_TOL:
            return True
        denom = max(abs(s), abs_v, 1e-9)
        if abs(value - s) / denom <= _REL_TOL:
            return True
    return False


def fact_check_article(
    markdown: str,
    data: list[dict[str, Any]] | None = None,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Đối chiếu số trong bài với nguồn data/stats.
    Trả về metadata để UI cảnh báo — không sửa nội dung bài.
    """
    claims = extract_claim_numbers(markdown)
    sources = collect_source_numbers(data, stats)

    if not data and not stats:
        return {
            "ok": True,
            "checked": 0,
            "matched": 0,
            "unmatched": [],
            "warnings": ["Chưa có data/stats nguồn để fact-check."],
            "source_count": 0,
        }

    unmatched: list[dict[str, Any]] = []
    matched = 0
    for claim in claims:
        if _matches_source(float(claim["value"]), sources):
            matched += 1
        else:
            unmatched.append(claim)

    warnings: list[str] = []
    if unmatched:
        preview = ", ".join(u["raw"] for u in unmatched[:5])
        more = len(unmatched) - 5
        suffix = f" (+{more} số khác)" if more > 0 else ""
        warnings.append(
            f"{len(unmatched)} số trong bài chưa khớp nguồn dữ liệu: {preview}{suffix}."
        )

    return {
        "ok": len(unmatched) == 0,
        "checked": len(claims),
        "matched": matched,
        "unmatched": unmatched[:20],
        "warnings": warnings,
        "source_count": len(sources),
    }
