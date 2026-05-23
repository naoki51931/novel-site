from datetime import datetime, timedelta

import jwt
from fastapi import HTTPException, Request
from fastapi.responses import Response


def _legacy():
    from . import main as legacy

    return legacy


def create_admin_token(username: str) -> str:
    legacy = _legacy()
    if not legacy.ADMIN_JWT_SECRET:
        raise HTTPException(500, "ADMIN_JWT_SECRET 未設定")
    expire = datetime.utcnow() + timedelta(minutes=legacy.ADMIN_JWT_EXPIRES_MINUTES)
    payload = {"role": "admin", "sub": username, "exp": expire}
    return jwt.encode(payload, legacy.ADMIN_JWT_SECRET, algorithm=legacy.ALGORITHM)


def verify_admin_token(token: str) -> dict:
    legacy = _legacy()
    if not legacy.ADMIN_JWT_SECRET:
        raise HTTPException(500, "ADMIN_JWT_SECRET 未設定")
    try:
        payload = jwt.decode(token, legacy.ADMIN_JWT_SECRET, algorithms=[legacy.ALGORITHM])
    except Exception:
        raise HTTPException(401, "管理者トークンが不正です")
    if payload.get("role") != "admin":
        raise HTTPException(403, "管理者権限が必要です")
    return payload


def _admin_request_needs_csrf(request: Request) -> bool:
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return False
    path = (request.url.path or "").strip()
    if not path.startswith("/api/admin/"):
        return False
    if path == "/api/admin/auth/login":
        return False
    return True


def _ensure_admin_csrf(request: Request) -> None:
    legacy = _legacy()
    csrf_cookie = (request.cookies.get(legacy.ADMIN_CSRF_COOKIE_NAME) or "").strip()
    csrf_header = (request.headers.get("X-CSRF-Token") or "").strip()
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(403, "CSRF トークンが無効です")


def require_admin(request: Request) -> None:
    legacy = _legacy()
    admin_cookie = request.cookies.get("admin_token")
    if admin_cookie:
        verify_admin_token(admin_cookie)
        if _admin_request_needs_csrf(request):
            _ensure_admin_csrf(request)
        return
    if legacy.ADMIN_API_KEY:
        legacy_token = request.headers.get("X-Admin-Token")
        if legacy_token == legacy.ADMIN_API_KEY:
            return
    raise HTTPException(401, "管理者権限が必要です")


def get_admin_username(request: Request) -> str | None:
    admin_cookie = request.cookies.get("admin_token")
    if not admin_cookie:
        return None
    try:
        payload = verify_admin_token(admin_cookie)
    except Exception:
        return None
    return payload.get("sub")


def _issue_admin_csrf_cookie(response: Response) -> None:
    legacy = _legacy()
    csrf_token = legacy.secrets.token_urlsafe(32)
    response.set_cookie(
        key=legacy.ADMIN_CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=legacy.ADMIN_COOKIE_SECURE,
        samesite="lax",
        max_age=legacy.ADMIN_JWT_EXPIRES_MINUTES * 60,
        path="/",
    )


def _set_admin_cookie(response: Response, token: str | None) -> None:
    legacy = _legacy()
    if token:
        response.set_cookie(
            key="admin_token",
            value=token,
            httponly=True,
            secure=legacy.ADMIN_COOKIE_SECURE,
            samesite="lax",
            max_age=legacy.ADMIN_JWT_EXPIRES_MINUTES * 60,
            path="/",
        )
        _issue_admin_csrf_cookie(response)
    else:
        response.delete_cookie(key="admin_token", path="/")
        response.delete_cookie(key=legacy.ADMIN_CSRF_COOKIE_NAME, path="/")
