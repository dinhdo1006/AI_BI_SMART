"""
Cross-domain join — kết hợp dữ liệu từ nhiều domain DB.

Kiến trúc:
  1. Router nhận diện câu hỏi liên domain (2+ domain).
  2. CrossDomainPlanner lập kế hoạch: query domain A, query domain B.
  3. Thực thi từng SQL trên DB tương ứng.
  4. JoinEngine join kết quả ở Python (hash join theo key chung).
  5. Trả rows đã join cho LLM viết insight.

Hiện tại hỗ trợ:
  - finance_vnfdata (VNFDATA stock/finance DB)
  - Bất kỳ domain nào có config trong configs/*.json + DB thật

Khi chỉ có 1 domain: trả None → luồng chat xử lý bình thường.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Regex nhận diện câu hỏi đa domain (import từ cross_domain.py để không trùng)
from core.cross_domain import detect_cross_domain_request


def plan_cross_domain_query(
    question: str,
    *,
    available_domains: list[str],
) -> list[dict[str, str]] | None:
    """
    Lập kế hoạch query cho từng domain.

    Returns:
        List[{domain_id, sub_question}] nếu nhận diện được đa domain,
        None nếu câu hỏi chỉ thuộc 1 domain (xử lý bình thường).
    """
    if len(available_domains) < 2:
        return None

    q_lower = (question or "").lower()

    # Nhận diện domain trong câu hỏi bằng keywords từng domain
    _DOMAIN_KEYWORDS: dict[str, list[str]] = {
        "finance_vnfdata": [
            "cổ phiếu", "co phieu", "vnfdata", "tài chính", "tai chinh",
            "p/e", "p/b", "roe", "rsi", "macd", "bollinger", "thị trường",
            "chứng khoán", "chung khoan", "vn-index", "vnindex",
        ],
        "it_deployment": [
            "it", "deployment", "dự án it", "du an it", "phần mềm",
            "phan mem", "hệ thống", "he thong", "fsi", "tiến độ", "tien do",
        ],
        "mining_geology": [
            "khai khoáng", "khai khoang", "địa chất", "dia chat",
            "trữ lượng", "tru luong", "hàm lượng", "ham luong",
            "mỏ", "mo khoáng", "quặng",
        ],
    }

    matched: list[str] = []
    for domain_id in available_domains:
        keywords = _DOMAIN_KEYWORDS.get(domain_id, [domain_id.replace("_", " ")])
        if any(kw in q_lower for kw in keywords):
            matched.append(domain_id)

    if len(matched) < 2:
        return None

    # Tách câu hỏi thành sub-question cho từng domain (đơn giản: dùng câu gốc)
    return [
        {"domain_id": d, "sub_question": question}
        for d in matched
    ]


def execute_cross_domain(
    plan: list[dict[str, str]],
    *,
    sql_executor: Any,  # callable(domain_id, question) -> list[dict]
) -> dict[str, Any] | None:
    """
    Thực thi plan, join kết quả Python-side.

    sql_executor: hàm nhận (domain_id, question) → list[dict] rows.

    Returns dict với keys: data, domains_used, join_key, row_count.
    """
    domain_results: dict[str, list[dict[str, Any]]] = {}
    for step in plan:
        domain_id = step["domain_id"]
        sub_q = step["sub_question"]
        try:
            rows = sql_executor(domain_id, sub_q)
            if rows:
                domain_results[domain_id] = rows
        except Exception as exc:
            logger.warning("Cross-domain query failed for %s: %s", domain_id, exc)

    if not domain_results:
        return None

    if len(domain_results) == 1:
        rows = next(iter(domain_results.values()))
        return {
            "data": rows,
            "domains_used": list(domain_results.keys()),
            "join_key": None,
            "row_count": len(rows),
        }

    # Thử join theo cột chung
    domain_ids = list(domain_results.keys())
    rows_a = domain_results[domain_ids[0]]
    rows_b = domain_results[domain_ids[1]]
    joined = _python_join(rows_a, rows_b)

    return {
        "data": joined,
        "domains_used": domain_ids,
        "join_key": _find_join_key(rows_a, rows_b),
        "row_count": len(joined),
    }


def _find_join_key(
    rows_a: list[dict[str, Any]],
    rows_b: list[dict[str, Any]],
) -> str | None:
    """Tìm cột chung đầu tiên để join (ưu tiên ticker/mã/id/code)."""
    if not rows_a or not rows_b:
        return None
    keys_a = set(str(k).lower() for k in rows_a[0])
    keys_b = set(str(k).lower() for k in rows_b[0])
    common = keys_a & keys_b
    for priority in ("ticker", "ma", "code", "id", "company", "symbol"):
        if priority in common:
            return priority
    return next(iter(common), None)


def _python_join(
    rows_a: list[dict[str, Any]],
    rows_b: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Hash join rows_a ⋈ rows_b theo cột chung đầu tiên."""
    join_key = _find_join_key(rows_a, rows_b)
    if not join_key:
        # Không có cột chung → ghép nối tiếp
        return rows_a + rows_b

    # Normalize: tìm key thực (case-sensitive) trong row
    def _real_key(row: dict[str, Any], target: str) -> str | None:
        for k in row:
            if str(k).lower() == target:
                return k
        return None

    # Build index từ rows_b
    b_index: dict[Any, dict[str, Any]] = {}
    for row in rows_b:
        rk = _real_key(row, join_key)
        if rk:
            b_index[row[rk]] = row

    # Join
    result: list[dict[str, Any]] = []
    for row in rows_a:
        rk = _real_key(row, join_key)
        v = row.get(rk) if rk else None
        extra = b_index.get(v, {})
        # rows_a overwrites rows_b trên key trùng
        result.append({**extra, **row})

    return result
