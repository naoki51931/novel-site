import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.responses import Response

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import admin_auth_helpers
from app import main


def test_admin_auth_helpers_are_imported_into_main():
    assert main.create_admin_token.__module__ == "app.admin_auth_helpers"
    assert main.verify_admin_token.__module__ == "app.admin_auth_helpers"
    assert main.require_admin.__module__ == "app.admin_auth_helpers"


def test_admin_token_roundtrip(monkeypatch):
    monkeypatch.setattr(main, "ADMIN_JWT_SECRET", "test-secret")
    monkeypatch.setattr(main, "ALGORITHM", "HS256")
    monkeypatch.setattr(main, "ADMIN_JWT_EXPIRES_MINUTES", 30)

    token = admin_auth_helpers.create_admin_token("alice")
    payload = admin_auth_helpers.verify_admin_token(token)

    assert payload["sub"] == "alice"
    assert payload["role"] == "admin"


def test_require_admin_rejects_missing_csrf(monkeypatch):
    monkeypatch.setattr(main, "ADMIN_JWT_SECRET", "test-secret")
    monkeypatch.setattr(main, "ALGORITHM", "HS256")
    monkeypatch.setattr(main, "ADMIN_JWT_EXPIRES_MINUTES", 30)
    monkeypatch.setattr(main, "ADMIN_CSRF_COOKIE_NAME", "admin_csrf")
    monkeypatch.setattr(main, "ADMIN_API_KEY", "")

    token = admin_auth_helpers.create_admin_token("alice")
    request = SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/api/admin/test"),
        cookies={"admin_token": token, "admin_csrf": "cookie-token"},
        headers={},
    )

    with pytest.raises(HTTPException) as exc_info:
        admin_auth_helpers.require_admin(request)

    assert exc_info.value.status_code == 403


def test_set_admin_cookie_sets_and_clears(monkeypatch):
    monkeypatch.setattr(main, "ADMIN_CSRF_COOKIE_NAME", "admin_csrf")
    monkeypatch.setattr(main, "ADMIN_COOKIE_SECURE", True)
    monkeypatch.setattr(main, "ADMIN_JWT_EXPIRES_MINUTES", 30)
    monkeypatch.setattr(main.secrets, "token_urlsafe", lambda n: "csrf-token")

    response = Response()
    admin_auth_helpers._set_admin_cookie(response, "admin-token")
    cookies = response.headers.getlist("set-cookie")
    assert any("admin_token=admin-token" in c for c in cookies)
    assert any("admin_csrf=csrf-token" in c for c in cookies)

    response = Response()
    admin_auth_helpers._set_admin_cookie(response, None)
    cookies = response.headers.getlist("set-cookie")
    assert any("admin_token=\"\"" in c for c in cookies)
    assert any("admin_csrf=\"\"" in c for c in cookies)
