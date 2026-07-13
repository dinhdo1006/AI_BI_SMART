"""Đọc metadata schema từ DB (SQLite / PostgreSQL)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from core.db_dialect import SqlDialect, detect_dialect
from core.db_engine import get_engine


@dataclass
class ColumnInfo:
    name: str
    type_sql: str
    nullable: bool = True
    is_pk: bool = False


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)


def introspect_schema(db_url: str) -> dict[str, TableInfo]:
    """
    Trả về map tên_bảng → TableInfo từ DB thật.
    Fallback rỗng nếu không kết nối được.
    """
    try:
        engine = get_engine(db_url)
        inspector = inspect(engine)
        tables: dict[str, TableInfo] = {}
        for table_name in inspector.get_table_names():
            if table_name.startswith("sqlite_"):
                continue
            cols: list[ColumnInfo] = []
            pk_cols = set(inspector.get_pk_constraint(table_name).get("constrained_columns") or [])
            for col in inspector.get_columns(table_name):
                cols.append(
                    ColumnInfo(
                        name=col["name"],
                        type_sql=str(col.get("type", "TEXT")),
                        nullable=bool(col.get("nullable", True)),
                        is_pk=col["name"] in pk_cols,
                    )
                )
            tables[table_name] = TableInfo(name=table_name, columns=cols)
        return tables
    except SQLAlchemyError:
        return {}


def tables_to_ddl(tables: dict[str, TableInfo], dialect: SqlDialect) -> str:
    """Sinh CREATE TABLE đơn giản từ metadata introspection."""
    if not tables:
        return ""

    parts: list[str] = []
    for name in sorted(tables.keys()):
        tbl = tables[name]
        col_defs: list[str] = []
        for col in tbl.columns:
            suffix = ""
            if col.is_pk:
                suffix = " PRIMARY KEY"
            elif not col.nullable:
                suffix = " NOT NULL"
            col_defs.append(f"  {col.name} {col.type_sql}{suffix}")
        parts.append(f"CREATE TABLE {name} (\n" + ",\n".join(col_defs) + "\n);")
    return "\n\n".join(parts)


def check_db_connection(db_url: str) -> tuple[bool, str]:
    """Ping DB — dùng cho health check."""
    try:
        engine = get_engine(db_url)
        dialect = detect_dialect(db_url)
        with engine.connect() as conn:
            if dialect == "postgresql":
                conn.execute(text("SELECT 1"))
            else:
                conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:
        return False, str(exc)
