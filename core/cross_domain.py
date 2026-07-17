"""Phát hiện câu hỏi liên domain khi hệ thống chưa có đủ domain."""

from __future__ import annotations

import re

_CROSS_DOMAIN_RE = re.compile(
    r"("
    r"li[eê]n\s*domain|cross[\s-]*domain|multi[\s-]*domain|"
    r"(it\s*deployment|d[ựu]\s*[áa]n\s*it).{0,40}(t[àa]i\s*ch[íi]nh|vnfdata|ch[ứu]ng\s*kho[áa]n)|"
    r"(t[àa]i\s*ch[íi]nh|vnfdata|ch[ứu]ng\s*kho[áa]n).{0,40}(it\s*deployment|d[ựu]\s*[áa]n\s*it)|"
    r"(mining|kho[áa]ng\s*s[ảa]n|đ[ịi]a\s*ch[ấa]t).{0,40}(t[àa]i\s*ch[íi]nh|it)|"
    r"(t[àa]i\s*ch[íi]nh|it).{0,40}(mining|kho[áa]ng\s*s[ảa]n)"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_OTHER_DOMAIN_ONLY_RE = re.compile(
    r"("
    r"\bit\s*deployment\b|ti[ếe]n\s*[đd][ộo]\s*d[ựu]\s*[áa]n\s*fsi|"
    r"mining\s*&\s*geology|tr[ữu]\s*l[ượuo]ng\s*m[ỏo]|h[àa]m\s*l[ưượuo]ng\s*qu[ặă]ng"
    r")",
    re.IGNORECASE,
)


def detect_cross_domain_request(
    query: str,
    *,
    available_domains: list[str] | None = None,
) -> dict[str, str] | None:
    """
    Nếu user hỏi liên domain / domain chưa có → trả message hướng dẫn.
    Không chặn câu hỏi thuần VNFDATA.
    """
    q = (query or "").strip()
    if not q:
        return None

    domains = [d for d in (available_domains or []) if d != "vnfdata_article_templates"]
    has_finance = any("finance" in d or "vnfdata" in d for d in domains)
    has_it = any("it" in d for d in domains)
    has_mining = any("mining" in d or "geology" in d for d in domains)

    if _CROSS_DOMAIN_RE.search(q):
        missing = []
        if not has_it:
            missing.append("IT Deployment")
        if not has_mining:
            missing.append("Mining & Geology")
        miss = ", ".join(missing) if missing else "domain phụ"
        return {
            "code": "cross_domain_unavailable",
            "message": (
                "Câu hỏi liên domain hiện chưa hỗ trợ đầy đủ. "
                f"Hệ thống đang có dữ liệu thật chủ yếu ở VNFDATA; còn thiếu: {miss}. "
                "Bạn hãy hỏi trong một domain, hoặc bổ sung config domain thứ hai."
            ),
        }

    if _OTHER_DOMAIN_ONLY_RE.search(q) and has_finance and not (has_it or has_mining):
        return {
            "code": "domain_not_connected",
            "message": (
                "Domain IT Deployment / Mining chưa được kết nối dữ liệu thật. "
                "Hiện chỉ domain VNFDATA (tài chính) sẵn sàng — "
                "hãy hỏi về cổ phiếu, chỉ số tài chính, RSI/MACD, hoặc so sánh cùng ngành."
            ),
        }

    return None
