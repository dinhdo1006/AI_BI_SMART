"""Narrative Planner — lập dàn ý rồi viết bài báo phân tích hoàn chỉnh."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Callable

from langchain_ollama import OllamaLLM

from core.article_templates import (
    classify_article_template,
    format_template_brief,
    outline_from_template,
)
from core.insight_stats import compute_insight_stats
from core.ollama_client import make_ollama_llm

_NARRATIVE_MODEL = os.getenv("INSIGHT_MODEL", "qwen2.5:14b")
_MAX_SAMPLE_ROWS = 25
# fast = 1 LLM call (mặc định, nhanh với 14b); full = outline + từng mục + finalize
_NARRATIVE_MODE = (os.getenv("NARRATIVE_MODE") or "fast").strip().lower()
_OUTLINE_NUM_PREDICT = 600
_SECTION_NUM_PREDICT = 700
_FINALIZE_NUM_PREDICT = 1200
_FULL_ARTICLE_NUM_PREDICT = 2200
_REVISE_ARTICLE_NUM_PREDICT = 2200

ProgressCb = Callable[[str], None] | None

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


def _get_llm(*, num_predict: int, temperature: float = 0.2, timeout: float = 240) -> OllamaLLM:
    return make_ollama_llm(
        model=_NARRATIVE_MODEL,
        temperature=temperature,
        num_predict=num_predict,
        timeout=timeout,
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
                "id": "conclusion",
                "heading": "Kết luận, rủi ro và khuyến nghị",
                "focus": "Hạn chế dữ liệu + hành động theo dõi tiếp theo",
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
                "id": "conclusion",
                "heading": "Kết luận, rủi ro và điểm theo dõi",
                "focus": "Rủi ro diễn giải + hạn chế mẫu + tóm tắt ngắn",
            },
        ],
    }


def _default_outline(question: str, domain_name: str, domain_id: str = "") -> dict[str, Any]:
    if is_finance_domain(domain_name) or is_finance_domain(domain_id):
        matched = classify_article_template(question)
        if matched:
            return outline_from_template(
                matched, question=question, domain_name=domain_name
            )
        return _default_outline_vietstock(question, domain_name)
    return _default_outline_bi(question, domain_name)


def _report_timestamp(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%d/%m/%Y %H:%M")


def stamp_article_timestamp(article: str, when: datetime | None = None) -> str:
    """Chèn dòng Thời gian tạo báo cáo sau tiêu đề # (nếu chưa có)."""
    text = (article or "").strip()
    stamp = f"*Thời gian tạo báo cáo: {_report_timestamp(when)}*"
    if "Thời gian tạo báo cáo:" in text:
        return text

    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("# ") and not stripped.startswith("##"):
            insert_at = i + 1
            break
    # Bỏ dòng trống ngay sau tiêu đề rồi chèn stamp + blank
    while insert_at < len(lines) and not lines[insert_at].strip():
        insert_at += 1
    block = [stamp, ""]
    lines[insert_at:insert_at] = block
    return "\n".join(lines).strip()


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

    matched = classify_article_template(question) if finance else None
    if matched:
        return outline_from_template(
            matched, question=question, domain_name=domain_name
        )

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
    template_brief = format_template_brief(outline)
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
Viết MỘT mục bài báo tiếng Việt (120–250 từ) theo dàn ý dưới đây.
Chỉ dùng số liệu trong THỐNG KÊ và MẪU JSON — tuyệt đối không bịa số.
{tone}

{template_brief}

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
6. Nếu thiếu số để trả lời câu hỏi template → nêu rõ không đủ dữ liệu.

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
    template_brief = format_template_brief(outline)
    lo = outline.get("word_count_min") or 500
    hi = outline.get("word_count_max") or 900
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

{template_brief}

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
7. Độ dài toàn bài khoảng {lo}–{hi} từ.

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


def write_full_article_one_shot(
    *,
    outline: dict[str, Any],
    question: str,
    stats: dict[str, Any],
    sample_rows: list[dict[str, Any]],
    insight_summary: str = "",
) -> str:
    """
    Viết cả bài trong 1 lần gọi LLM (nhanh với model 7b/14b).
    Dùng dàn ý cố định — không gọi outline/finalize riêng.
    """
    stats_json = json.dumps(stats, ensure_ascii=False, indent=2)
    sample_json = json.dumps(
        sample_rows[:_MAX_SAMPLE_ROWS], ensure_ascii=False, indent=2
    )
    vietstock = (outline.get("style") or "") == "vietstock"
    template_brief = format_template_brief(outline)
    lo = outline.get("word_count_min") or 500
    hi = outline.get("word_count_max") or 900
    style_note = (
        "Phong cách Vietstock: ngôn ngữ nhà đầu tư, khuyến nghị quan sát "
        "(Theo dõi / Tích cực / Thận trọng) nếu phù hợp; không bịa giá mục tiêu."
        if vietstock
        else "Phong cách BI nội bộ, rõ ràng, có số liệu."
    )
    section_lines = []
    for sec in outline.get("sections") or []:
        section_lines.append(
            f"- ## {sec.get('heading')}: {sec.get('focus')}"
        )
    sections_block = "\n".join(section_lines) or "- ## Phát hiện chính\n- ## Kết luận"

    prompt = f"""Bạn là biên tập viên phân tích dữ liệu.
Viết MỘT bài báo tiếng Việt hoàn chỉnh (khoảng {lo}–{hi} từ) dựa trên thống kê có sẵn.
{style_note}
Chỉ dùng số trong THỐNG KÊ / MẪU — tuyệt đối không bịa số, không bịa P/E hay giá mục tiêu.

{template_brief}

=== CÂU HỎI ===
{question}

=== META ===
Tiêu đề đề xuất: {outline.get("title")}
Góc bài: {outline.get("angle")}
Đối tượng: {outline.get("audience")}

=== DÀN Ý CÁC MỤC (bắt buộc có ## tương ứng) ===
{sections_block}

=== TÓM TẮT INSIGHT SẴN CÓ (tham khảo, không copy nguyên) ===
{(insight_summary or "")[:1200] or "(không có)"}

=== THỐNG KÊ ===
{stats_json}

=== MẪU DỮ LIỆU ===
{sample_json}

=== YÊU CẦU OUTPUT ===
1. Dòng đầu: # Tiêu đề hấp dẫn
2. Đoạn lead 2–3 câu ngay sau tiêu đề (trước ## đầu tiên)
3. Các mục ## theo dàn ý, viết liền mạch có số liệu
4. Trả lời đủ các câu hỏi của TEMPLATE (nếu có); thiếu data → nói rõ
5. Markdown sạch, không code fence, không nhắc SQL/LLM

Bài báo:"""
    try:
        article = (
            _get_llm(
                num_predict=_FULL_ARTICLE_NUM_PREDICT,
                temperature=0.25,
                timeout=300,
            )
            .invoke(prompt)
            .strip()
        )
        if article:
            if not article.lstrip().startswith("#"):
                title = outline.get("title") or f"Phân tích: {question[:60]}"
                article = f"# {title}\n\n{article}"
            return article
    except Exception:
        pass

    # Fallback tối thiểu khi LLM lỗi
    title = outline.get("title") or f"Phân tích: {question[:60]}"
    highlights = json.dumps(stats.get("highlights") or {}, ensure_ascii=False)
    return (
        f"# {title}\n\n"
        f"*{outline.get('angle') or ''}*\n\n"
        f"## Phát hiện chính\n\n"
        f"Thống kê nổi bật: {highlights}\n\n"
        f"## Kết luận\n\n"
        f"(Chưa sinh được bài đầy đủ — kiểm tra Ollama / INSIGHT_MODEL.)"
    )


def revise_article(
    *,
    article_markdown: str,
    instruction: str,
    question: str = "",
    insight_summary: str = "",
) -> dict[str, Any]:
    """
    Chỉnh sửa bài đã viết theo chỉ đạo của user.
    Không truy vấn lại DB; chỉ biên tập nội dung đang có và giữ nguyên số liệu.
    """
    article = (article_markdown or "").strip()
    ask = (instruction or "").strip()
    if not article:
        raise ValueError("Thiếu nội dung bài viết cần sửa")
    if not ask:
        raise ValueError("Thiếu yêu cầu chỉnh sửa bài viết")

    prompt = f"""Bạn là biên tập viên phân tích dữ liệu.
Hãy chỉnh sửa bài Markdown hiện có theo YÊU CẦU SỬA BÀI.

=== NGUYÊN TẮC BẮT BUỘC ===
1. Giữ nguyên sự thật và mọi số liệu đang có; không bịa thêm số, giá mục tiêu, khuyến nghị đầu tư hoặc nguồn dữ liệu mới.
2. Nếu user yêu cầu thêm nội dung nhưng bài gốc không có dữ kiện, hãy viết thận trọng và nêu rõ thiếu dữ liệu.
3. Giữ định dạng Markdown sạch: tiêu đề #, mục ##, không code fence.
4. Không nhắc đến LLM, prompt, SQL hoặc quá trình nội bộ.
5. Trả về TOÀN BỘ bài sau chỉnh sửa, không chỉ phần thay đổi.

=== CÂU HỎI GỐC ===
{question or "(không có)"}

=== TÓM TẮT INSIGHT THAM KHẢO ===
{(insight_summary or "")[:1500] or "(không có)"}

=== YÊU CẦU SỬA BÀI ===
{ask}

=== BÀI HIỆN TẠI ===
{article}

=== BÀI SAU CHỈNH SỬA ==="""
    revised = (
        _get_llm(
            num_predict=_REVISE_ARTICLE_NUM_PREDICT,
            temperature=0.2,
            timeout=300,
        )
        .invoke(prompt)
        .strip()
    )
    if not revised:
        revised = article
    if not revised.lstrip().startswith("#"):
        revised = f"# Bài phân tích đã chỉnh sửa\n\n{revised}"
    return {
        "article_markdown": revised,
        "outline": {"revision_instruction": ask, "source": "revise_article"},
        "word_count": len(re.findall(r"\S+", revised)),
        "sections_written": len(re.findall(r"^##\s+", revised, flags=re.MULTILINE)),
    }


def generate_article(
    *,
    question: str,
    domain_name: str,
    data: list[dict[str, Any]],
    stats: dict[str, Any] | None = None,
    insight_summary: str = "",
    domain_id: str = "",
    on_progress: ProgressCb = None,
) -> dict[str, Any]:
    """
    Pipeline viết bài.

    - fast (mặc định): dàn ý cố định + 1 LLM call
    - full: outline → từng section → finalize (chậm, NARRATIVE_MODE=full)
    """
    def _progress(msg: str) -> None:
        if on_progress:
            try:
                on_progress(msg)
            except Exception:
                pass

    _progress("Đang tính thống kê…")
    computed = stats if stats is not None else compute_insight_stats(data)

    mode = _NARRATIVE_MODE
    if mode == "full":
        _progress("Đang lập dàn ý…")
        outline = outline_plan(
            question=question,
            domain_name=domain_name,
            stats=computed,
            insight_summary=insight_summary,
            domain_id=domain_id,
        )
        _progress(f"Đang viết {len(outline.get('sections') or [])} mục…")
        sections = write_sections(
            outline=outline,
            question=question,
            stats=computed,
            sample_rows=data,
        )
        _progress("Đang hoàn thiện bài…")
        article = finalize_article(
            outline=outline,
            sections=sections,
            question=question,
        )
        sections_written = len(sections)
    else:
        _progress("Đang chuẩn bị dàn ý…")
        outline = _default_outline(question, domain_name, domain_id)
        _progress("Đang viết bài hoàn chỉnh (1 lượt)…")
        article = write_full_article_one_shot(
            outline=outline,
            question=question,
            stats=computed,
            sample_rows=data,
            insight_summary=insight_summary,
        )
        sections_written = len(outline.get("sections") or [])

    _progress("Đã xong — đang trả kết quả…")
    now = datetime.now()
    generated_at = _report_timestamp(now)
    article = stamp_article_timestamp(article, now)
    word_count = len(re.findall(r"\S+", article))
    return {
        "article_markdown": article,
        "outline": outline,
        "word_count": word_count,
        "stats": computed,
        "sections_written": sections_written,
        "style": outline.get("style") or "bi",
        "mode": mode if mode == "full" else "fast",
        "template_id": outline.get("template_id") or "",
        "template_name": outline.get("template_name") or "",
        "generated_at": generated_at,
    }
