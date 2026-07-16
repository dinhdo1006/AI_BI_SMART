"""Fast-path SQL cho domain demo SQLite — Postgres dùng LLM + entity resolver."""

from __future__ import annotations

import re
import unicodedata

# Chỉ dùng cho schema SQLite demo (ma_cp) — không phải danh sách đóng cho Postgres.
_STOCK_TICKERS = (
    "FPT", "VCB", "HPG", "SSI", "MWG",
    "VNM", "TCB", "BID", "GAS", "MSN", "REE", "PNJ",
)


def _normalize(text: str) -> str:
    lowered = (text or "").lower()
    nfd = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _extract_ticker(query: str, norm: str) -> str | None:
    tickers = _extract_tickers(query, norm)
    return tickers[0] if tickers else None


def _extract_tickers(query: str, norm: str) -> list[str]:
    upper = query.upper()
    found: list[str] = []
    for ticker in _STOCK_TICKERS:
        if re.search(rf"\b{re.escape(ticker)}\b", upper) or ticker.lower() in norm:
            found.append(ticker)
    return found


def _extract_quarter(norm: str) -> str | None:
    km = re.search(r"q([1-4])\s*/\s*(20\d{2})", norm)
    if km:
        return f"Q{km.group(1)}/{km.group(2)}"
    return None


def _extract_limit(norm: str, default: int = 5) -> int:
    m = re.search(r"top\s*(\d+)", norm)
    if m:
        return max(1, min(int(m.group(1)), 30))
    m = re.search(r"(\d+)\s*phien", norm)
    if m:
        return max(1, min(int(m.group(1)), 30))
    m = re.search(r"(\d+)\s*(ma|cp|doanh nghiep)", norm)
    if m:
        return max(1, min(int(m.group(1)), 30))
    return default


def _time_series_asc_sql(inner_sql: str) -> str:
    """Subquery: lấy N phiên mới nhất rồi sort ASC cho chart."""
    return (
        f"SELECT * FROM ({inner_sql}) AS _fp "
        f"ORDER BY ngay_gd ASC"
    )


def _finance_fast_sql(user_query: str, norm: str) -> str | None:
    ticker = _extract_ticker(user_query, norm)
    tickers = _extract_tickers(user_query, norm)

    # So sánh chỉ số tài chính nhiều mã (vốn hóa, P/E, beta, …)
    if len(tickers) >= 2 and (
        "so sanh" in norm or "so sánh" in user_query.lower() or len(tickers) >= 3
    ):
        metric_cols: list[str] = []
        if any(k in norm for k in ("von hoa", "von hóa")):
            metric_cols.append("c.von_hoa AS von_hoa")
        if "pe" in norm or "p/e" in user_query.lower():
            metric_cols.append("c.pe AS pe")
        if "beta" in norm:
            metric_cols.append("c.he_so_beta AS he_so_beta")
        if "pb" in norm or "p/b" in user_query.lower():
            metric_cols.append("c.pb AS pb")
        if "eps" in norm:
            metric_cols.append("c.eps AS eps")
        if any(k in norm for k in ("roe", "roa")):
            if "roe" in norm:
                metric_cols.append("c.roe AS roe")
            if "roa" in norm:
                metric_cols.append("c.roa AS roa")
        if metric_cols:
            in_list = ", ".join(f"'{t}'" for t in tickers[:6])
            cols = ", ".join(metric_cols)
            return (
                "SELECT c.ma_cp AS ma_cp, d.ten_dn AS ten_dn, "
                f"{cols} "
                "FROM chi_so_tai_chinh c JOIN doanh_nghiep d ON c.ma_cp = d.ma_cp "
                f"WHERE c.ma_cp IN ({in_list}) "
                "ORDER BY c.ma_cp ASC"
            )

    # Doanh thu cao nhất nhưng biên LN sau thuế thấp hơn trung bình
    if any(k in norm for k in ("doanh thu", "doanh thu thuan")) and any(
        k in norm for k in ("cao nhat", "cao nhất", "lon nhat", "lớn nhất")
    ) and any(k in norm for k in ("bien", "biên", "loi nhuan", "lợi nhuận", "margin")):
        ky_bc = _extract_quarter(norm)
        if ky_bc:
            return (
                "SELECT b.ma_cp AS ma_cp, d.ten_dn AS ten_dn, "
                f"'{ky_bc}' AS ky_bc, "
                "b.doanh_thu_thuan AS doanh_thu_thuan, b.ln_sau_thue AS ln_sau_thue, "
                "ROUND(b.ln_sau_thue * 100.0 / NULLIF(b.doanh_thu_thuan, 0), 2) AS bien_ln_pct, "
                f"(SELECT AVG(ROUND(ln_sau_thue * 100.0 / NULLIF(doanh_thu_thuan, 0), 2)) "
                f"FROM bctc_tong_hop WHERE ky_bc = '{ky_bc}') AS bien_tb_cac_ma "
                "FROM bctc_tong_hop b JOIN doanh_nghiep d ON b.ma_cp = d.ma_cp "
                f"WHERE b.ky_bc = '{ky_bc}' "
                f"AND b.ma_cp = (SELECT ma_cp FROM bctc_tong_hop WHERE ky_bc = '{ky_bc}' "
                "ORDER BY doanh_thu_thuan DESC LIMIT 1) "
                f"AND ROUND(b.ln_sau_thue * 100.0 / NULLIF(b.doanh_thu_thuan, 0), 2) < ("
                f"SELECT AVG(ROUND(ln_sau_thue * 100.0 / NULLIF(doanh_thu_thuan, 0), 2)) "
                f"FROM bctc_tong_hop WHERE ky_bc = '{ky_bc}')"
            )

    # Top doanh thu thuần theo kỳ (không cần mã CP)
    if any(k in norm for k in ("doanh thu", "doanh thu thuan")) and any(
        k in norm for k in ("cao nhat", "cao nhất", "lon nhat", "lớn nhất", "top")
    ):
        ky_bc = _extract_quarter(norm)
        if ky_bc:
            n = _extract_limit(norm, default=1)
            return (
                "SELECT b.ma_cp AS ma_cp, d.ten_dn AS ten_dn, b.ky_bc AS ky_bc, "
                "b.doanh_thu_thuan AS doanh_thu_thuan, b.ln_sau_thue AS ln_sau_thue, "
                "ROUND(b.ln_sau_thue * 100.0 / NULLIF(b.doanh_thu_thuan, 0), 2) AS bien_ln_pct "
                "FROM bctc_tong_hop b JOIN doanh_nghiep d ON b.ma_cp = d.ma_cp "
                f"WHERE b.ky_bc = '{ky_bc}' "
                f"ORDER BY b.doanh_thu_thuan DESC LIMIT {n}"
            )

    # Top vốn hóa HoSE (không cần mã CP)
    if any(k in norm for k in ("von hoa", "von hóa", "top")) and any(
        k in norm for k in ("hose", "ho se", "san hose")
    ):
        n = _extract_limit(norm, default=5)
        return (
            "SELECT d.ma_cp AS ma_cp, d.ten_dn AS ten_dn, d.nganh AS nganh, "
            "c.von_hoa AS von_hoa, c.pe AS pe, c.eps AS eps "
            "FROM doanh_nghiep d JOIN chi_so_tai_chinh c ON d.ma_cp = c.ma_cp "
            "WHERE d.san_giao_dich = 'HoSE' "
            f"ORDER BY c.von_hoa DESC LIMIT {n}"
        )

    # So sánh ROE và ROA nhiều mã
    if any(k in norm for k in ("roe", "roa")) and (
        "so sanh" in norm or "so sánh" in user_query.lower() or ticker
    ):
        if not tickers and ticker:
            tickers = [ticker]
        if len(tickers) >= 2:
            in_list = ", ".join(f"'{t}'" for t in tickers[:6])
            return (
                "SELECT c.ma_cp AS ma_cp, d.ten_dn AS ten_dn, "
                "c.roe AS roe, c.roa AS roa "
                "FROM chi_so_tai_chinh c JOIN doanh_nghiep d ON c.ma_cp = d.ma_cp "
                f"WHERE c.ma_cp IN ({in_list}) "
                "ORDER BY c.ma_cp ASC"
            )

    # Top P/E thấp nhất trên HoSE
    if any(k in norm for k in ("pe", "p/e")) and any(
        k in norm for k in ("thap nhat", "thấp nhất", "re nhat", "rẻ nhất", "top")
    ):
        n = _extract_limit(norm, default=5)
        return (
            "SELECT d.ma_cp AS ma_cp, d.ten_dn AS ten_dn, d.nganh AS nganh, "
            "c.pe AS pe, c.eps AS eps, c.von_hoa AS von_hoa "
            "FROM doanh_nghiep d JOIN chi_so_tai_chinh c ON d.ma_cp = c.ma_cp "
            "WHERE d.san_giao_dich = 'HoSE' AND c.pe IS NOT NULL "
            f"ORDER BY c.pe ASC LIMIT {n}"
        )

    # Mã tăng mạnh nhất / biến động lớn nhất trong phiên gần nhất
    if any(k in norm for k in ("tang manh", "tăng mạnh", "bien dong", "biến động")) and any(
        k in norm for k in ("nhat", "nhất", "lon nhat", "lớn nhất", "cao nhat", "cao nhất")
    ):
        return (
            "SELECT g.ma_cp AS ma_cp, d.ten_dn AS ten_dn, g.ngay_gd AS ngay_gd, "
            "g.gia_dong_cua AS gia_dong_cua, g.bien_dong_pct AS bien_dong_pct, "
            "g.khoi_luong_gd AS khoi_luong_gd "
            "FROM gia_co_phieu_lich_su g JOIN doanh_nghiep d ON g.ma_cp = d.ma_cp "
            "WHERE g.ngay_gd = (SELECT MAX(ngay_gd) FROM gia_co_phieu_lich_su) "
            "ORDER BY g.bien_dong_pct DESC LIMIT 5"
        )

    # So sánh EPS nhiều mã
    if "eps" in norm and (
        "so sanh" in norm or "so sánh" in user_query.lower() or len(tickers) >= 2
    ):
        codes = tickers if len(tickers) >= 2 else _STOCK_TICKERS[:3]
        in_list = ", ".join(f"'{t}'" for t in codes[:6])
        return (
            "SELECT c.ma_cp AS ma_cp, d.ten_dn AS ten_dn, "
            "c.eps AS eps, c.pe AS pe, c.von_hoa AS von_hoa "
            "FROM chi_so_tai_chinh c JOIN doanh_nghiep d ON c.ma_cp = d.ma_cp "
            f"WHERE c.ma_cp IN ({in_list}) "
            "ORDER BY c.eps DESC"
        )

    if not ticker:
        return None

    # Cơ cấu tài sản (pie) — 1 mã, BCTC mới nhất
    if any(k in norm for k in ("co cau", "cơ cấu", "tai san", "tài sản", "von chu", "vốn chủ")):
        return (
            "SELECT b.ma_cp AS ma_cp, d.ten_dn AS ten_dn, b.ky_bc AS ky_bc, "
            "b.tong_tai_san AS tong_tai_san, b.von_chu_so_huu AS von_chu_so_huu, "
            "b.tong_no AS tong_no "
            "FROM bctc_tong_hop b JOIN doanh_nghiep d ON b.ma_cp = d.ma_cp "
            f"WHERE b.ma_cp = '{ticker}' "
            "ORDER BY b.ky_bc DESC LIMIT 1"
        )

    # Giá điều chỉnh từ đầu tháng
    if any(k in norm for k in ("dieu chinh", "điều chỉnh", "dau thang", "đầu tháng")):
        inner = (
            "SELECT g.ma_cp AS ma_cp, g.ngay_gd AS ngay_gd, "
            "g.gia_dieu_chinh AS gia_dieu_chinh, g.gia_dong_cua AS gia_dong_cua, "
            "g.bien_dong_pct AS bien_dong_pct "
            f"FROM gia_co_phieu_lich_su g WHERE g.ma_cp = '{ticker}' "
            "AND g.ngay_gd >= date('now', 'start of month') "
            "ORDER BY g.ngay_gd DESC LIMIT 31"
        )
        return _time_series_asc_sql(inner)

    # Giá / giao dịch N phiên gần nhất (combo chart)
    if any(
        k in norm
        for k in (
            "phien",
            "gia",
            "giao dich",
            "dien bien",
            "dong cua",
            "khoi luong",
            "bieu do",
        )
    ):
        n = _extract_limit(norm, default=5)
        inner = (
            "SELECT g.ma_cp AS ma_cp, g.ngay_gd AS ngay_gd, "
            "g.gia_mo AS gia_mo, g.gia_cao AS gia_cao, g.gia_thap AS gia_thap, "
            "g.gia_dong_cua AS gia_dong_cua, g.khoi_luong_gd AS khoi_luong_gd, "
            "g.gia_tri_gd AS gia_tri_gd, g.bien_dong_pct AS bien_dong_pct "
            f"FROM gia_co_phieu_lich_su g WHERE g.ma_cp = '{ticker}' "
            f"ORDER BY g.ngay_gd DESC LIMIT {n}"
        )
        return _time_series_asc_sql(inner)

    # BCTC một mã + kỳ (vd: FPT Q1/2026)
    if any(k in norm for k in ("doanh thu", "loi nhuan", "bctc", "tai chinh")):
        ky_fmt = _extract_quarter(norm)
        if ky_fmt:
            return (
                "SELECT b.ma_cp AS ma_cp, d.ten_dn AS ten_dn, b.ky_bc AS ky_bc, "
                "b.doanh_thu_thuan AS doanh_thu_thuan, b.ln_sau_thue AS ln_sau_thue, "
                "b.ln_truoc_thue AS ln_truoc_thue "
                "FROM bctc_tong_hop b JOIN doanh_nghiep d ON b.ma_cp = d.ma_cp "
                f"WHERE b.ma_cp = '{ticker}' AND b.ky_bc = '{ky_fmt}'"
            )

    return None


def _finance_pg_fast_sql(user_query: str, norm: str) -> str | None:
    """
    Postgres / vnfdatadb: không map intent → SQL cứng.
    Schema đúng + Schema RAG + entity resolver (mã từ DB) → LLM sinh SQL.
    """
    return None


def try_fast_sql(
    domain_id: str,
    user_query: str,
    *,
    db_url: str | None = None,
) -> str | None:
    """
    Fast-path chỉ cho schema SQLite demo.
    finance_vnfdata + PostgreSQL → None (tránh hardcode câu hỏi).
    """
    from core.db_dialect import detect_dialect

    norm = _normalize(user_query)
    dialect = detect_dialect(db_url or "")

    if domain_id == "finance_vnfdata":
        if dialect == "postgresql":
            return _finance_pg_fast_sql(user_query, norm)
        return _finance_fast_sql(user_query, norm)

    return None
