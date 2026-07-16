"""Truy hồi few-shot theo độ giống câu hỏi — không hardcode intent→SQL."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _normalize(text: str) -> str:
    lowered = (text or "").lower()
    nfd = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _tokens(text: str) -> set[str]:
    norm = _normalize(text)
    return {t for t in re.findall(r"[a-z0-9_]+", norm) if len(t) >= 2}


def score_few_shot(user_query: str, example: dict[str, Any]) -> float:
    """Điểm chồng token giữa câu hỏi user và question (và hint từ SQL)."""
    q = _tokens(user_query)
    if not q:
        return 0.0
    ex_q = _tokens(str(example.get("question") or ""))
    sql = _tokens(str(example.get("sql") or ""))
    if not ex_q:
        return 0.0
    inter = len(q & ex_q)
    union = len(q | ex_q) or 1
    jaccard = inter / union
    # Bonus nhẹ nếu cột/bảng trong SQL trùng token nghiệp vụ (market_cap, von…)
    sql_hit = len(q & sql) * 0.05
    return jaccard + sql_hit


def rank_few_shots(
    user_query: str,
    examples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sắp xếp few-shot: liên quan nhất lên đầu (giữ nguyên nếu điểm bằng 0)."""
    if not examples:
        return []
    scored = [(score_few_shot(user_query, ex), i, ex) for i, ex in enumerate(examples)]
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [ex for _, _, ex in scored]


def best_few_shot_sql(
    user_query: str,
    examples: list[dict[str, Any]],
    *,
    min_score: float = 0.12,
) -> str | None:
    """
    SQL từ few-shot gần nhất khi LLM thất bại.
    Chỉ dùng khi độ giống đủ — tránh lấy nhầm ví dụ không liên quan.
    """
    if not examples:
        return None
    ranked = rank_few_shots(user_query, examples)
    if not ranked:
        return None
    best = ranked[0]
    if score_few_shot(user_query, best) < min_score:
        return None
    sql = (best.get("sql") or "").strip()
    return sql or None
