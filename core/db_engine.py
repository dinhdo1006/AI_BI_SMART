"""Cache SQLAlchemy Engine theo db_url — tránh tạo/xóa mỗi request."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from core.db_dialect import detect_dialect

_engines: dict[str, Engine] = {}


def get_engine(db_url: str) -> Engine:
    """
    Tạo / tái sử dụng Engine.

    - PostgreSQL: pool_size + max_overflow (nhiều user Streamlit/API).
    - SQLite: không dùng check_same_thread / pool Postgres (SQLite khác cơ chế).
    - Không truyền connect_args đặc thù SQLite vào Postgres.
    """
    if db_url not in _engines:
        dialect = detect_dialect(db_url)
        kwargs: dict = {
            "future": True,
            "pool_pre_ping": True,
        }
        if dialect == "postgresql":
            kwargs.update(
                {
                    "pool_size": 10,
                    "max_overflow": 20,
                    "pool_recycle": 1800,
                }
            )
        # SQLite: để SQLAlchemy mặc định (StaticPool / NullPool tùy URL).
        # Không set check_same_thread — tránh lẫn sang Postgres.
        _engines[db_url] = create_engine(db_url, **kwargs)
    return _engines[db_url]


def clear_engine_cache(db_url: str | None = None) -> None:
    """Đóng engine cache (khi đổi URL / test)."""
    global _engines
    if db_url:
        engine = _engines.pop(db_url, None)
        if engine is not None:
            engine.dispose()
        return
    for eng in _engines.values():
        eng.dispose()
    _engines = {}
