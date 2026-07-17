"""RBAC — vai trò & quyền cho B2B."""

from __future__ import annotations

from typing import Literal

Role = Literal["admin", "analyst", "viewer"]

ROLES: tuple[Role, ...] = ("admin", "analyst", "viewer")

# Quyền → vai trò tối thiểu được phép
PERMISSIONS: dict[str, frozenset[Role]] = {
    "chat": frozenset({"admin", "analyst", "viewer"}),
    "explore": frozenset({"admin", "analyst", "viewer"}),
    "export": frozenset({"admin", "analyst", "viewer"}),
    "dashboard.read": frozenset({"admin", "analyst", "viewer"}),
    "dashboard.write": frozenset({"admin", "analyst"}),
    "article.write": frozenset({"admin", "analyst"}),
    "article.revise": frozenset({"admin", "analyst"}),
    "upload": frozenset({"admin", "analyst"}),
    "alerts.manage": frozenset({"admin", "analyst"}),
    "feedback": frozenset({"admin", "analyst", "viewer"}),
    "admin.tenants": frozenset({"admin"}),
    "admin.users": frozenset({"admin"}),
    "admin.keys": frozenset({"admin"}),
    "admin.branding": frozenset({"admin"}),
    "admin.jobs": frozenset({"admin"}),
}


def normalize_role(role: str | None) -> Role:
    r = (role or "viewer").strip().lower()
    if r in ROLES:
        return r  # type: ignore[return-value]
    return "viewer"


def has_permission(role: str | None, permission: str) -> bool:
    allowed = PERMISSIONS.get(permission)
    if allowed is None:
        return False
    return normalize_role(role) in allowed
