"""Load metadata cấu hình domain từ thư mục configs/ + biến môi trường."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Thư mục gốc dự án & configs/
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
_CONFIGS_DIR: Path = _PROJECT_ROOT / "configs"

# Nạp .env một lần khi import module (ưu tiên hơn JSON cho db_url)
load_dotenv(_PROJECT_ROOT / ".env")


def _env_db_url_key(domain_id: str) -> str:
    """Map domain_id → tên biến môi trường, vd: it_deployment → IT_DEPLOYMENT_DB_URL."""
    return f"{domain_id.upper()}_DB_URL"


def load_domain_config(domain_id: str) -> dict[str, Any]:
    """
    Đọc file JSON cấu hình theo domain_id.

    db_url: ưu tiên biến môi trường {DOMAIN_ID}_DB_URL trong .env;
            nếu không có thì fallback về giá trị trong JSON.

    Args:
        domain_id: Tên domain (vd: "it_deployment", "mining_geology").
                   Tương ứng với file configs/{domain_id}.json.

    Returns:
        Dict chứa db_url, ddl_schema, data_dictionary, few_shot_examples.

    Raises:
        FileNotFoundError: Khi không tìm thấy file config.
        ValueError: Khi JSON không hợp lệ hoặc thiếu trường bắt buộc.
    """
    config_path = _CONFIGS_DIR / f"{domain_id}.json"

    if not config_path.is_file():
        raise FileNotFoundError(
            f"Không tìm thấy config cho domain '{domain_id}'. "
            f"Đường dẫn kỳ vọng: {config_path}"
        )

    with config_path.open(encoding="utf-8") as f:
        config: dict[str, Any] = json.load(f)

    # Kiểm tra các trường bắt buộc để fail-fast
    required_keys = ("db_url", "ddl_schema", "data_dictionary", "few_shot_examples")
    missing = [k for k in required_keys if k not in config]
    if missing:
        raise ValueError(
            f"Config '{domain_id}' thiếu các trường bắt buộc: {', '.join(missing)}"
        )

    # Ưu tiên DB URL từ .env — dễ chuyển sang PostgreSQL sau này
    env_url = os.getenv(_env_db_url_key(domain_id), "").strip()
    if env_url:
        config["db_url"] = env_url

    return config


def list_available_domains() -> list[str]:
    """Liệt kê các domain_id có sẵn trong thư mục configs/."""
    return sorted(p.stem for p in _CONFIGS_DIR.glob("*.json"))
