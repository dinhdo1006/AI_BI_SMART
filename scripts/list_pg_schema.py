"""
Liệt kê toàn bộ bảng + cột từ FINANCE_VNFDATA_DB_URL (PostgreSQL).
Chạy trên máy/server đã kết nối được vnfdatadb:

    python scripts/list_pg_schema.py

Output:
    docs/vnfdatadb_schema.json
    docs/vnfdatadb_tables.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
import os

load_dotenv(ROOT / ".env")

from core.schema_introspection import check_db_connection, introspect_schema


def main() -> int:
    url = (os.getenv("FINANCE_VNFDATA_DB_URL") or "").strip()
    if not url or url.startswith("sqlite"):
        print(
            "FINANCE_VNFDATA_DB_URL chưa trỏ PostgreSQL.\n"
            "Ví dụ: postgresql+psycopg2://postgres:PASS@127.0.0.1:5432/vnfdatadb"
        )
        return 1

    ok, detail = check_db_connection(url)
    if not ok:
        print(f"Không kết nối được DB:\n{detail}")
        return 1

    tables = introspect_schema(url)
    out_dir = ROOT / "docs"
    out_dir.mkdir(exist_ok=True)

    payload = {
        "database_url_host": url.split("@")[-1] if "@" in url else "(hidden)",
        "table_count": len(tables),
        "tables": {
            name: [
                {
                    "name": c.name,
                    "type": c.type_sql,
                    "nullable": c.nullable,
                    "pk": c.is_pk,
                }
                for c in info.columns
            ]
            for name, info in sorted(tables.items())
        },
    }
    json_path = out_dir / "vnfdatadb_schema.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        f"# Schema vnfdatadb — {len(tables)} bảng",
        "",
        "| # | Bảng | Số cột | Cột (rút gọn) |",
        "|---|------|--------|---------------|",
    ]
    for i, name in enumerate(sorted(tables), start=1):
        cols = tables[name].columns
        preview = ", ".join(c.name for c in cols[:10])
        if len(cols) > 10:
            preview += f", … (+{len(cols) - 10})"
        lines.append(f"| {i} | `{name}` | {len(cols)} | {preview} |")

    lines.append("")
    lines.append("## Chi tiết từng bảng")
    lines.append("")
    for name in sorted(tables):
        lines.append(f"### `{name}`")
        lines.append("")
        lines.append("| Cột | Type | PK | Nullable |")
        lines.append("|-----|------|----|----------|")
        for c in tables[name].columns:
            lines.append(
                f"| `{c.name}` | {c.type_sql} | "
                f"{'Y' if c.is_pk else ''} | {'Y' if c.nullable else 'N'} |"
            )
        lines.append("")

    md_path = out_dir / "vnfdatadb_tables.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"OK — {len(tables)} bảng")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")
    print("\nDanh sách tên bảng:")
    for name in sorted(tables):
        print(f"  - {name} ({len(tables[name].columns)} cols)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
