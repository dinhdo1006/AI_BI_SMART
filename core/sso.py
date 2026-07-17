"""
SSO — hỗ trợ OIDC (Google Workspace, Azure AD) và SAML 2.0.

Cấu hình qua biến môi trường:

  # OIDC chung (Google / Azure / Keycloak)
  SSO_PROVIDER=oidc              # oidc | saml | disabled (mặc định)
  SSO_OIDC_CLIENT_ID=...
  SSO_OIDC_CLIENT_SECRET=...
  SSO_OIDC_DISCOVERY_URL=...     # Google: https://accounts.google.com/.well-known/openid-configuration
                                  # Azure: https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration
  SSO_OIDC_REDIRECT_URI=http://yourdomain/api/v1/sso/callback
  SSO_OIDC_SCOPE=openid email profile

  # SAML 2.0 (Azure AD Enterprise App hoặc các IdP khác)
  SSO_PROVIDER=saml
  SSO_SAML_IDP_METADATA_URL=...  # URL metadata của IdP
  SSO_SAML_SP_ENTITY_ID=...
  SSO_SAML_SP_ACS_URL=http://yourdomain/api/v1/sso/saml/acs
  SSO_SAML_CERT_FILE=...         # PEM cert của SP (tuỳ chọn)
  SSO_SAML_KEY_FILE=...          # PEM key của SP (tuỳ chọn)

Luồng OIDC:
  1. GET /api/v1/sso/login        → redirect IdP
  2. GET /api/v1/sso/callback     → nhận code → exchange → upsert user → trả API key

Luồng SAML:
  1. GET /api/v1/sso/saml/login   → redirect IdP với AuthnRequest
  2. POST /api/v1/sso/saml/acs    → nhận SAMLResponse → upsert user → trả API key
"""

from __future__ import annotations

import os
import secrets
import urllib.parse
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from core.tenancy import (
    authenticate_user,
    create_api_key,
    create_user,
    ensure_default_tenant,
    get_tenant,
    is_multi_tenant_enabled,
    list_tenants,
)

router = APIRouter(prefix="/api/v1/sso", tags=["sso"])

_SSO_PROVIDER = os.getenv("SSO_PROVIDER", "disabled").strip().lower()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sso_enabled() -> bool:
    return _SSO_PROVIDER in ("oidc", "saml")


def _upsert_sso_user(
    email: str,
    name: str,
    tenant_id: str | None,
) -> dict[str, Any]:
    """
    Tìm hoặc tạo user SSO. Trả user dict.
    Nếu tenant_id=None → dùng default tenant.
    """
    if is_multi_tenant_enabled():
        ensure_default_tenant()

    # Resolve tenant
    if tenant_id:
        tenant = get_tenant(tenant_id)
    else:
        tenants = list_tenants()
        tenant = tenants[0] if tenants else None

    if not tenant:
        raise HTTPException(status_code=500, detail="Chưa có tenant nào được tạo")

    tid = str(tenant["id"])

    # Thử authenticate (user đã tồn tại — dùng dummy password sẽ fail)
    # Tạo mới nếu chưa có, bỏ qua nếu đã tồn tại
    try:
        create_user(
            tenant_id=tid,
            email=email,
            name=name or email,
            role="analyst",
            password=secrets.token_hex(32),  # random password — chỉ dùng SSO
        )
    except Exception:
        pass  # user đã tồn tại → bỏ qua

    return {"email": email, "name": name, "tenant_id": tid}


def _issue_api_key(email: str, tenant_id: str) -> str:
    """Tạo API key session cho SSO user."""
    result = create_api_key(
        tenant_id=tenant_id,
        name=f"sso:{email}",
        role="analyst",
    )
    return str(result.get("api_key") or "")


# ---------------------------------------------------------------------------
# OIDC
# ---------------------------------------------------------------------------

@router.get("/login")
def sso_login(request: Request) -> RedirectResponse:
    """Bắt đầu luồng OIDC — redirect đến IdP."""
    if _SSO_PROVIDER != "oidc":
        raise HTTPException(status_code=501, detail="SSO_PROVIDER không phải oidc")

    client_id = os.getenv("SSO_OIDC_CLIENT_ID", "")
    discovery_url = os.getenv("SSO_OIDC_DISCOVERY_URL", "")
    redirect_uri = os.getenv("SSO_OIDC_REDIRECT_URI", "")
    scope = os.getenv("SSO_OIDC_SCOPE", "openid email profile")

    if not client_id or not discovery_url or not redirect_uri:
        raise HTTPException(
            status_code=503,
            detail="SSO OIDC chưa cấu hình (SSO_OIDC_CLIENT_ID / SSO_OIDC_DISCOVERY_URL / SSO_OIDC_REDIRECT_URI)",
        )

    # Lấy authorization_endpoint từ discovery URL
    import urllib.request, json as _json
    try:
        with urllib.request.urlopen(discovery_url, timeout=5) as resp:
            meta = _json.loads(resp.read())
        auth_ep = meta["authorization_endpoint"]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Không lấy được OIDC metadata: {exc}") from exc

    state = secrets.token_urlsafe(16)
    # Lưu state vào session cookie (đơn giản — production dùng Redis/DB)
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
    })
    resp = RedirectResponse(url=f"{auth_ep}?{params}", status_code=302)
    resp.set_cookie("sso_state", state, httponly=True, samesite="lax", max_age=300)
    return resp


@router.get("/callback")
def sso_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    request: Request = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """
    OIDC callback — exchange code → token → user info → API key.
    Frontend nhận {api_key, email, tenant_id} rồi lưu localStorage.
    """
    if _SSO_PROVIDER != "oidc":
        raise HTTPException(status_code=501, detail="SSO_PROVIDER không phải oidc")
    if error:
        raise HTTPException(status_code=401, detail=f"IdP từ chối: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Thiếu authorization code")

    client_id = os.getenv("SSO_OIDC_CLIENT_ID", "")
    client_secret = os.getenv("SSO_OIDC_CLIENT_SECRET", "")
    redirect_uri = os.getenv("SSO_OIDC_REDIRECT_URI", "")
    discovery_url = os.getenv("SSO_OIDC_DISCOVERY_URL", "")

    import urllib.request, json as _json, urllib.error
    try:
        with urllib.request.urlopen(discovery_url, timeout=5) as r:
            meta = _json.loads(r.read())
        token_ep = meta["token_endpoint"]
        userinfo_ep = meta.get("userinfo_endpoint", "")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Exchange code → tokens
    token_data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(token_ep, data=token_data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            tokens = _json.loads(r.read())
    except urllib.error.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Lỗi lấy token: {exc}") from exc

    access_token = tokens.get("access_token", "")
    if not access_token:
        raise HTTPException(status_code=502, detail="Không có access_token")

    # Lấy thông tin user
    email = ""
    name = ""
    if userinfo_ep:
        try:
            req2 = urllib.request.Request(
                userinfo_ep,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            with urllib.request.urlopen(req2, timeout=10) as r:
                info = _json.loads(r.read())
            email = info.get("email", "")
            name = info.get("name", "") or info.get("given_name", "")
        except Exception:
            pass

    if not email:
        raise HTTPException(status_code=502, detail="Không lấy được email từ IdP")

    user = _upsert_sso_user(email, name, tenant_id=None)
    api_key = _issue_api_key(email, str(user["tenant_id"]))

    return {
        "ok": True,
        "email": email,
        "name": name,
        "tenant_id": user["tenant_id"],
        "api_key": api_key,
        "provider": "oidc",
    }


# ---------------------------------------------------------------------------
# SAML 2.0
# ---------------------------------------------------------------------------

@router.get("/saml/login")
def saml_login() -> Any:
    """Redirect đến IdP với SAML AuthnRequest."""
    if _SSO_PROVIDER != "saml":
        raise HTTPException(status_code=501, detail="SSO_PROVIDER không phải saml")

    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth  # type: ignore[import]
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="Thiếu python3-saml. Cài: pip install python3-saml",
        ) from exc

    saml_settings = _build_saml_settings()
    # Tạo mock request để khởi tạo Auth object
    auth = OneLogin_Saml2_Auth({"https": "on", "http_host": "localhost"}, saml_settings)
    sso_url = auth.login()
    return RedirectResponse(url=sso_url, status_code=302)


@router.post("/saml/acs")
async def saml_acs(request: Request) -> dict[str, Any]:
    """SAML ACS — nhận SAMLResponse từ IdP → upsert user → API key."""
    if _SSO_PROVIDER != "saml":
        raise HTTPException(status_code=501, detail="SSO_PROVIDER không phải saml")

    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth  # type: ignore[import]
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="Thiếu python3-saml. Cài: pip install python3-saml",
        ) from exc

    form = await request.form()
    saml_response = form.get("SAMLResponse", "")
    if not saml_response:
        raise HTTPException(status_code=400, detail="Thiếu SAMLResponse")

    saml_settings = _build_saml_settings()
    req = {
        "https": "on",
        "http_host": request.url.hostname or "localhost",
        "script_name": "/api/v1/sso/saml/acs",
        "get_data": {},
        "post_data": {"SAMLResponse": saml_response},
    }
    auth = OneLogin_Saml2_Auth(req, saml_settings)
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        raise HTTPException(status_code=401, detail=f"SAML lỗi: {errors}")

    attributes = auth.get_attributes()
    email = (
        attributes.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress", [""])[0]
        or attributes.get("email", [""])[0]
        or auth.get_nameid()
        or ""
    )
    name = (
        attributes.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name", [""])[0]
        or attributes.get("displayName", [""])[0]
        or ""
    )

    if not email:
        raise HTTPException(status_code=502, detail="Không lấy được email từ SAML assertion")

    user = _upsert_sso_user(email, name, tenant_id=None)
    api_key = _issue_api_key(email, str(user["tenant_id"]))

    return {
        "ok": True,
        "email": email,
        "name": name,
        "tenant_id": user["tenant_id"],
        "api_key": api_key,
        "provider": "saml",
    }


@router.get("/metadata")
def saml_metadata() -> Any:
    """Trả SAML SP metadata XML cho IdP đăng ký."""
    if _SSO_PROVIDER != "saml":
        raise HTTPException(status_code=404, detail="SAML chưa bật")
    try:
        from onelogin.saml2.settings import OneLogin_Saml2_Settings  # type: ignore[import]
        from fastapi.responses import Response as FResponse
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Thiếu python3-saml") from exc

    settings = OneLogin_Saml2_Settings(_build_saml_settings())
    meta, errors = settings.get_sp_metadata(), settings.validate_metadata(settings.get_sp_metadata())
    if errors:
        raise HTTPException(status_code=500, detail=str(errors))
    return FResponse(content=meta, media_type="application/xml")


def _build_saml_settings() -> dict[str, Any]:
    idp_meta_url = os.getenv("SSO_SAML_IDP_METADATA_URL", "")
    sp_entity = os.getenv("SSO_SAML_SP_ENTITY_ID", "ai-bi-smart")
    sp_acs = os.getenv("SSO_SAML_SP_ACS_URL", "http://localhost:2004/api/v1/sso/saml/acs")

    # IdP settings (có thể đọc từ metadata URL trong production)
    idp_settings: dict[str, Any] = {
        "entityId": idp_meta_url or "https://idp.example.com/",
        "singleSignOnService": {
            "url": idp_meta_url or "https://idp.example.com/sso",
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        },
        "x509cert": os.getenv("SSO_SAML_IDP_CERT", ""),
    }

    sp_settings: dict[str, Any] = {
        "entityId": sp_entity,
        "assertionConsumerService": {
            "url": sp_acs,
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
        },
    }

    cert_file = os.getenv("SSO_SAML_CERT_FILE", "")
    key_file = os.getenv("SSO_SAML_KEY_FILE", "")
    if cert_file:
        try:
            sp_settings["x509cert"] = open(cert_file).read()
        except OSError:
            pass
    if key_file:
        try:
            sp_settings["privateKey"] = open(key_file).read()
        except OSError:
            pass

    return {
        "strict": True,
        "debug": False,
        "sp": sp_settings,
        "idp": idp_settings,
    }


@router.get("/status")
def sso_status() -> dict[str, Any]:
    """Kiểm tra SSO đã cấu hình chưa."""
    return {
        "provider": _SSO_PROVIDER,
        "enabled": _sso_enabled(),
        "oidc_configured": bool(
            os.getenv("SSO_OIDC_CLIENT_ID") and os.getenv("SSO_OIDC_DISCOVERY_URL")
        ) if _SSO_PROVIDER == "oidc" else False,
        "saml_configured": bool(os.getenv("SSO_SAML_IDP_METADATA_URL")) if _SSO_PROVIDER == "saml" else False,
    }
