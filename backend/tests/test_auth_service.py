import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main
from app.services import auth_service


def test_x_oauth_callback_reuses_completed_redirect(monkeypatch):
    redirect_url = "https://shosetsu-toukou-site.org/oauth/callback?token=test&username=alice"

    monkeypatch.setattr(main, "X_OAUTH_CONSUMER_KEY", "key")
    monkeypatch.setattr(main, "X_OAUTH_CONSUMER_SECRET", "secret")
    monkeypatch.setattr(main, "_is_android_app_oauth_start", lambda request: False)
    monkeypatch.setattr(main, "_oauth_redirect_uri", lambda provider, request=None: f"https://api.example.com/{provider}/callback")
    monkeypatch.setattr(main, "_pop_oauth1_request_token", lambda oauth_token: None)
    monkeypatch.setattr(main, "_peek_oauth1_completed_redirect", lambda oauth_token: redirect_url)

    response = asyncio.run(
        auth_service.oauth_callback_service(
            provider="x",
            oauth_token="request-token",
            oauth_verifier="verifier",
            request=SimpleNamespace(),
            db=SimpleNamespace(),
        )
    )

    assert response.status_code == 307
    assert response.headers["location"] == redirect_url


def test_completed_redirect_store_expires(monkeypatch):
    main.OAUTH1_COMPLETED_REDIRECTS.clear()
    now = {"value": 100.0}
    monkeypatch.setattr(main.time, "time", lambda: now["value"])

    main._store_oauth1_completed_redirect("token-1", "https://example.com/oauth/callback?token=abc")
    assert main._peek_oauth1_completed_redirect("token-1") == "https://example.com/oauth/callback?token=abc"

    now["value"] += main.OAUTH1_REQUEST_TOKEN_TTL_SECONDS + 1
    assert main._peek_oauth1_completed_redirect("token-1") is None
