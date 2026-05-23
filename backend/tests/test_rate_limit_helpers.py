import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main
from app import rate_limit_helpers


def test_rate_limit_helpers_are_imported_into_main():
    assert main._enforce_admin_login_rate_limit.__module__ == "app.rate_limit_helpers"
    assert main._enforce_ai_chat_rate_limit.__module__ == "app.rate_limit_helpers"
    assert main._public_contact_remote_ip.__module__ == "app.rate_limit_helpers"


def test_ai_chat_rate_limit_blocks_on_second_guest_request(monkeypatch):
    monkeypatch.setattr(rate_limit_helpers, "get_redis_client", lambda: None)
    monkeypatch.setattr(rate_limit_helpers.time, "time", lambda: 100.0)

    rate_limit_helpers._enforce_ai_chat_rate_limit(
        namespace="test_guest_limit",
        remote_ip="127.0.0.1",
        guest_id="guest-1",
        user=None,
        window_sec=60,
        user_max_requests=1,
        guest_max_requests=1,
    )

    with pytest.raises(HTTPException) as exc_info:
        rate_limit_helpers._enforce_ai_chat_rate_limit(
            namespace="test_guest_limit",
            remote_ip="127.0.0.1",
            guest_id="guest-1",
            user=None,
            window_sec=60,
            user_max_requests=1,
            guest_max_requests=1,
        )

    assert exc_info.value.status_code == 429
