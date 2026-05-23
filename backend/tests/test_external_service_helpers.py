import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import external_service_helpers
from app import main


def test_external_service_helpers_are_imported_into_main():
    assert main.verify_recaptcha_token.__module__ == "app.external_service_helpers"
    assert main._split_character_terms.__module__ == "app.external_service_helpers"
    assert main._split_character_fullname_terms.__module__ == "app.external_service_helpers"


def test_verify_recaptcha_token_returns_true_when_disabled(monkeypatch):
    monkeypatch.setattr(external_service_helpers, "RECAPTCHA_ENABLED", False)
    monkeypatch.setattr(external_service_helpers, "RECAPTCHA_ENTERPRISE_ENABLED", False)

    assert external_service_helpers.verify_recaptcha_token("") is True


def test_split_character_fullname_terms_expands_pairs():
    out = external_service_helpers._split_character_fullname_terms("五条 悟 夏油 傑")

    assert out[0] == "五条 悟 夏油 傑"
    assert "五条 悟" in out
    assert "五条悟" in out
    assert "夏油 傑" in out
    assert "夏油傑" in out
