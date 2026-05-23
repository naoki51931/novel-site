import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main
from app import notification_helpers


def test_notification_helpers_are_imported_into_main():
    assert main.create_notification.__module__ == "app.notification_helpers"
    assert main.send_notification_email.__module__ == "app.notification_helpers"
    assert main.notify_recommended_users_new_novel.__module__ == "app.notification_helpers"


def test_notification_target_url_uses_frontend_origin(monkeypatch):
    monkeypatch.setattr(main, "FRONTEND_ORIGIN", "https://example.com")

    assert notification_helpers._notification_target_url(None) == "https://example.com/notifications"
    assert notification_helpers._notification_target_url("/episodes/1") == "https://example.com/episodes/1"
    assert notification_helpers._notification_target_url("https://other.example/path") == "https://other.example/path"


def test_unknown_email_address_error_detects_smtp_rejection():
    err = notification_helpers.smtplib.SMTPRecipientsRefused(
        {"a@example.com": (550, b"User unknown")}
    )

    assert notification_helpers._is_unknown_email_address_error(err) is True
