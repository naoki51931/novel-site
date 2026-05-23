import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main
from app.services.ai_misc_service import (
    auto_fill_ai_novel_inputs_post_service,
    auto_fill_ai_novel_inputs_service,
    get_ai_novel_remaining_service,
)


class _AutoFillReq:
    query = "hero"
    characters = "John Doe"


def test_ai_novel_misc_routes_are_mounted_via_router():
    route = next(
        r
        for r in main.app.routes
        if getattr(r, "path", None) == "/api/ai/novels/remaining" and "GET" in getattr(r, "methods", set())
    )
    assert route.endpoint.__module__ == "app.routers.ai_novel_misc"


def test_get_ai_novel_remaining_service(monkeypatch):
    monkeypatch.setattr(main, "get_or_set_ai_guest_id", lambda request, response: "guest-1")
    monkeypatch.setattr(main, "get_guest_ai_usage", lambda db, guest_id: SimpleNamespace(generate_count=2))
    monkeypatch.setattr(main, "AI_GUEST_FREE_MAX", 5)
    monkeypatch.setattr(main, "get_optional_current_user", lambda request, db: SimpleNamespace(id=1))
    monkeypatch.setattr(main, "is_effective_premium_user", lambda user: True)
    monkeypatch.setattr(main, "_ai_novel_remaining_for_user", lambda db, user: (8, 5, 3))
    monkeypatch.setattr(main, "AI_NOVEL_ADDON_UNIT_GENERATIONS", 10)
    monkeypatch.setattr(main, "AI_NOVEL_ADDON_PRICE_YEN", 200)

    out = get_ai_novel_remaining_service(
        request=SimpleNamespace(headers={}),
        response=SimpleNamespace(),
        db=SimpleNamespace(),
    )

    assert out == {
        "guest_remaining": 3,
        "user_remaining": 8,
        "user_base_remaining": 5,
        "user_paid_remaining": 3,
        "addon_unit_generations": 10,
        "addon_unit_price_yen": 200,
    }


@pytest.mark.anyio
async def test_auto_fill_ai_novel_inputs_services(monkeypatch):
    class _Resp:
        status_code = 200
        text = ""
        content = b"x"

        def json(self):
            return {
                "items": [
                    {"title": "Hero Story", "link": "https://preferred.example/1", "snippet": "snip1"},
                    {"title": "Another Story", "link": "https://other.example/2", "snippet": "snip2"},
                ]
            }

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None):
            return _Resp()

    monkeypatch.setattr(main, "GOOGLE_CSE_API_KEY", "key")
    monkeypatch.setattr(main, "GOOGLE_CSE_CX", "cx")
    monkeypatch.setattr(main, "httpx", SimpleNamespace(AsyncClient=lambda timeout=10.0: _Client()))
    monkeypatch.setattr(main, "_split_search_terms", lambda q: [q, q])
    monkeypatch.setattr(main, "_split_character_fullname_terms", lambda c: ["John Doe", "Jane Roe"])
    monkeypatch.setattr(main, "_split_character_terms", lambda c: ["John", "Jane"])
    monkeypatch.setattr(main, "_is_preferred_cse_host", lambda link: "preferred" in str(link))
    monkeypatch.setattr(main, "_build_auto_fill_snippets", lambda picked: ("genre", "chars"))
    from app import ai_source_helpers

    monkeypatch.setattr(ai_source_helpers, "_extract_title_candidates_from_source_titles", lambda **kwargs: ["Hero Story"])

    out1 = await auto_fill_ai_novel_inputs_service(query="hero", characters="John Doe")
    out2 = await auto_fill_ai_novel_inputs_post_service(payload=_AutoFillReq())

    assert out1["query"] == "hero"
    assert out1["characters_query"] == "John Doe"
    assert out1["genre_append"] == "genre"
    assert out1["characters_append"] == "chars"
    assert out1["inferred_source_title"] == "Hero Story"
    assert out1["source_title_candidates"] == ["Hero Story"]
    assert out1["sources"][0]["title"] == "Hero Story"
    assert out2["query"] == "hero"
