import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main
from app import google_indexing_helpers
from app import public_indexing_helpers


def test_public_indexing_helpers_are_imported_into_main():
    assert main._enqueue_indexnow_urls.__module__ == "app.public_indexing_helpers"
    assert main._sitemap_urlset_xml.__module__ == "app.public_indexing_helpers"
    assert main.build_public_page_urls.__module__ == "app.public_indexing_helpers"


def test_google_indexing_helpers_are_imported_into_main():
    assert main._build_google_indexing_access_token.__module__ == "app.google_indexing_helpers"
    assert main._inspect_google_indexed_status.__module__ == "app.google_indexing_helpers"
    assert main._should_retry_google_indexing_publish.__module__ == "app.google_indexing_helpers"


def test_google_indexing_daily_quota_error_distinguishes_burst_limits():
    assert google_indexing_helpers._is_google_indexing_daily_quota_error(429, "Exceeded requests per day") is True
    assert google_indexing_helpers._is_google_indexing_daily_quota_error(429, "Too many requests per minute") is False


def test_dedupe_urls_keep_order_preserves_first_occurrence():
    out = public_indexing_helpers._dedupe_urls_keep_order(
        [" https://a ", "https://b", "https://a", "", "https://b", "https://c"]
    )

    assert out == ["https://a", "https://b", "https://c"]


def test_sitemap_urlset_xml_renders_lastmod():
    xml = public_indexing_helpers._sitemap_urlset_xml(
        [("https://example.com/a", datetime(2025, 1, 2)), ("https://example.com/b", None)]
    )

    assert "<loc>https://example.com/a</loc>" in xml
    assert "<lastmod>2025-01-02</lastmod>" in xml
    assert "<loc>https://example.com/b</loc>" in xml


def test_is_novel_indexable_for_search_checks_public_status_and_age_limit():
    class _Novel:
        is_public = True
        status = "public"
        age_limit = "all"

    assert public_indexing_helpers._is_novel_indexable_for_search(_Novel()) is True
    _Novel.age_limit = "r18"
    assert public_indexing_helpers._is_novel_indexable_for_search(_Novel()) is False
