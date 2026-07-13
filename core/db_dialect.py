"""Nhận diện dialect SQL từ chuỗi kết nối SQLAlchemy."""

from __future__ import annotations

from typing import Literal

SqlDialect = Literal["sqlite", "postgresql", "unknown"]


def detect_dialect(db_url: str) -> SqlDialect:
    lower = (db_url or "").lower()
    if lower.startswith("sqlite"):
        return "sqlite"
    if lower.startswith("postgresql") or lower.startswith("postgres"):
        return "postgresql"
    return "unknown"


def dialect_label(dialect: SqlDialect) -> str:
    if dialect == "postgresql":
        return "PostgreSQL"
    if dialect == "sqlite":
        return "SQLite"
    return "SQL"
