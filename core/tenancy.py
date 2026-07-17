"""Multi-tenant store — tenants, users, API keys (SQLite local)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.rbac import normalize_role

_LOCK = threading.Lock()
_DB_PATH = Path(__file__).resolve().parent.parent / ".cache" / "tenancy.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_secret(secret: str) -> str:
    salt = os.getenv("TENANCY_HASH_SALT", "ai-bi-smart-tenancy").encode("utf-8")
    return hashlib.sha256(salt + secret.encode("utf-8")).hexdigest()


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            branding_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            email TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            UNIQUE(tenant_id, email),
            FOREIGN KEY(tenant_id) REFERENCES tenants(id)
        );
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            user_id TEXT,
            name TEXT NOT NULL,
            key_prefix TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(tenant_id) REFERENCES tenants(id)
        );
        """
    )
    conn.commit()
    return conn


def is_multi_tenant_enabled() -> bool:
    return os.getenv("AUTH_MULTI_TENANT", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def ensure_default_tenant() -> dict[str, Any]:
    """Seed tenant mặc định + admin nếu DB trống."""
    with _LOCK:
        conn = _conn()
        try:
            row = conn.execute("SELECT id FROM tenants LIMIT 1").fetchone()
            if row:
                return get_tenant(str(row["id"])) or {}

            tenant_id = "tenant_default"
            admin_email = (
                os.getenv("DEFAULT_ADMIN_EMAIL", "admin@local").strip().lower()
            )
            admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123").strip()
            admin_name = os.getenv("DEFAULT_ADMIN_NAME", "Admin").strip() or "Admin"
            created = _now()
            branding = {
                "product_name": os.getenv("BRAND_PRODUCT_NAME", "AI BI Smart"),
                "primary_color": os.getenv("BRAND_PRIMARY_COLOR", "#0f766e"),
                "logo_url": os.getenv("BRAND_LOGO_URL", ""),
            }
            conn.execute(
                """
                INSERT INTO tenants (id, name, slug, branding_json, created_at, active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    tenant_id,
                    os.getenv("DEFAULT_TENANT_NAME", "Default Tenant"),
                    "default",
                    json.dumps(branding, ensure_ascii=False),
                    created,
                ),
            )
            user_id = uuid.uuid4().hex[:12]
            conn.execute(
                """
                INSERT INTO users
                (id, tenant_id, email, name, role, password_hash, created_at, active)
                VALUES (?, ?, ?, ?, 'admin', ?, ?, 1)
                """,
                (
                    user_id,
                    tenant_id,
                    admin_email,
                    admin_name,
                    _hash_secret(admin_password),
                    created,
                ),
            )
            # API key đọc được 1 lần khi seed
            raw_key = f"abi_{secrets.token_urlsafe(24)}"
            key_id = uuid.uuid4().hex[:12]
            conn.execute(
                """
                INSERT INTO api_keys
                (id, tenant_id, user_id, name, key_prefix, key_hash, role, created_at, active)
                VALUES (?, ?, ?, ?, ?, ?, 'admin', ?, 1)
                """,
                (
                    key_id,
                    tenant_id,
                    user_id,
                    "Default admin key",
                    raw_key[:10],
                    _hash_secret(raw_key),
                    created,
                ),
            )
            conn.commit()
            return {
                "id": tenant_id,
                "admin_email": admin_email,
                "admin_password": admin_password,
                "api_key": raw_key,
                "branding": branding,
            }
        finally:
            conn.close()


def create_tenant(
    *,
    name: str,
    slug: str | None = None,
    branding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tenant_id = f"tenant_{uuid.uuid4().hex[:10]}"
    slug_val = (slug or name).strip().lower().replace(" ", "-")[:40] or tenant_id
    created = _now()
    brand = branding or {
        "product_name": name,
        "primary_color": "#0f766e",
        "logo_url": "",
    }
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(
                """
                INSERT INTO tenants (id, name, slug, branding_json, created_at, active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    tenant_id,
                    name.strip() or tenant_id,
                    slug_val,
                    json.dumps(brand, ensure_ascii=False),
                    created,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return get_tenant(tenant_id) or {"id": tenant_id}


def list_tenants() -> list[dict[str, Any]]:
    with _LOCK:
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT id, name, slug, branding_json, created_at, active FROM tenants ORDER BY created_at"
            ).fetchall()
        finally:
            conn.close()
    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "name": r["name"],
                "slug": r["slug"],
                "branding": json.loads(r["branding_json"] or "{}"),
                "created_at": r["created_at"],
                "active": bool(r["active"]),
            }
        )
    return out


def get_tenant(tenant_id: str) -> dict[str, Any] | None:
    with _LOCK:
        conn = _conn()
        try:
            r = conn.execute(
                "SELECT id, name, slug, branding_json, created_at, active FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
        finally:
            conn.close()
    if not r:
        return None
    return {
        "id": r["id"],
        "name": r["name"],
        "slug": r["slug"],
        "branding": json.loads(r["branding_json"] or "{}"),
        "created_at": r["created_at"],
        "active": bool(r["active"]),
    }


def update_tenant_branding(tenant_id: str, branding: dict[str, Any]) -> dict[str, Any] | None:
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(
                "UPDATE tenants SET branding_json = ? WHERE id = ?",
                (json.dumps(branding, ensure_ascii=False), tenant_id),
            )
            conn.commit()
        finally:
            conn.close()
    return get_tenant(tenant_id)


def create_user(
    *,
    tenant_id: str,
    email: str,
    name: str,
    role: str,
    password: str,
) -> dict[str, Any]:
    user_id = uuid.uuid4().hex[:12]
    created = _now()
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(
                """
                INSERT INTO users
                (id, tenant_id, email, name, role, password_hash, created_at, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    user_id,
                    tenant_id,
                    email.strip().lower(),
                    name.strip() or email,
                    normalize_role(role),
                    _hash_secret(password),
                    created,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return get_user(user_id) or {"id": user_id}


def list_users(tenant_id: str) -> list[dict[str, Any]]:
    with _LOCK:
        conn = _conn()
        try:
            rows = conn.execute(
                """
                SELECT id, tenant_id, email, name, role, created_at, active
                FROM users WHERE tenant_id = ? ORDER BY created_at
                """,
                (tenant_id,),
            ).fetchall()
        finally:
            conn.close()
    return [
        {
            "id": r["id"],
            "tenant_id": r["tenant_id"],
            "email": r["email"],
            "name": r["name"],
            "role": r["role"],
            "created_at": r["created_at"],
            "active": bool(r["active"]),
        }
        for r in rows
    ]


def get_user(user_id: str) -> dict[str, Any] | None:
    with _LOCK:
        conn = _conn()
        try:
            r = conn.execute(
                """
                SELECT id, tenant_id, email, name, role, created_at, active
                FROM users WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
        finally:
            conn.close()
    if not r:
        return None
    return {
        "id": r["id"],
        "tenant_id": r["tenant_id"],
        "email": r["email"],
        "name": r["name"],
        "role": r["role"],
        "created_at": r["created_at"],
        "active": bool(r["active"]),
    }


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    email_n = email.strip().lower()
    with _LOCK:
        conn = _conn()
        try:
            r = conn.execute(
                """
                SELECT id, tenant_id, email, name, role, password_hash, active
                FROM users WHERE email = ? AND active = 1
                ORDER BY created_at ASC LIMIT 1
                """,
                (email_n,),
            ).fetchone()
        finally:
            conn.close()
    if not r:
        return None
    expected = str(r["password_hash"])
    provided = _hash_secret(password)
    if not hmac.compare_digest(expected, provided):
        return None
    return {
        "id": r["id"],
        "tenant_id": r["tenant_id"],
        "email": r["email"],
        "name": r["name"],
        "role": r["role"],
    }


def create_api_key(
    *,
    tenant_id: str,
    name: str,
    role: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    raw_key = f"abi_{secrets.token_urlsafe(24)}"
    key_id = uuid.uuid4().hex[:12]
    created = _now()
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(
                """
                INSERT INTO api_keys
                (id, tenant_id, user_id, name, key_prefix, key_hash, role, created_at, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    key_id,
                    tenant_id,
                    user_id,
                    name.strip() or "API key",
                    raw_key[:10],
                    _hash_secret(raw_key),
                    normalize_role(role),
                    created,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return {
        "id": key_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "name": name,
        "role": normalize_role(role),
        "api_key": raw_key,
        "key_prefix": raw_key[:10],
        "created_at": created,
    }


def resolve_api_key(raw_key: str) -> dict[str, Any] | None:
    if not raw_key:
        return None
    digest = _hash_secret(raw_key)
    with _LOCK:
        conn = _conn()
        try:
            r = conn.execute(
                """
                SELECT k.id, k.tenant_id, k.user_id, k.name, k.role, k.active,
                       t.active AS tenant_active, t.name AS tenant_name,
                       t.branding_json
                FROM api_keys k
                JOIN tenants t ON t.id = k.tenant_id
                WHERE k.key_hash = ?
                """,
                (digest,),
            ).fetchone()
            if not r or not r["active"] or not r["tenant_active"]:
                return None
            conn.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                (_now(), r["id"]),
            )
            conn.commit()
        finally:
            conn.close()
    return {
        "key_id": r["id"],
        "tenant_id": r["tenant_id"],
        "tenant_name": r["tenant_name"],
        "user_id": r["user_id"],
        "role": normalize_role(str(r["role"])),
        "name": r["name"],
        "branding": json.loads(r["branding_json"] or "{}"),
        "auth_mode": "tenant_key",
    }


def list_api_keys(tenant_id: str) -> list[dict[str, Any]]:
    with _LOCK:
        conn = _conn()
        try:
            rows = conn.execute(
                """
                SELECT id, tenant_id, user_id, name, key_prefix, role,
                       created_at, last_used_at, active
                FROM api_keys WHERE tenant_id = ?
                ORDER BY created_at DESC
                """,
                (tenant_id,),
            ).fetchall()
        finally:
            conn.close()
    return [
        {
            "id": r["id"],
            "tenant_id": r["tenant_id"],
            "user_id": r["user_id"],
            "name": r["name"],
            "key_prefix": r["key_prefix"],
            "role": r["role"],
            "created_at": r["created_at"],
            "last_used_at": r["last_used_at"],
            "active": bool(r["active"]),
        }
        for r in rows
    ]
