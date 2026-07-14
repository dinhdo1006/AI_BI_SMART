"""Qwen Router — phân loại intent trước khi gọi SQLCoder."""

from __future__ import annotations

import os
import re
from typing import Literal

from core.ollama_client import make_ollama_llm
from core.viz_advisor import is_viz_only_request
from langchain_ollama import OllamaLLM

Intent = Literal["sql", "viz", "followup", "chitchat", "oos"]

INTENT_SQL = "sql"
INTENT_VIZ = "viz"
INTENT_FOLLOWUP = "followup"
INTENT_CHITCHAT = "chitchat"
INTENT_OOS = "oos"

_VALID_INTENTS: frozenset[str] = frozenset(
    {INTENT_SQL, INTENT_VIZ, INTENT_FOLLOWUP, INTENT_CHITCHAT, INTENT_OOS}
)

_ROUTER_MODEL = os.getenv("INSIGHT_MODEL", "qwen2.5:14b")
_ROUTER_NUM_PREDICT = 16

# Heuristic nhanh — tránh gọi LLM khi đã rõ ràng
_CHITCHAT_PATTERNS = re.compile(
    r"^\s*("
    r"xin\s*chào|chào\s*(bạn|anh|chị|em)?|hello|hi\b|hey\b|"
    r"cảm\s*ơn|thanks|thank\s*you|"
    r"bạn\s*(là\s*ai|làm\s*được\s*gì)|"
    r"giúp\s*tôi\s*(với)?\s*$|"
    r"ok\b|oke\b|được\s*rồi"
    r")\s*[!.?]*\s*$",
    re.IGNORECASE,
)

_OOS_PATTERNS = re.compile(
    r"("
    r"viết\s*(code|python|javascript|hàm)|"
    r"hàm\s*python|python\s*(sort|code|script)|"
    r"dịch\s*(sang|thuật)|"
    r"kể\s*(chuyện|truyện)|"
    r"thời\s*tiết|"
    r"nấu\s*ăn|"
    r"bóng\s*đá|"
    r"chứng\s*khoán\s*mỹ|"
    r"bitcoin|crypto"
    r")",
    re.IGNORECASE,
)

_FOLLOWUP_PATTERNS = re.compile(
    r"("
    r"^(còn|thế|vậy|và)\s|"
    r"\b(nó|chúng|cái\s*đó|dự\s*án\s*đó|mã\s*đó|cái\s*trên)\b|"
    r"chi\s*tiết\s*hơn|giải\s*thích\s*thêm|phân\s*tích\s*sâu\s*hơn|"
    r"so\s*sánh\s*với\s*(cái|kỳ)\s*(trước|đó)"
    r")",
    re.IGNORECASE,
)

_SQL_HINT = re.compile(
    r"("
    r"liệt\s*kê|cho\s*xem|hiển\s*thị|bao\s*nhiêu|top\s*\d*|"
    r"trung\s*bình|tổng|so\s*sánh|diễn\s*biến|xu\s*hướng|"
    r"vốn\s*hóa|giá|khối\s*lượng|dự\s*án|trữ\s*lượng|"
    r"select|sql|bảng|biểu\s*đồ|chart|vẽ"
    r")",
    re.IGNORECASE,
)

_ROUTER_PROMPT = """Bạn là bộ phân loại intent cho hệ thống Conversational BI.
Chỉ trả về ĐÚNG MỘT từ trong danh sách sau (không giải thích):

sql — câu hỏi cần truy vấn dữ liệu / số liệu / bảng / biểu đồ từ database
viz — chỉ đổi loại biểu đồ (cột, đường, tròn, area…) trên dữ liệu đã có
followup — câu hỏi nối tiếp dựa ngữ cảnh trước (đại từ: nó, cái đó, dự án đó…)
chitchat — chào hỏi, cảm ơn, hỏi hệ thống là gì, không cần dữ liệu
oos — ngoài phạm vi BI (viết code, thời tiết, nấu ăn, chủ đề không liên quan domain)

Ví dụ:
Câu: Liệt kê top 5 dự án tiến độ cao nhất → sql
Câu: Vẽ biểu đồ đường giúp tôi → viz
Câu: Còn dự án đó thì sao? → followup
Câu: Xin chào → chitchat
Câu: Viết giúp tôi hàm Python sort → oos

Câu hỏi: {query}
Intent:"""


def _get_router_llm() -> OllamaLLM:
    return make_ollama_llm(
        model=_ROUTER_MODEL,
        temperature=0.0,
        num_predict=_ROUTER_NUM_PREDICT,
        timeout=60,
    )


def _heuristic_intent(
    query: str,
    *,
    has_history: bool,
    has_reuse_data: bool,
) -> Intent | None:
    """Rule-based nhanh — trả None nếu cần LLM."""
    q = (query or "").strip()
    if not q:
        return INTENT_CHITCHAT

    if is_viz_only_request(q):
        return INTENT_VIZ if has_reuse_data else INTENT_SQL

    if _CHITCHAT_PATTERNS.search(q) and not _SQL_HINT.search(q):
        return INTENT_CHITCHAT

    if _OOS_PATTERNS.search(q) and not _SQL_HINT.search(q):
        return INTENT_OOS

    if has_history and _FOLLOWUP_PATTERNS.search(q) and len(q) < 80:
        return INTENT_FOLLOWUP

    if _SQL_HINT.search(q):
        return INTENT_SQL

    return None


def _parse_intent_output(raw: str) -> Intent:
    cleaned = (raw or "").strip().lower()
    # Lấy token đầu tiên nếu LLM thêm chữ thừa
    token = re.split(r"[\s,.:;]+", cleaned)[0] if cleaned else ""
    if token in _VALID_INTENTS:
        return token  # type: ignore[return-value]
    for intent in _VALID_INTENTS:
        if intent in cleaned:
            return intent  # type: ignore[return-value]
    return INTENT_SQL


def classify_intent(
    query: str,
    *,
    has_history: bool = False,
    has_reuse_data: bool = False,
    use_llm: bool = True,
) -> Intent:
    """
    Phân loại intent câu hỏi user.

    Ưu tiên heuristic; nếu không chắc và use_llm=True → gọi Qwen (INSIGHT_MODEL).
    Mặc định fallback = sql (an toàn cho BI).
    """
    heuristic = _heuristic_intent(
        query, has_history=has_history, has_reuse_data=has_reuse_data
    )
    if heuristic is not None:
        return heuristic

    if not use_llm:
        return INTENT_SQL

    try:
        raw = _get_router_llm().invoke(_ROUTER_PROMPT.format(query=query.strip()))
        intent = _parse_intent_output(raw)
        # viz mà không có data cũ → chuyển sang sql
        if intent == INTENT_VIZ and not has_reuse_data:
            return INTENT_SQL
        return intent
    except Exception:
        return INTENT_SQL


def answer_chitchat(query: str) -> str:
    """Trả lời ngắn bằng Qwen — không truy vấn DB."""
    prompt = (
        "Bạn là trợ lý AI BI Smart — phân tích dữ liệu doanh nghiệp bằng tiếng Việt.\n"
        "Trả lời ngắn gọn (2–4 câu), thân thiện. Không bịa số liệu.\n"
        "Gợi ý người dùng hỏi về dự án IT, địa chất/mỏ, hoặc chứng khoán VNFDATA.\n\n"
        f"Người dùng: {query.strip()}\n"
        "Trợ lý:"
    )
    try:
        llm = make_ollama_llm(
            model=_ROUTER_MODEL,
            temperature=0.3,
            num_predict=256,
            timeout=60,
        )
        return (llm.invoke(prompt) or "").strip() or (
            "Xin chào! Tôi là AI BI Smart — hãy chọn domain và hỏi về dữ liệu "
            "(ví dụ: top dự án, diễn biến giá cổ phiếu, trữ lượng mỏ)."
        )
    except Exception:
        return (
            "Xin chào! Tôi là AI BI Smart. Hãy đặt câu hỏi phân tích dữ liệu "
            "theo domain đang chọn trên sidebar."
        )


def out_of_scope_message(query: str) -> str:
    """Thông báo lịch sự khi câu hỏi ngoài phạm vi BI."""
    _ = query
    return (
        "Câu hỏi này nằm ngoài phạm vi phân tích dữ liệu BI của hệ thống. "
        "Tôi hỗ trợ truy vấn và phân tích số liệu theo domain "
        "(IT Deployment, Mining & Geology, VNFDATA Tài chính). "
        "Bạn hãy hỏi về bảng biểu, xu hướng, top/bottom, hoặc so sánh chỉ số nhé."
    )
