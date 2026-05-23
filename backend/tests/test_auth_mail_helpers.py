import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import auth_mail_helpers
from app import main


def test_auth_mail_helpers_are_imported_into_main():
    assert main.send_password_reset_email.__module__ == "app.auth_mail_helpers"
    assert main.send_register_email_verification_code.__module__ == "app.auth_mail_helpers"
    assert main.send_2fa_email.__module__ == "app.auth_mail_helpers"


def test_register_email_verification_code_raises_without_smtp(monkeypatch):
    monkeypatch.setattr(auth_mail_helpers, "SMTP_HOST", None)
    monkeypatch.setattr(auth_mail_helpers, "SMTP_USER", None)
    monkeypatch.setattr(auth_mail_helpers, "SMTP_PASS", None)

    try:
        auth_mail_helpers.send_register_email_verification_code("user@example.com", "123456", 10)
    except RuntimeError as exc:
        assert "SMTP設定" in str(exc)
    else:
        raise AssertionError("RuntimeError was not raised")
