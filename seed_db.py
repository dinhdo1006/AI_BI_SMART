"""Tạo mock_database.db và bơm dữ liệu phong phú để demo BI (3 domain)."""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH: Path = Path(__file__).resolve().parent / "mock_database.db"
_SEED_RANDOM = random.Random(42)

_VNFDATA_TABLES = (
    "gia_co_phieu_lich_su",
    "bctc_tong_hop",
    "chi_so_tai_chinh",
    "doanh_nghiep",
)

# 12 mã HoSE — đủ để test top/so sánh/ngành
_COMPANIES: list[tuple] = [
    ("FPT", "FPT Corporation", "HoSE", "Công nghệ thông tin", "Phi tài chính", "2006-12-13", 1708.0, 72.5),
    ("VCB", "Ngân hàng TMCP Ngoại thương Việt Nam", "HoSE", "Ngân hàng", "Ngân hàng", "2009-06-30", 8356.0, 18.2),
    ("HPG", "Tập đoàn Hòa Phát", "HoSE", "Thép & kim loại", "Phi tài chính", "2007-11-15", 5700.0, 45.0),
    ("SSI", "Công ty CP Chứng khoán SSI", "HoSE", "Chứng khoán", "Chứng khoán", "2006-11-29", 2080.0, 55.8),
    ("MWG", "Công ty CP Đầu tư Thế Giới Di Động", "HoSE", "Bán lẻ", "Phi tài chính", "2014-12-05", 1860.0, 38.6),
    ("VNM", "Vinamilk", "HoSE", "Thực phẩm & đồ uống", "Phi tài chính", "2006-01-11", 2080.0, 48.0),
    ("TCB", "Techcombank", "HoSE", "Ngân hàng", "Ngân hàng", "2018-06-04", 3510.0, 22.0),
    ("BID", "BIDV", "HoSE", "Ngân hàng", "Ngân hàng", "2007-07-26", 3418.0, 15.5),
    ("GAS", "PV Gas", "HoSE", "Dầu khí", "Phi tài chính", "2011-08-04", 2400.0, 52.0),
    ("MSN", "Masan Group", "HoSE", "Thực phẩm", "Phi tài chính", "2011-11-05", 5920.0, 41.0),
    ("REE", "REE Corporation", "HoSE", "Bất động sản & CN", "Phi tài chính", "2000-07-28", 1380.0, 62.0),
    ("PNJ", "PNJ", "HoSE", "Bán lẻ", "Phi tài chính", "2006-12-15", 680.0, 58.0),
]

_QUARTERS = ("Q1/2025", "Q2/2025", "Q3/2025", "Q4/2025", "Q1/2026")

# (ma_cp, base_price, base_volume, base_doanh_thu_ty, pe, roe, von_hoa_ty)
_FIN_PROFILES: dict[str, tuple] = {
    "FPT": (128_500.0, 3_200_000.0, 11_800.0, 18.5, 22.8, 185.2, 0.95),
    "VCB": (62_800.0, 5_800_000.0, 16_500.0, 12.8, 18.2, 512.0, 0.72),
    "HPG": (26_450.0, 12_500_000.0, 30_200.0, 9.2, 14.5, 198.5, 1.15),
    "SSI": (38_200.0, 4_100_000.0, 2_450.0, 15.0, 19.6, 45.2, 1.28),
    "MWG": (71_500.0, 2_800_000.0, 38_500.0, 11.2, 16.8, 125.8, 0.88),
    "VNM": (58_200.0, 1_900_000.0, 14_200.0, 14.5, 20.1, 168.0, 0.65),
    "TCB": (24_800.0, 8_200_000.0, 12_800.0, 10.5, 17.5, 142.0, 1.05),
    "BID": (38_500.0, 6_500_000.0, 15_600.0, 11.8, 16.2, 198.0, 0.82),
    "GAS": (92_400.0, 1_200_000.0, 18_900.0, 13.2, 15.8, 210.0, 0.58),
    "MSN": (78_600.0, 2_100_000.0, 22_400.0, 16.8, 13.5, 95.0, 1.22),
    "REE": (48_900.0, 980_000.0, 5_600.0, 12.2, 11.8, 32.5, 0.92),
    "PNJ": (88_200.0, 850_000.0, 8_200.0, 13.5, 18.5, 28.4, 0.78),
}


def _trading_days(count: int, end: date | None = None) -> list[str]:
    """Sinh danh sách ngày giao dịch (bỏ T7/CN)."""
    if end is None:
        end = date(2026, 7, 7)
    days: list[str] = []
    d = end
    while len(days) < count:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d -= timedelta(days=1)
    return list(reversed(days))


def _weekly_mondays(weeks: int, end: date | None = None) -> list[str]:
    if end is None:
        end = date(2026, 7, 7)
    mondays: list[str] = []
    d = end
    while len(mondays) < weeks:
        if d.weekday() == 0:
            mondays.append(d.isoformat())
        d -= timedelta(days=1)
    return list(reversed(mondays))


def _seed_vnfdata(cur: sqlite3.Cursor) -> dict[str, int]:
    for tbl in _VNFDATA_TABLES:
        cur.execute(f"DELETE FROM {tbl}")

    cur.executemany(
        """
        INSERT INTO doanh_nghiep
        (ma_cp, ten_dn, san_giao_dich, nganh, loai_hinh_dn, ngay_niem_yet, von_dieu_le, free_float)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        _COMPANIES,
    )

    bctc_rows: list[tuple] = []
    bctc_id = 1
    for ma_cp, profile in _FIN_PROFILES.items():
        base_dt = profile[3]
        for qi, ky in enumerate(_QUARTERS):
            growth = 1.0 + qi * 0.035 + _SEED_RANDOM.uniform(-0.02, 0.04)
            dt = round(base_dt * growth, 1)
            gia_von = round(dt * 0.72, 1)
            ln_ttt = round(dt * 0.14, 1)
            ln_stt = round(ln_ttt * 0.8, 1)
            ts = round(dt * 5.2, 1)
            no = round(ts * 0.38, 1)
            vcs = round(ts - no, 1)
            bctc_rows.append(
                (bctc_id, ma_cp, ky, dt, gia_von, ln_ttt, ln_stt, ts, no, vcs)
            )
            bctc_id += 1

    cur.executemany(
        """
        INSERT INTO bctc_tong_hop
        (id, ma_cp, ky_bc, doanh_thu_thuan, gia_von, ln_truoc_thue, ln_sau_thue,
         tong_tai_san, tong_no, von_chu_so_huu)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        bctc_rows,
    )

    ratio_rows = [
        (
            ma,
            prof[3],
            round(prof[3] / 4.5, 2),
            round(prof[0] / prof[3], 0),
            prof[4],
            round(prof[4] * 0.45, 2),
            prof[5] * 1000,
            prof[6],
        )
        for ma, prof in _FIN_PROFILES.items()
    ]
    cur.executemany(
        """
        INSERT INTO chi_so_tai_chinh
        (ma_cp, pe, pb, eps, roe, roa, von_hoa, he_so_beta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ratio_rows,
    )

    trading_days = _trading_days(60)
    price_rows: list[tuple] = []
    row_id = 1
    for ma_cp, profile in _FIN_PROFILES.items():
        base_px, base_vol = profile[0], profile[1]
        prev_close = base_px
        # FPT: xu hướng tăng 3 tuần; HPG: volume đột biến phiên cuối
        for i, ngay in enumerate(trading_days):
            if ma_cp == "FPT" and i >= len(trading_days) - 15:
                drift = 1.006
            elif ma_cp == "HPG" and i == len(trading_days) - 1:
                drift = 1.002
            else:
                drift = 1.0 + ((i % 7) - 3) * 0.003

            close = round(prev_close * drift, 0)
            open_px = round(prev_close * (1 + 0.001 * (i % 3 - 1)), 0)
            high = round(max(open_px, close) * 1.01, 0)
            low = round(min(open_px, close) * 0.99, 0)
            adj = round(close * 0.998, 0)
            vol_mult = 2.8 if (ma_cp == "HPG" and i == len(trading_days) - 1) else (
                0.85 + (i % 5) * 0.06
            )
            vol = round(base_vol * vol_mult, 0)
            gia_tri = round(vol * close / 1_000_000_000, 2)
            bien_dong = (
                round((close - prev_close) / prev_close * 100, 2) if i > 0 else 0.0
            )
            price_rows.append(
                (row_id, ma_cp, ngay, open_px, high, low, close, adj, vol, gia_tri, bien_dong)
            )
            row_id += 1
            prev_close = close

    cur.executemany(
        """
        INSERT INTO gia_co_phieu_lich_su
        (id, ma_cp, ngay_gd, gia_mo, gia_cao, gia_thap, gia_dong_cua,
         gia_dieu_chinh, khoi_luong_gd, gia_tri_gd, bien_dong_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        price_rows,
    )

    return {
        "doanh_nghiep": len(_COMPANIES),
        "bctc_tong_hop": len(bctc_rows),
        "chi_so_tai_chinh": len(ratio_rows),
        "gia_co_phieu_lich_su": len(price_rows),
    }


def _seed_it(cur: sqlite3.Cursor) -> dict[str, int]:
    projects = [
        (1, "ERP Migration Phase 1", "in_progress", "Nguyen An", "Finance IT", 420000, "2026-01-15", "High"),
        (2, "Data Lake Modernization", "in_progress", "Tran Binh", "Data Platform", 310000, "2026-02-01", "High"),
        (3, "SSO Integration", "completed", "Le Chi", "Security", 95000, "2025-11-01", "Medium"),
        (4, "Legacy CRM Shutdown", "on_hold", "Pham Dung", "Sales Ops", 60000, "2026-03-10", "Low"),
        (5, "Cloud Cost Optimization", "cancelled", "Hoang Em", "Cloud Ops", 45000, "2026-01-20", "Medium"),
        (6, "HR Self-Service Portal", "in_progress", "Vu Giang", "HR Tech", 180000, "2026-04-01", "Medium"),
        (7, "Warehouse WMS Upgrade", "in_progress", "Do Hai", "Supply Chain", 265000, "2026-02-18", "High"),
        (8, "Customer 360 Dashboard", "completed", "Ngo Lan", "Analytics", 140000, "2025-12-05", "High"),
        (9, "Mobile Banking App v3", "in_progress", "Tran Minh", "Digital Banking", 520000, "2026-03-01", "High"),
        (10, "Network Segmentation", "in_progress", "Le Hoa", "Security", 195000, "2026-02-20", "Medium"),
        (11, "SAP S/4HANA Pilot", "in_progress", "Pham Quan", "Finance IT", 680000, "2026-01-08", "High"),
        (12, "AI Chatbot Platform", "in_progress", "Do Linh", "Data Platform", 240000, "2026-04-15", "Medium"),
        (13, "Legacy Mainframe Decom", "on_hold", "Nguyen Duc", "Infrastructure", 89000, "2026-05-01", "Low"),
        (14, "Vendor Portal Integration", "in_progress", "Hoang Yen", "Supply Chain", 155000, "2026-03-25", "Medium"),
        (15, "Regulatory Reporting Hub", "in_progress", "Vu Khanh", "Compliance", 375000, "2026-02-10", "High"),
    ]

    milestones = ("Kickoff", "Discovery", "Design", "Build", "UAT", "Pilot", "Rollout", "Hypercare")
    progress_rows: list[tuple] = []
    pid = 1
    weeks = _weekly_mondays(14)

    for proj_id, name, status, *_rest in projects:
        if status not in ("in_progress", "completed"):
            continue
        start_pct = 8.0 if status == "in_progress" else 40.0
        target = 100.0 if status == "completed" else 78.0
        # Data Lake & ERP chậm hơn
        if proj_id == 2:
            target = 58.0
        if proj_id == 11:
            target = 42.0

        step = (target - start_pct) / max(1, len(weeks) - 1)
        for wi, wdate in enumerate(weeks):
            pct = round(min(target, start_pct + step * wi), 2)
            ms = milestones[min(wi, len(milestones) - 1)]
            progress_rows.append((pid, proj_id, pct, wdate, ms))
            pid += 1
            if status == "completed" and pct >= 100:
                break

    # on_hold: 2 snapshot
    for proj_id in (4, 13):
        progress_rows.append((pid, proj_id, 12.0, "2026-04-01", "Freeze"))
        pid += 1
        progress_rows.append((pid, proj_id, 15.0, "2026-06-01", "Review"))
        pid += 1

    cur.executemany(
        """
        INSERT INTO projects
        (id, project_name, status, owner, department, budget_usd, start_date, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        projects,
    )
    cur.executemany(
        """
        INSERT INTO fsi_progress (id, project_id, completion_pct, updated_at, milestone)
        VALUES (?, ?, ?, ?, ?)
        """,
        progress_rows,
    )
    return {"projects": len(projects), "fsi_progress": len(progress_rows)}


def _seed_mining(cur: sqlite3.Cursor) -> dict[str, int]:
    areas = [
        (1, "Quang Ninh Coal Basin", "coal", "Quang Ninh", "active"),
        (2, "Lao Cai Copper Belt", "copper", "Lao Cai", "active"),
        (3, "Bong Mieu Gold Field", "gold", "Quang Nam", "exploration"),
        (4, "Thai Nguyen Iron Range", "iron", "Thai Nguyen", "active"),
        (5, "Dak Nong Bauxite Plateau", "bauxite", "Dak Nong", "active"),
        (6, "Campha Coastal Coal", "coal", "Quang Ninh", "active"),
        (7, "Sin Quyen Copper Zone", "copper", "Lao Cai", "exploration"),
        (8, "Nui Phao Multi-Metal", "tungsten", "Thai Nguyen", "active"),
        (9, "Ha Giang Zinc Prospect", "zinc", "Ha Giang", "exploration"),
        (10, "Kon Tum Bauxite South", "bauxite", "Kon Tum", "exploration"),
        (11, "Binh Dinh Titanium Sands", "titanium", "Binh Dinh", "active"),
        (12, "Cao Bang Apatite Mine", "apatite", "Cao Bang", "active"),
    ]

    survey_dates = [
        "2025-08-15", "2025-11-01", "2026-01-20", "2026-04-10", "2026-06-25",
    ]
    reserves_rows: list[tuple] = []
    rid = 1
    for mine_id, _name, mineral, _prov, status in areas:
        surveys = 3 if status == "exploration" else 4
        base_tonnage = 200_000 + mine_id * 85_000
        base_grade = {"gold": 4.2, "copper": 1.9, "coal": 40.0}.get(mineral, 25.0)

        for si in range(surveys):
            growth = 1.0 + si * 0.08 + _SEED_RANDOM.uniform(-0.03, 0.05)
            tonnage = round(base_tonnage * growth, 1)
            depth = round(80 + mine_id * 12 + si * 18, 1)
            grade = round(base_grade * (1 + si * 0.02), 2)
            reserves_rows.append(
                (rid, mine_id, tonnage, depth, grade, survey_dates[si])
            )
            rid += 1

    cur.executemany(
        "INSERT INTO mine_areas (id, area_name, mineral_type, province, status) VALUES (?, ?, ?, ?, ?)",
        areas,
    )
    cur.executemany(
        """
        INSERT INTO reserves (id, mine_id, tonnage, depth_m, grade_pct, surveyed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        reserves_rows,
    )
    return {"mine_areas": len(areas), "reserves": len(reserves_rows)}


def seed() -> None:
    """Tạo schema + seed 3 domain (IT, Mining, VNFDATA Finance)."""
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY,
                project_name TEXT NOT NULL,
                status TEXT NOT NULL,
                owner TEXT NOT NULL,
                department TEXT NOT NULL,
                budget_usd REAL NOT NULL,
                start_date TEXT NOT NULL,
                priority TEXT NOT NULL
            );
            CREATE TABLE fsi_progress (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                completion_pct REAL NOT NULL,
                updated_at TEXT NOT NULL,
                milestone TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE TABLE mine_areas (
                id INTEGER PRIMARY KEY,
                area_name TEXT NOT NULL,
                mineral_type TEXT NOT NULL,
                province TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE reserves (
                id INTEGER PRIMARY KEY,
                mine_id INTEGER NOT NULL,
                tonnage REAL NOT NULL,
                depth_m REAL NOT NULL,
                grade_pct REAL NOT NULL,
                surveyed_at TEXT NOT NULL,
                FOREIGN KEY (mine_id) REFERENCES mine_areas(id)
            );
            CREATE TABLE doanh_nghiep (
                ma_cp TEXT PRIMARY KEY,
                ten_dn TEXT NOT NULL,
                san_giao_dich TEXT NOT NULL,
                nganh TEXT NOT NULL,
                loai_hinh_dn TEXT NOT NULL,
                ngay_niem_yet TEXT NOT NULL,
                von_dieu_le REAL NOT NULL,
                free_float REAL NOT NULL
            );
            CREATE TABLE gia_co_phieu_lich_su (
                id INTEGER PRIMARY KEY,
                ma_cp TEXT NOT NULL,
                ngay_gd TEXT NOT NULL,
                gia_mo REAL NOT NULL,
                gia_cao REAL NOT NULL,
                gia_thap REAL NOT NULL,
                gia_dong_cua REAL NOT NULL,
                gia_dieu_chinh REAL NOT NULL,
                khoi_luong_gd REAL NOT NULL,
                gia_tri_gd REAL NOT NULL,
                bien_dong_pct REAL NOT NULL,
                FOREIGN KEY (ma_cp) REFERENCES doanh_nghiep(ma_cp)
            );
            CREATE TABLE bctc_tong_hop (
                id INTEGER PRIMARY KEY,
                ma_cp TEXT NOT NULL,
                ky_bc TEXT NOT NULL,
                doanh_thu_thuan REAL NOT NULL,
                gia_von REAL NOT NULL,
                ln_truoc_thue REAL NOT NULL,
                ln_sau_thue REAL NOT NULL,
                tong_tai_san REAL NOT NULL,
                tong_no REAL NOT NULL,
                von_chu_so_huu REAL NOT NULL,
                FOREIGN KEY (ma_cp) REFERENCES doanh_nghiep(ma_cp)
            );
            CREATE TABLE chi_so_tai_chinh (
                id INTEGER PRIMARY KEY,
                ma_cp TEXT NOT NULL,
                pe REAL,
                pb REAL,
                eps REAL,
                roe REAL,
                roa REAL,
                von_hoa REAL NOT NULL,
                he_so_beta REAL,
                FOREIGN KEY (ma_cp) REFERENCES doanh_nghiep(ma_cp)
            );
            """
        )

        it_counts = _seed_it(cur)
        mining_counts = _seed_mining(cur)
        fin_counts = _seed_vnfdata(cur)
        conn.commit()

        print(f"[OK] Seeded demo DB: {DB_PATH}")
        print(f"  IT: projects={it_counts['projects']}, fsi_progress={it_counts['fsi_progress']}")
        print(
            f"  Mining: mine_areas={mining_counts['mine_areas']}, "
            f"reserves={mining_counts['reserves']}"
        )
        print(
            f"  VNFDATA: doanh_nghiep={fin_counts['doanh_nghiep']}, "
            f"gia_co_phieu_lich_su={fin_counts['gia_co_phieu_lich_su']}, "
            f"bctc_tong_hop={fin_counts['bctc_tong_hop']}, "
            f"chi_so_tai_chinh={fin_counts['chi_so_tai_chinh']}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
