"""Narrative Planner — lập dàn ý rồi viết bài báo phân tích hoàn chỉnh."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from langchain_community.llms import Ollama

from core.insight_stats import compute_insight_stats

_NARRATIVE_MODEL = os.getenv("INSIGHT_MODEL", "qwen2.5:7b")
_MAX_SAMPLE_ROWS = 40
_OUTLINE_NUM_PREDICT = 600
_SECTION_NUM_PREDICT = 700
_FINALIZE_NUM_PREDICT = 1200

_JSON_FENCE = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?```",
    re.IGNORECASE | re.DOTALL,
)

_FINANCE_KEYWORDS = (
    "finance",
    "vnfdata",
    "chứng khoán",
    "chung khoan",
    "tài chính",
    "tai chinh",
    "vietstock",
    "hose",
    "cổ phiếu",
    "co phieu",
)


def _get_llm(*, num_predict: int, temperature: float = 0.2) -> Ollama:
    return Ollama(
        model=_NARRATIVE_MODEL,
        temperature=temperature,
        num_predict=num_predict,
        timeout=180,
    )


def _extract_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    fence = _JSON_FENCE.search(text)
    if fence:
        text = fence.group(1).strip()
    # Tìm object JSON đầu tiên
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def is_finance_domain(domain_name: str) -> bool:
    """True nếu domain thuộc tài chính / VNFDATA → dùng khung Vietstock."""
    lower = (domain_name or "").casefold()
    return any(k in lower for k in _FINANCE_KEYWORDS)


def _default_outline_bi(question: str, domain_name: str) -> dict[str, Any]:
    return {
        "title": f"Phân tích dữ liệu: {question[:80]}",
        "angle": "Phân tích số liệu thực tế, nêu điểm nổi bật và hàm ý kinh doanh",
        "audience": "Lãnh đạo / chuyên viên phân tích",
        "style": "bi",
        "domain": domain_name,
        "sections": [
            {
                "id": "lead",
                "heading": "Mở đầu — Bối cảnh",
                "focus": "Tóm tắt câu hỏi và phạm vi dữ liệu",
            },
            {
                "id": "findings",
                "heading": "Phát hiện chính",
                "focus": "Số liệu nổi bật, top/bottom, outlier",
            },
            {
                "id": "analysis",
                "heading": "Phân tích chuyên sâu",
                "focus": "So sánh, xu hướng, biến động theo kỳ",
            },
            {
                "id": "risks",
                "heading": "Rủi ro và giới hạn",
                "focus": "Hạn chế dữ liệu, điểm cần thận trọng",
            },
            {
                "id": "conclusion",
                "heading": "Kết luận và khuyến nghị",
                "focus": "Hành động theo dõi tiếp theo",
            },
        ],
    }


def _default_outline_vietstock(question: str, domain_name: str) -> dict[str, Any]:
    """Khung gần báo cáo phân tích Vietstock (không bịa giá mục tiêu)."""
    return {
        "title": f"Báo cáo phân tích: {question[:80]}",
        "angle": "Góc nhìn nhà đầu tư — số liệu thực tế, khuyến nghị quan sát",
        "audience": "Nhà đầu tư / chuyên viên phân tích chứng khoán",
        "style": "vietstock",
        "domain": domain_name,
        "sections": [
            {
                "id": "thesis",
                "heading": "Tóm tắt luận điểm",
                "focus": (
                    "Luận điểm chính + khuyến nghị quan sát "
                    "(Theo dõi / Tích cực / Thận trọng) — chỉ dựa trên data; "
                    "KHÔNG bịa giá mục tiêu nếu không có trong thống kê"
                ),
            },
            {
                "id": "update",
                "heading": "Cập nhật số liệu & biến động",
                "focus": (
                    "Số liệu nổi bật, YoY/QoQ (period_comparison), trend, "
                    "top/bottom, highlights"
                ),
            },
            {
                "id": "analysis",
                "heading": "Phân tích chi tiết",
                "focus": "So sánh đối tượng, outlier, correlation nếu có",
            },
            {
                "id": "risks",
                "heading": "Rủi ro & giới hạn dữ liệu",
                "focus": "Rủi ro diễn giải + hạn chế mẫu dữ liệu",
            },
            {
                "id": "conclusion",
                "heading": "Kết luận",
                "focus": "Tóm tắt ngắn + điểm cần theo dõi tiếp",
            },
        ],
    }


def _default_outline(question: str, domain_name: str, domain_id: str = "") -> dict[str, Any]:
    if is_finance_domain(domain_name) or is_finance_domain(domain_id):
        return _default_outline_vietstock(question, domain_name)
    return _default_outline_bi(question, domain_name)


def outline_plan(
    *,
    question: str,
    domain_name: str,
    stats: dict[str, Any],
    insight_summary: str = "",
    domain_id: str = "",
) -> dict[str, Any]:
    """
    Step 1 — Qwen lập dàn ý JSON từ stats (không bịa số).
    Domain Finance → khung Vietstock; domain khác → BI nội bộ.
    """
    finance = is_finance_domain(domain_name) or is_finance_domain(domain_id)
    style = "vietstock" if finance else "bi"
    stats_json = json.dumps(stats, ensure_ascii=False, indent=2)
    fallback = _default_outline(question, domain_name, domain_id)

    if finance:
        role = (
            "Bạn là biên tập viên báo cáo phân tích chứng khoán kiểu Vietstock. "
            "Ngôn ngữ nhà đầu tư, rõ ràng, có số liệu."
        )
        schema_sections = """
  "sections": [
    {"id": "thesis", "heading": "Tóm tắt luận điểm", "focus": "..."},
    {"id": "update", "heading": "Cập nhật số liệu & biến động", "focus": "..."},
    {"id": "analysis", "heading": "Phân tích chi tiết", "focus": "..."},
    {"id": "risks", "heading": "Rủi ro & giới hạn dữ liệu", "focus": "..."},
    {"id": "conclusion", "heading": "Kết luận", "focus": "..."}
  ]"""
        extra_rules = """
=== QUY TẮC VIETSTOCK ===
- Tiêu đề nên nêu mã CP / chủ đề nếu có trong câu hỏi hoặc data.
- Có thể đề xuất khuyến nghị quan sát: Theo dõi / Tích cực / Thận trọng.
- TUYỆT ĐỐI KHÔNG bịa giá mục tiêu, P/E, DCF nếu không có trong THỐNG KÊ.
- Ưu tiên dùng period_comparison, trend, top_bottom, outliers, highlights.
"""
    else:
        role = "Bạn là biên tập viên phân tích dữ liệu BI."
        schema_sections = """
  "sections": [
    {"id": "lead", "heading": "...", "focus": "..."},
    {"id": "findings", "heading": "...", "focus": "..."},
    {"id": "analysis", "heading": "...", "focus": "..."},
    {"id": "risks", "heading": "...", "focus": "..."},
    {"id": "conclusion", "heading": "...", "focus": "..."}
  ]"""
        extra_rules = ""

    prompt = f"""{role}
Nhiệm vụ: lập DÀN Ý bài báo tiếng Việt dựa trên câu hỏi và THỐNG KÊ có sẵn.
CHỈ trả về JSON hợp lệ, không markdown, không giải thích.
{extra_rules}
=== DOMAIN ===
{domain_name}

=== CÂU HỎI ===
{question}

=== THỐNG KÊ (đã tính bằng code — chỉ dùng số này) ===
{stats_json}

=== TÓM TẮT INSIGHT SẴN CÓ (tham khảo góc nhìn) ===
{insight_summary[:800] if insight_summary else "(không có)"}

=== SCHEMA JSON BẮT BUỘC ===
{{
  "title": "tiêu đề bài báo",
  "angle": "góc tiếp cận 1 câu",
  "audience": "đối tượng đọc",
  "style": "{style}",
  "domain": "{domain_name}",
{schema_sections}
}}

JSON:"""
    try:
        raw = _get_llm(num_predict=_OUTLINE_NUM_PREDICT, temperature=0.1).invoke(
            prompt
        )
        outline = _extract_json(raw)
        if not isinstance(outline.get("sections"), list) or not outline["sections"]:
            return fallback
        outline.setdefault("title", fallback["title"])
        outline.setdefault("angle", fallback.get("angle", ""))
        outline.setdefault(
            "audience",
            fallback.get("audience", "Lãnh đạo / chuyên viên phân tích"),
        )
        outline["style"] = style
        outline["domain"] = domain_name
        return outline
    except Exception:
        return fallback


def write_sections(
    *,
    outline: dict[str, Any],
    question: str,
    stats: dict[str, Any],
    sample_rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """
    Step 2 — viết từng section (1 LLM call / section).
    """
    stats_json = json.dumps(stats, ensure_ascii=False, indent=2)
    sample_json = json.dumps(sample_rows[:_MAX_SAMPLE_ROWS], ensure_ascii=False, indent=2)
    vietstock = (outline.get("style") or "") == "vietstock"
    tone = (
        "Viết theo phong cách báo cáo phân tích Vietstock: "
        "ngôn ngữ nhà đầu tư, nêu khuyến nghị quan sát nếu phù hợp, "
        "không bịa giá mục tiêu / định giá."
        if vietstock
        else "Viết theo phong cách báo cáo BI nội bộ, rõ ràng, có số liệu."
    )
    written: list[dict[str, str]] = []

    for section in outline.get("sections") or []:
        heading = str(section.get("heading") or "Mục")
        focus = str(section.get("focus") or "")
        sec_id = str(section.get("id") or heading)
        prompt = f"""Bạn là phóng viên phân tích dữ liệu.
Viết MỘT mục bài báo tiếng Việt (150–280 từ) theo dàn ý dưới đây.
Chỉ dùng số liệu trong THỐNG KÊ và MẪU JSON — tuyệt đối không bịa số.
{tone}

=== CÂU HỎI ===
{question}

=== GÓC BÀI ===
{outline.get("angle") or ""}

=== MỤC CẦN VIẾT ===
Tiêu đề: {heading}
Trọng tâm: {focus}

=== THỐNG KÊ ===
{stats_json}

=== MẪU DỮ LIỆU ===
{sample_json}

=== QUY TẮC ===
1. Bắt đầu bằng ## {heading}
2. Viết liền mạch, có số liệu cụ thể.
3. Không nhắc SQL/LLM/backend.
4. Không viết các mục khác.
5. Không bịa giá mục tiêu, P/E, DCF nếu không có trong THỐNG KÊ.

Nội dung:"""
        try:
            body = _get_llm(
                num_predict=_SECTION_NUM_PREDICT, temperature=0.25
            ).invoke(prompt).strip()
        except Exception:
            body = (
                f"## {heading}\n\n"
                f"(Chưa sinh được nội dung cho mục này — "
                f"tham khảo thống kê: {json.dumps(stats.get('highlights') or {}, ensure_ascii=False)}. )"
            )
        if not body.lstrip().startswith("#"):
            body = f"## {heading}\n\n{body}"
        written.append({"id": sec_id, "heading": heading, "content": body})

    return written


def finalize_article(
    *,
    outline: dict[str, Any],
    sections: list[dict[str, str]],
    question: str,
) -> str:
    """
    Step 3 — ghép + chỉnh thành bài hoàn chỉnh (tiêu đề + kết luận thống nhất).
    """
    joined = "\n\n".join(s["content"] for s in sections if s.get("content"))
    vietstock = (outline.get("style") or "") == "vietstock"
    style_note = (
        "Phong cách Vietstock: tiêu đề chuyên nghiệp, lead nêu luận điểm + "
        "khuyến nghị quan sát (nếu có), không bịa giá mục tiêu."
        if vietstock
        else "Phong cách BI nội bộ, rõ ràng."
    )
    prompt = f"""Bạn là tổng biên tập.
Hãy hoàn thiện bài báo phân tích tiếng Việt từ các mục đã viết.
Giữ nguyên mọi số liệu — không thêm số mới.
{style_note}

=== CÂU HỎI GỐC ===
{question}

=== META ===
Tiêu đề đề xuất: {outline.get("title")}
Góc bài: {outline.get("angle")}
Đối tượng: {outline.get("audience")}
Style: {outline.get("style") or "bi"}

=== CÁC MỤC ĐÃ VIẾT ===
{joined}

=== YÊU CẦU OUTPUT ===
1. Dòng đầu: # Tiêu đề hấp dẫn
2. Đoạn lead 2–3 câu ngay sau tiêu đề (trước ## đầu tiên) — tóm tắt luận điểm.
3. Giữ các ## heading; chỉnh câu cho mượt, bỏ trùng lặp.
4. Kết thúc bằng ## Kết luận ngắn (nếu chưa có).
5. Markdown sạch, không code fence.
6. Không bịa giá mục tiêu / định giá nếu không có trong nội dung gốc.

Bài báo:"""
    try:
        article = _get_llm(
            num_predict=_FINALIZE_NUM_PREDICT, temperature=0.2
        ).invoke(prompt).strip()
        if article:
            return article
    except Exception:
        pass

    # Fallback: ghép thủ công
    title = outline.get("title") or f"Phân tích: {question[:60]}"
    parts = [f"# {title}", ""]
    if outline.get("angle"):
        parts.append(f"*{outline['angle']}*")
        parts.append("")
    parts.append(joined)
    return "\n".join(parts).strip()


def generate_article(
    *,
    question: str,
    domain_name: str,
    data: list[dict[str, Any]],
    stats: dict[str, Any] | None = None,
    insight_summary: str = "",
    domain_id: str = "",
) -> dict[str, Any]:
    """
    Pipeline đầy đủ: outline → write_sections → finalize_article.

    Returns:
        { article_markdown, outline, word_count, stats }
    """
    computed = stats if stats is not None else compute_insight_stats(data)
    outline = outline_plan(
        question=question,
        domain_name=domain_name,
        stats=computed,
        insight_summary=insight_summary,
        domain_id=domain_id,
    )
    sections = write_sections(
        outline=outline,
        question=question,
        stats=computed,
        sample_rows=data,
    )
    article = finalize_article(
        outline=outline,
        sections=sections,
        question=question,
    )
    word_count = len(re.findall(r"\S+", article))
    return {
        "article_markdown": article,
        "outline": outline,
        "word_count": word_count,
        "stats": computed,
        "sections_written": len(sections),
        "style": outline.get("style") or "bi",
    }
