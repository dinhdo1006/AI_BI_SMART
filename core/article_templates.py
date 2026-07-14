"""VNFDATA article templates — catalog từ Template AI viết bài 12.7."""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "vnfdata_article_templates.json"

_WORD_RANGE_RE = re.compile(
    r"(\d[\d.]*)\s*[-–—]\s*(\d[\d.]*)",
)


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_text(text: str) -> str:
    t = _strip_accents((text or "").casefold())
    t = re.sub(r"[^\w\s%-]+", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


@lru_cache(maxsize=1)
def load_template_catalog() -> dict[str, Any]:
    if not _CONFIG_PATH.is_file():
        return {"version": "", "templates": [], "default_structure": []}
    with _CONFIG_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        return {"version": "", "templates": [], "default_structure": []}
    templates = data.get("templates") or []
    data["templates"] = [t for t in templates if isinstance(t, dict) and t.get("id")]
    return data


def list_templates() -> list[dict[str, Any]]:
    return list(load_template_catalog().get("templates") or [])


def get_template(template_id: str) -> dict[str, Any] | None:
    tid = (template_id or "").strip()
    for item in list_templates():
        if str(item.get("id") or "") == tid:
            return item
    return None


def parse_word_count_range(spec: str) -> tuple[int, int]:
    """'600-800' / '800-1.000' → (min, max). Fallback (500, 700)."""
    raw = (spec or "").strip()
    m = _WORD_RANGE_RE.search(raw)
    if not m:
        return 500, 700

    def _to_int(s: str) -> int:
        return int(re.sub(r"[^\d]", "", s) or "0")

    lo, hi = _to_int(m.group(1)), _to_int(m.group(2))
    if lo <= 0 or hi <= 0:
        return 500, 700
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi


def target_word_count(spec: str) -> int:
    lo, hi = parse_word_count_range(spec)
    return (lo + hi) // 2


def classify_article_template(question: str) -> dict[str, Any] | None:
    """
    Chọn template khớp nhất theo keyword (ưu tiên cụm dài hơn).
    Không khớp → None (caller dùng khung Vietstock chung).
    """
    q = normalize_text(question)
    if not q:
        return None

    best: dict[str, Any] | None = None
    best_score = 0

    for item in list_templates():
        score = 0
        name_n = normalize_text(str(item.get("name") or ""))
        if name_n and name_n in q:
            score += len(name_n) + 8

        for kw in item.get("keywords") or []:
            nk = normalize_text(str(kw))
            if nk and nk in q:
                score += len(nk)

        if score > best_score:
            best_score = score
            best = item

    return best if best_score > 0 else None


def _section_id(heading: str, index: int) -> str:
    slug = normalize_text(heading).replace(" ", "_")[:32] or f"sec_{index}"
    return f"s{index}_{slug}"


def outline_from_template(
    template: dict[str, Any],
    *,
    question: str,
    domain_name: str,
) -> dict[str, Any]:
    """Chuyển 1 dòng template catalog → outline Narrative Planner."""
    catalog = load_template_catalog()
    structure = list(template.get("structure") or [])
    if not structure:
        structure = list(catalog.get("default_structure") or [])
    if not structure:
        structure = ["Mở bài", "Phân tích số liệu", "Nhận định", "Kết luận"]

    questions = [str(q).strip() for q in (template.get("ai_questions") or []) if str(q).strip()]
    sections: list[dict[str, str]] = []
    n = len(structure)
    for i, heading in enumerate(structure):
        if i == 0:
            focus = (
                f"Mở bài theo loại «{template.get('name')}»; "
                f"chỉ tiêu chính: {template.get('primary_metrics') or '—'}; "
                f"phạm vi so sánh: {template.get('compare_scope') or '—'}"
            )
        elif i == n - 1:
            focus = (
                "Kết luận ngắn, rủi ro / hạn chế dữ liệu; "
                "không bịa số ngoài thống kê"
            )
        else:
            # Phân bổ câu hỏi AI vào các mục giữa
            mid = questions or [
                f"Phân tích {template.get('primary_metrics') or 'chỉ tiêu chính'} "
                f"và {template.get('secondary_metrics') or 'chỉ tiêu phụ'}"
            ]
            # Round-robin 1–2 câu hỏi / mục
            chunk = [mid[j] for j in range(i - 1, len(mid), max(1, n - 2))]
            if not chunk:
                chunk = mid[:2]
            focus = " | ".join(chunk[:2])
        sections.append(
            {
                "id": _section_id(str(heading), i + 1),
                "heading": str(heading),
                "focus": focus,
            }
        )

    lo, hi = parse_word_count_range(str(template.get("word_count") or ""))
    return {
        "title": f"{template.get('name')}: {question[:72]}",
        "angle": (
            f"Template VNFDATA «{template.get('name')}» — "
            f"đối tượng: {template.get('target') or '—'}; "
            f"chu kỳ: {template.get('cycle') or '—'}"
        ),
        "audience": "Nhà đầu tư / chuyên viên phân tích chứng khoán",
        "style": "vietstock",
        "domain": domain_name,
        "template_id": template.get("id"),
        "template_name": template.get("name"),
        "template_category": template.get("category"),
        "target": template.get("target") or "",
        "cycle": template.get("cycle") or "",
        "word_count_min": lo,
        "word_count_max": hi,
        "has_chart": bool(template.get("has_chart")),
        "channel": template.get("channel") or "Web",
        "ai_questions": questions,
        "context_hints": list(template.get("context") or []),
        "primary_metrics": template.get("primary_metrics") or "",
        "secondary_metrics": template.get("secondary_metrics") or "",
        "compare_scope": template.get("compare_scope") or "",
        "input_data": template.get("input_data") or "",
        "rule": template.get("rule") or "",
        "sections": sections,
    }


def format_template_brief(outline: dict[str, Any]) -> str:
    """Khối prompt mô tả template + câu hỏi bắt buộc."""
    if not outline.get("template_id"):
        return ""

    qs = outline.get("ai_questions") or []
    q_lines = "\n".join(f"  {i}. {q}" for i, q in enumerate(qs, 1)) or "  (không có)"
    ctx = outline.get("context_hints") or []
    c_lines = "\n".join(f"  - {c}" for c in ctx) or "  (không có)"
    lo = outline.get("word_count_min") or 500
    hi = outline.get("word_count_max") or 700

    return f"""
=== TEMPLATE VNFDATA (bắt buộc tuân thủ) ===
ID: {outline.get('template_id')}
Loại bài: {outline.get('template_name')}
Đối tượng: {outline.get('target') or outline.get('audience')}
Dữ liệu đầu vào kỳ vọng: {outline.get('input_data') or '—'}
Chỉ tiêu chính: {outline.get('primary_metrics') or '—'}
Chỉ tiêu phụ: {outline.get('secondary_metrics') or '—'}
Phạm vi so sánh: {outline.get('compare_scope') or '—'}
Rule / điều kiện: {outline.get('rule') or '—'}
Độ dài mục tiêu: {lo}–{hi} từ
Kênh: {outline.get('channel') or 'Web'}

AI PHẢI trả lời các câu hỏi sau (chỉ dựa trên THỐNG KÊ/MẪU; nếu thiếu số thì nói rõ không đủ dữ liệu — không bịa):
{q_lines}

Ngữ cảnh tham khảo (chỉ dùng nếu có trong data; không bịa tin bên ngoài):
{c_lines}
""".strip()
