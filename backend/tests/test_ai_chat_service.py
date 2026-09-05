import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import ai_source_helpers, main, notification_helpers, public_chat_helpers
from app.ai_chat_runtime_helpers import _ai_chat_provider_candidates
from app.services.ai_chat_service import (
    ai_chat_generate_image_service,
    ai_chat_service,
    ai_chat_auto_continue_service,
    ai_chat_character_anime_title_candidates_service,
    ai_chat_next_user_lines_service,
    augment_ai_chat_character_service,
    create_ai_chat_character_service,
    delete_ai_chat_message_image_service,
    delete_ai_chat_messages_from_point_service,
    delete_ai_chat_character_service,
    favorite_public_ai_chat_character_service,
    get_ai_chat_engagement_summary_service,
    get_ai_chat_access_status_service,
    get_ai_chat_latest_prompt_preview_service,
    get_public_ai_chat_character_detail_service,
    import_ai_chat_messages_service,
    like_public_ai_chat_character_service,
    list_ai_chat_characters_service,
    list_ai_chat_messages_service,
    publish_ai_chat_character_service,
    unfavorite_public_ai_chat_character_service,
    unlike_public_ai_chat_character_service,
    update_ai_chat_character_service,
    upload_ai_chat_character_image_service,
    upload_ai_chat_message_images_service,
)


def test_ai_chat_access_route_is_mounted_via_router():
    route = next(
        r
        for r in main.app.routes
        if getattr(r, "path", None) == "/api/ai/chat/access" and "GET" in getattr(r, "methods", set())
    )
    assert route.endpoint.__module__ == "app.routers.ai_chat"


def test_ai_chat_message_import_route_is_mounted_via_router():
    route = next(
        r
        for r in main.app.routes
        if getattr(r, "path", None) == "/api/ai/chat/characters/{character_id}/messages/import"
        and "POST" in getattr(r, "methods", set())
    )
    assert route.endpoint.__module__ == "app.routers.ai_chat"


def test_ai_chat_route_is_mounted_via_router():
    route = next(
        r
        for r in main.app.routes
        if getattr(r, "path", None) == "/api/ai/chat" and "POST" in getattr(r, "methods", set())
    )
    assert route.endpoint.__module__ == "app.routers.ai_chat"


def test_ai_chat_generate_image_route_is_mounted_via_router():
    route = next(
        r
        for r in main.app.routes
        if getattr(r, "path", None) == "/api/ai/chat/generate_image" and "POST" in getattr(r, "methods", set())
    )
    assert route.endpoint.__module__ == "app.routers.ai_chat"


def test_ai_chat_explicit_remote_model_can_fallback_to_local_when_local_is_default(monkeypatch):
    monkeypatch.setenv("AI_CHAT_DEFAULT_PROVIDER", "local")

    candidates = _ai_chat_provider_candidates(
        "openrouter",
        "google/gemini-3-flash-preview",
        resolve_ai_chat_provider=lambda provider, model: provider or "openrouter",
    )

    assert candidates == ["openrouter", "local"]


def test_ai_chat_explicit_remote_model_does_not_fallback_to_local_without_local_default(monkeypatch):
    monkeypatch.delenv("AI_CHAT_DEFAULT_PROVIDER", raising=False)

    candidates = _ai_chat_provider_candidates(
        "openrouter",
        "google/gemini-3-flash-preview",
        resolve_ai_chat_provider=lambda provider, model: provider or "openrouter",
    )

    assert candidates == ["openrouter"]


class _DummyReq:
    character_id = None
    character_name = "Mina"
    personality = "calm"
    history = []
    input_hint = "next idea"
    suggestions_count = 3
    language_style = "normal"
    r18 = False
    model = None
    provider = None


class _AutoContinueReq:
    character_id = None
    character_name = "Mina"
    personality = "calm"
    history = [
        SimpleNamespace(role="user", content="hello"),
        SimpleNamespace(role="assistant", content="hi there"),
    ]
    long_reply = True
    short_reply = False
    r18 = False
    language_style = "normal"
    model = None
    provider = None


class _AIChatReq:
    message = "hello"
    character_id = None
    character_name = "Mina"
    personality = "calm"
    mode = "say"
    long_reply = False
    short_reply = False
    r18 = False
    language_style = "normal"
    history = []
    auto_dialogue = False
    model = None
    provider = None


class _AIChatImageReq:
    prompt = "draw a sunset"
    character_id = None
    negative_prompt = ""
    model_id = ""
    width = 576
    height = 1024
    steps = 40
    guidance_scale = 6.5
    seed = None


class _AugmentReq:
    character_name = "Mina"
    personality = "kind"
    anime_title = "Sky Story"
    model = None
    provider = None


class _AnimeTitleReq:
    character_name = "Mina"
    limit = 3
    model = None
    provider = None


class _CharacterCreateReq:
    name = "Mina"
    personality = "kind"
    speech_gender = "female"


class _CharacterUpdateReq:
    name = "Mina Updated"
    personality = "bold"
    speech_gender = "male"


class _CharacterPublishReq:
    is_public = True


class _MessageImportReq:
    replace_existing = True
    messages = [
        SimpleNamespace(role="user", mode="say", content="hello", is_auto_dialogue=False),
        SimpleNamespace(role="assistant", mode="do", content="reply", is_auto_dialogue=True),
    ]


@pytest.mark.anyio
async def test_ai_chat_next_user_lines_service_falls_back_and_deduplicates(monkeypatch):
    viewer = SimpleNamespace(id=1)
    recorded = {}

    async def _call_ai_chat_json_with_fallback(*args, **kwargs):
        return {"suggestions": ["  line1  ", "line1", "", "line2"]}, 12, "model-x"

    monkeypatch.setattr(main, "get_optional_current_user", lambda request, db: viewer)
    monkeypatch.setattr(main, "_ensure_ai_chat_access", lambda viewer, db: None)
    monkeypatch.setattr(main, "_enforce_ai_chat_rate_limit", lambda **kwargs: None)
    monkeypatch.setattr(main, "_public_contact_remote_ip", lambda request: "127.0.0.1")
    monkeypatch.setattr(main, "_build_ai_chat_history_text", lambda history, character_name: "")
    monkeypatch.setattr(main, "build_summary_text", lambda history, recent_limit=20, max_chars=1200: "")
    monkeypatch.setattr(main, "AI_CHAT_MEMORY_ENABLED", False)
    monkeypatch.setattr(main, "_build_language_style_rules", lambda style: "style")
    monkeypatch.setattr(main, "_build_ai_chat_next_line_suggest_prompt", lambda **kwargs: "prompt")
    monkeypatch.setattr(main, "_build_ai_chat_content_safety_rules", lambda r18=False: "")
    monkeypatch.setattr(main, "_call_ai_chat_json_with_fallback", _call_ai_chat_json_with_fallback)
    monkeypatch.setattr(main, "_normalize_next_line_suggestion", lambda text: text.strip())
    monkeypatch.setattr(
        main,
        "_fallback_next_line_suggestions",
        lambda input_hint, suggestions_count: ["line2", "line3", "line4"],
    )
    monkeypatch.setattr(
        main,
        "_record_ai_chat_tokens",
        lambda db, viewer, guest_usage, tokens: recorded.update({"tokens": tokens, "viewer_id": viewer.id}),
    )

    out = await ai_chat_next_user_lines_service(
        req=_DummyReq(),
        request=SimpleNamespace(headers={}),
        response=SimpleNamespace(),
        db=SimpleNamespace(),
    )

    assert out.character_name == "Mina"
    assert out.suggestions == ["line1", "line2", "line3"]
    assert out.used_tokens == 12
    assert out.model == "model-x"
    assert recorded == {"tokens": 12, "viewer_id": 1}


@pytest.mark.anyio
async def test_ai_chat_auto_continue_service_returns_regenerated_reply(monkeypatch):
    viewer = SimpleNamespace(id=1)
    recorded = {}

    async def _call_ai_chat_json_with_fallback(*args, **kwargs):
        return {"say": "base reply", "do": "action"}, 7, "model-y"

    async def _regenerate_auto_dialogue_if_needed(**kwargs):
        return "expanded reply"

    monkeypatch.setattr(main, "get_optional_current_user", lambda request, db: viewer)
    monkeypatch.setattr(main, "_ensure_ai_chat_access", lambda viewer, db: None)
    monkeypatch.setattr(main, "_enforce_ai_chat_rate_limit", lambda **kwargs: None)
    monkeypatch.setattr(main, "_public_contact_remote_ip", lambda request: "127.0.0.1")
    monkeypatch.setattr(main, "AI_CHAT_MEMORY_ENABLED", False)
    monkeypatch.setattr(main, "_normalize_language_style", lambda style: "normal")
    monkeypatch.setattr(main, "_build_language_style_rules", lambda style: "style")
    monkeypatch.setattr(main, "_build_ai_chat_history_text", lambda history, character_name: "history")
    monkeypatch.setattr(main, "build_summary_text", lambda history, recent_limit=20, max_chars=1200: "summary")
    monkeypatch.setattr(main, "_build_auto_dialogue_prompt", lambda **kwargs: "prompt")
    monkeypatch.setattr(main, "_build_ai_chat_content_safety_rules", lambda r18=False: "")
    monkeypatch.setattr(main, "_call_ai_chat_json_with_fallback", _call_ai_chat_json_with_fallback)
    monkeypatch.setattr(main, "_regenerate_auto_dialogue_if_needed", _regenerate_auto_dialogue_if_needed)
    monkeypatch.setattr(
        main,
        "_record_ai_chat_tokens",
        lambda db, viewer, guest_usage, tokens: recorded.update({"tokens": tokens, "viewer_id": viewer.id}),
    )

    out = await ai_chat_auto_continue_service(
        req=_AutoContinueReq(),
        request=SimpleNamespace(headers={}),
        response=SimpleNamespace(),
        db=SimpleNamespace(),
    )

    assert out.reply == "expanded reply"
    assert out.say == "expanded reply"
    assert out.do == "action"
    assert out.mode == "say"
    assert out.used_tokens == 7
    assert out.model == "model-y"
    assert recorded == {"tokens": 7, "viewer_id": 1}


@pytest.mark.anyio
async def test_ai_chat_service_returns_reply_and_records_tokens(monkeypatch):
    viewer = SimpleNamespace(id=1)
    recorded = {}

    async def _call_ai_chat_json_with_fallback(*args, **kwargs):
        return {"say": "hello back", "do": "wave"}, 9, "model-z"

    monkeypatch.setattr(main, "get_optional_current_user", lambda request, db: viewer)
    monkeypatch.setattr(main, "_ensure_ai_chat_access", lambda viewer, db: None)
    monkeypatch.setattr(main, "_enforce_ai_chat_rate_limit", lambda **kwargs: None)
    monkeypatch.setattr(main, "_public_contact_remote_ip", lambda request: "127.0.0.1")
    monkeypatch.setattr(main, "_normalize_language_style", lambda style: "normal")
    monkeypatch.setattr(main, "_build_language_style_rules", lambda style: "style")
    monkeypatch.setattr(main, "_build_ai_chat_history_text", lambda history, character_name: "history")
    monkeypatch.setattr(main, "build_summary_text", lambda history, recent_limit=20, max_chars=1200: "summary")
    monkeypatch.setattr(main, "AI_CHAT_MEMORY_ENABLED", False)
    monkeypatch.setattr(main, "_build_ai_chat_branching_instruction", lambda history, message: "branch")
    monkeypatch.setattr(main, "_build_ai_chat_variation_instruction", lambda mode, history: "variation")
    monkeypatch.setattr(main, "_build_ai_chat_engagement_learning_instruction", lambda *args, **kwargs: "engage")
    monkeypatch.setattr(main, "_build_ai_chat_prompt", lambda **kwargs: "prompt")
    monkeypatch.setattr(main, "_build_ai_chat_system_instructions", lambda **kwargs: "system")
    monkeypatch.setattr(main, "_call_ai_chat_json_with_fallback", _call_ai_chat_json_with_fallback)
    monkeypatch.setattr(
        main,
        "_record_ai_chat_tokens",
        lambda db, viewer, guest_usage, tokens: recorded.update({"tokens": tokens, "viewer_id": viewer.id}),
    )

    out = await ai_chat_service(
        req=_AIChatReq(),
        request=SimpleNamespace(headers={}),
        response=SimpleNamespace(),
        db=SimpleNamespace(),
    )

    assert out.reply == "hello back"
    assert out.say == "hello back"
    assert out.do == "wave"
    assert out.mode == "say"
    assert out.used_tokens == 9
    assert out.model == "model-z"
    assert recorded == {"tokens": 9, "viewer_id": 1}


@pytest.mark.anyio
async def test_ai_chat_generate_image_service_requires_prompt(monkeypatch):
    viewer = SimpleNamespace(id=1)

    monkeypatch.setattr(main, "get_optional_current_user", lambda request, db: viewer)
    monkeypatch.setattr(main, "_ensure_ai_chat_access", lambda viewer, db: None)
    monkeypatch.setattr(main, "_enforce_ai_chat_rate_limit", lambda **kwargs: None)
    monkeypatch.setattr(main, "_public_contact_remote_ip", lambda request: "127.0.0.1")
    monkeypatch.setattr(main, "AI_CHAT_IMAGE_API_BASE_URL", "https://example.invalid")

    bad_req = _AIChatImageReq()
    bad_req.prompt = "   "

    with pytest.raises(main.HTTPException) as exc:
        await ai_chat_generate_image_service(
            req=bad_req,
            request=SimpleNamespace(headers={}),
            db=SimpleNamespace(),
        )

    assert exc.value.status_code == 400
    assert "prompt" in str(exc.value.detail)


def test_get_ai_chat_access_status_service_for_guest(monkeypatch):
    guest_usage = SimpleNamespace(tokens_used=120)

    monkeypatch.setattr(main, "get_optional_current_user", lambda request, db: None)
    monkeypatch.setattr(main, "get_or_set_ai_guest_id", lambda request, response: "guest-1")
    monkeypatch.setattr(main, "get_ai_chat_guest_usage", lambda db, guest_id: guest_usage)
    monkeypatch.setattr(main, "AI_CHAT_GUEST_TOKENS", 100)
    monkeypatch.setattr(main, "AI_CHAT_BLOCK_TOKENS", 5000)
    monkeypatch.setattr(main, "AI_CHAT_BLOCK_PRICE_YEN", 100)
    monkeypatch.setattr(main, "AI_CHAT_BLOCK_TOKENS", 5000)

    out = get_ai_chat_access_status_service(
        request=SimpleNamespace(headers={}),
        response=SimpleNamespace(),
        db=SimpleNamespace(),
    )

    assert out.is_guest is True
    assert out.used_tokens == 120
    assert out.allowed_tokens == 100
    assert out.needs_upgrade is True
    assert out.show_premium_prompt is True
    assert out.show_addon_prompt is False


@pytest.mark.anyio
async def test_augment_ai_chat_character_service_uses_search_and_merge(monkeypatch):
    async def _search_character_reference_sources(character_name, anime_title=None):
        return [{"title": "ref", "link": "https://example.com", "snippet": "snippet"}]

    async def _build_fanfic_personality_from_sources(**kwargs):
        return "fanfic profile"

    monkeypatch.setattr(main, "_looks_like_fictional_character_name", lambda name: True)
    monkeypatch.setattr(ai_source_helpers, "_search_character_reference_sources", _search_character_reference_sources)
    monkeypatch.setattr(ai_source_helpers, "_build_fanfic_personality_from_sources", _build_fanfic_personality_from_sources)
    monkeypatch.setattr(
        ai_source_helpers,
        "_merge_fanfic_with_base_personality",
        lambda fanfic_personality, base_personality: f"{base_personality}|{fanfic_personality}",
    )

    out = await augment_ai_chat_character_service(req=_AugmentReq())

    assert out.character_name == "Mina"
    assert out.anime_like_name is True
    assert out.used_search is True
    assert out.enriched_personality == "kind|fanfic profile"
    assert len(out.sources) == 1


@pytest.mark.anyio
async def test_ai_chat_character_anime_title_candidates_service_merges_and_deduplicates(monkeypatch):
    async def _search_character_reference_sources(character_name):
        return [{"title": "ref", "link": "https://example.com", "snippet": "snippet"}]

    async def _build_anime_title_candidates_from_sources(**kwargs):
        return ["Sky Story", "Moon Tale", "Sky Story"]

    monkeypatch.setattr(ai_source_helpers, "_search_character_reference_sources", _search_character_reference_sources)
    monkeypatch.setattr(
        ai_source_helpers,
        "_extract_title_candidates_from_source_titles",
        lambda character_name, sources, limit: ["Moon Tale", "Star Book"],
    )
    monkeypatch.setattr(ai_source_helpers, "_build_anime_title_candidates_from_sources", _build_anime_title_candidates_from_sources)

    out = await ai_chat_character_anime_title_candidates_service(req=_AnimeTitleReq())

    assert out.character_name == "Mina"
    assert out.used_search is True
    assert out.candidates == ["Sky Story", "Moon Tale", "Star Book"]
    assert len(out.sources) == 1


def test_list_ai_chat_characters_service_builds_recommendations(monkeypatch):
    user = SimpleNamespace(id=1, username="owner")
    char = SimpleNamespace(
        id=10,
        name="Mina",
        personality="kind",
        image_url="",
        is_r18=False,
        speech_gender="female",
        is_public=False,
        is_name_duplicate=False,
        published_at=None,
        created_at=None,
        updated_at=None,
        user_id=1,
    )

    rows = [(char, "owner")]
    query = SimpleNamespace(
        join=lambda *args, **kwargs: query,
        filter=lambda *args, **kwargs: query,
        order_by=lambda *args, **kwargs: query,
        all=lambda: rows,
    )
    db = SimpleNamespace(query=lambda *args, **kwargs: query)

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(main, "_is_ai_chat_demo_bypass_user", lambda user: False)
    monkeypatch.setattr(
        main,
        "_build_ai_chat_recommendation_map",
        lambda db, user_id, character_ids: {10: {"score": 1.5, "samples": 2, "is_recommended": True}},
    )
    monkeypatch.setattr(main, "_can_edit_ai_chat_character", lambda **kwargs: True)
    monkeypatch.setattr(main, "_compute_ai_chat_name_duplicate_index", lambda db, character: 0)
    monkeypatch.setattr(main, "normalize_speech_gender", lambda value: value)

    out = list_ai_chat_characters_service(request=SimpleNamespace(headers={}), db=db)

    assert len(out) == 1
    assert out[0].id == 10
    assert out[0].recommendation_score == 1.5
    assert out[0].recommendation_samples == 2
    assert out[0].is_recommended is True


def test_create_update_publish_delete_ai_chat_character_services(monkeypatch):
    user = SimpleNamespace(id=1, username="owner")
    char = SimpleNamespace(
        id=10,
        name="Mina",
        personality="kind",
        image_url="",
        is_r18=False,
        speech_gender="female",
        is_public=False,
        is_name_duplicate=False,
        published_at=None,
        created_at=None,
        updated_at=None,
        user_id=1,
        user=SimpleNamespace(username="owner"),
        deleted_at=None,
    )
    add_calls = []
    commit_calls = []

    class _DummyAIChatCharacter:
        user_id = object()
        name = object()
        character_id = object()
        is_deleted = object()
        id = object()

        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
            self.id = 10
            self.image_url = ""
            self.is_public = False
            self.user = SimpleNamespace(username="owner")
            self.published_at = None
            self.created_at = None
            self.updated_at = None

    same_name_query = SimpleNamespace(filter=lambda *args, **kwargs: same_name_query, all=lambda: [])
    message_query = SimpleNamespace(
        filter=lambda *args, **kwargs: message_query,
        order_by=lambda *args, **kwargs: message_query,
        limit=lambda *args, **kwargs: message_query,
        all=lambda: [],
    )

    def _query(*args, **kwargs):
        if args and len(args) == 1 and args[0] is main.models.AIChatCharacter:
            return same_name_query
        return message_query

    db = SimpleNamespace(
        query=_query,
        add=lambda item: add_calls.append(item),
        commit=lambda: commit_calls.append(True),
        refresh=lambda item: None,
    )

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(public_chat_helpers, "_contains_public_chat_r18_hint", lambda text: False)
    monkeypatch.setattr(main, "normalize_speech_gender", lambda value: value)
    monkeypatch.setattr(main, "_can_edit_ai_chat_character", lambda **kwargs: True)
    monkeypatch.setattr(main, "_compute_ai_chat_name_duplicate_index", lambda db, character: 0)
    monkeypatch.setattr(main.models, "AIChatCharacter", _DummyAIChatCharacter)
    monkeypatch.setattr(main, "_find_editable_ai_chat_character", lambda **kwargs: char)
    monkeypatch.setattr(public_chat_helpers, "_is_public_chat_r18", lambda item, messages: False)
    monkeypatch.setattr(main, "_local_static_path_from_url", lambda url: None)

    created = create_ai_chat_character_service(payload=_CharacterCreateReq(), request=SimpleNamespace(headers={}), db=db)
    updated = update_ai_chat_character_service(character_id=10, payload=_CharacterUpdateReq(), request=SimpleNamespace(headers={}), db=db)
    published = publish_ai_chat_character_service(character_id=10, payload=_CharacterPublishReq(), request=SimpleNamespace(headers={}), db=db)
    deleted = delete_ai_chat_character_service(character_id=10, request=SimpleNamespace(headers={}), db=db)

    assert created.name == "Mina"
    assert updated.name == "Mina Updated"
    assert updated.personality == "bold"
    assert published.is_public is True
    assert deleted == {"deleted": True}


def test_list_ai_chat_messages_service_returns_owner_names_for_demo_reader(monkeypatch):
    user = SimpleNamespace(id=1, username="owner")
    character = SimpleNamespace(id=10, name="Mina", is_public=False, is_r18=False)
    message = SimpleNamespace(
        id=5,
        role="assistant",
        mode="say",
        is_auto_dialogue=False,
        content="hello",
        character_name_snapshot="Mina",
        created_at=None,
    )

    query = SimpleNamespace(
        join=lambda *args, **kwargs: query,
        filter=lambda *args, **kwargs: query,
        order_by=lambda *args, **kwargs: query,
        limit=lambda *args, **kwargs: query,
        all=lambda: [(message, "other-user")],
    )
    db = SimpleNamespace(query=lambda *args, **kwargs: query)

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(main, "_find_accessible_ai_chat_character", lambda **kwargs: character)
    monkeypatch.setattr(main, "_is_ai_chat_demo_bypass_user", lambda user: True)

    out = list_ai_chat_messages_service(character_id=10, request=SimpleNamespace(headers={}), db=db)

    assert len(out) == 1
    assert out[0].id == 5
    assert out[0].character_name == "Mina"
    assert out[0].message_owner_username == "other-user"


@pytest.mark.anyio
async def test_upload_ai_chat_character_image_service_saves_gif(monkeypatch, tmp_path):
    user = SimpleNamespace(id=1, username="owner")
    character = SimpleNamespace(id=10, image_url=None)

    class _File:
        content_type = "image/gif"

        async def read(self):
            return b"GIF89a"

    db = SimpleNamespace(add=lambda item: None, commit=lambda: None, refresh=lambda item: None)

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(main, "_find_editable_ai_chat_character", lambda **kwargs: character)
    monkeypatch.setattr(main, "_local_static_path_from_url", lambda url: None)
    monkeypatch.setattr(main, "AI_CHAT_CHARACTER_IMAGE_DIR", str(tmp_path))
    monkeypatch.setattr(main.secrets, "token_hex", lambda n: "abc123")

    out = await upload_ai_chat_character_image_service(
        character_id=10,
        request=SimpleNamespace(headers={}),
        file=_File(),
        db=db,
    )

    assert out.ok is True
    assert out.image_url == "/static/ai_chat_character_images/chat_char_10_abc123.gif"


def test_get_public_ai_chat_character_detail_service_records_view(monkeypatch):
    viewer = SimpleNamespace(id=2)
    character = SimpleNamespace(
        id=10,
        name="Mina",
        personality="kind",
        image_url="",
        is_r18=False,
        published_at=None,
    )
    message = SimpleNamespace(
        id=7,
        role="assistant",
        mode="say",
        is_auto_dialogue=False,
        content="hello",
        created_at=None,
    )
    row_query = SimpleNamespace(
        join=lambda *args, **kwargs: row_query,
        filter=lambda *args, **kwargs: row_query,
        first=lambda: (character, "owner"),
    )
    message_query = SimpleNamespace(
        filter=lambda *args, **kwargs: message_query,
        order_by=lambda *args, **kwargs: message_query,
        limit=lambda *args, **kwargs: message_query,
        all=lambda: [message],
    )
    count_query = SimpleNamespace(filter=lambda *args, **kwargs: count_query, count=lambda: 3)
    liked_query = SimpleNamespace(filter=lambda *args, **kwargs: liked_query, first=lambda: object())
    favorited_query = SimpleNamespace(filter=lambda *args, **kwargs: favorited_query, first=lambda: None)
    commits = []
    view_history = {}
    query_results = [
        row_query,
        message_query,
        count_query,
        count_query,
        liked_query,
        favorited_query,
    ]

    def _query(*args, **kwargs):
        if not query_results:
            raise AssertionError(f"unexpected query args: {args}")
        return query_results.pop(0)

    db = SimpleNamespace(
        query=_query,
        add=lambda item: None,
        commit=lambda: commits.append(True),
    )

    monkeypatch.setattr(main, "get_optional_current_user", lambda request, db: viewer)
    monkeypatch.setattr(main, "resolve_site_key", lambda request: "site")
    monkeypatch.setattr(main, "can_user_access_novel_age_limit", lambda user, age: True)
    monkeypatch.setattr(public_chat_helpers, "_is_public_chat_r18", lambda character, messages: False)
    monkeypatch.setattr(public_chat_helpers, "_trim_public_character_intro", lambda text: text)
    monkeypatch.setattr(
        main,
        "record_user_view_history",
        lambda db, user_id, target_type, target_id, site_key: view_history.update(
            {
                "user_id": user_id,
                "target_type": target_type,
                "target_id": target_id,
                "site_key": site_key,
            }
        ),
    )

    out = get_public_ai_chat_character_detail_service(
        character_id=10,
        request=SimpleNamespace(headers={}),
        db=db,
    )

    assert out.id == 10
    assert out.like_count == 3
    assert out.favorite_count == 3
    assert out.is_liked is True
    assert out.is_favorited is False
    assert len(out.messages) == 1
    assert view_history == {
        "user_id": 2,
        "target_type": "ai_public_character",
        "target_id": 10,
        "site_key": "site",
    }
    assert commits == [True]


def test_public_ai_chat_like_and_favorite_services(monkeypatch):
    user = SimpleNamespace(id=2, username="reader")
    character = SimpleNamespace(id=10, name="Mina", is_r18=False, user_id=9)
    notifications = []
    added = []
    deleted = []
    commits = []

    class _Like:
        character_id = object()
        user_id = object()

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _Favorite:
        character_id = object()
        user_id = object()

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _CountQuery:
        def filter(self, *args, **kwargs):
            return self

        def count(self):
            return 4

    class _FirstQuery:
        def __init__(self, value):
            self.value = value

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return self.value

    query_results = [
        _FirstQuery(character),
        _FirstQuery(None),
        _CountQuery(),
        _FirstQuery(character),
        _FirstQuery(None),
        _CountQuery(),
        _FirstQuery(character),
        _FirstQuery(SimpleNamespace(id=1)),
        _CountQuery(),
        _FirstQuery(character),
        _FirstQuery(SimpleNamespace(id=2)),
        _CountQuery(),
    ]

    def _query(*args, **kwargs):
        if not query_results:
            raise AssertionError(f"unexpected query args: {args}")
        return query_results.pop(0)

    db = SimpleNamespace(
        query=_query,
        add=lambda item: added.append(item),
        delete=lambda item: deleted.append(item),
        commit=lambda: commits.append(True),
    )

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(main, "can_user_access_novel_age_limit", lambda user, age: True)
    monkeypatch.setattr(main.models, "AIChatCharacterLike", _Like)
    monkeypatch.setattr(main.models, "AIChatCharacterFavorite", _Favorite)
    monkeypatch.setattr(notification_helpers, "create_notification", lambda db, **kwargs: notifications.append(kwargs))
    monkeypatch.setattr(notification_helpers, "send_web_push_to_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(notification_helpers, "send_notification_email_if_enabled", lambda *args, **kwargs: None)

    liked = like_public_ai_chat_character_service(character_id=10, request=SimpleNamespace(headers={}), db=db)
    favorited = favorite_public_ai_chat_character_service(character_id=10, request=SimpleNamespace(headers={}), db=db)
    unliked = unlike_public_ai_chat_character_service(character_id=10, request=SimpleNamespace(headers={}), db=db)
    unfavorited = unfavorite_public_ai_chat_character_service(character_id=10, request=SimpleNamespace(headers={}), db=db)

    assert liked == {"ok": True, "liked": True, "like_count": 4}
    assert favorited == {"ok": True, "favorited": True, "favorite_count": 4}
    assert unliked == {"ok": True, "liked": False, "like_count": 4}
    assert unfavorited == {"ok": True, "favorited": False, "favorite_count": 4}
    assert len(added) == 2
    assert len(deleted) == 2
    assert len(notifications) == 2


def test_get_ai_chat_engagement_summary_service_aggregates_scores(monkeypatch):
    user = SimpleNamespace(id=1)
    character = SimpleNamespace(id=10, speech_gender="female")
    row1 = SimpleNamespace(
        id=1,
        created_at=None,
        latency_bucket="fast",
        followup_latency_seconds=1.0,
        engagement_score=2.0,
        latency_score=4.0,
        intimacy_score=6.0,
        cuteness_score=8.0,
        proactiveness_score=10.0,
        consistency_score=12.0,
        empathy_score=14.0,
        novelty_score=16.0,
        clarity_score=18.0,
        coolness_score=20.0,
        seriousness_score=22.0,
    )
    row2 = SimpleNamespace(
        id=2,
        created_at=None,
        latency_bucket="slow",
        followup_latency_seconds=3.0,
        engagement_score=4.0,
        latency_score=6.0,
        intimacy_score=8.0,
        cuteness_score=10.0,
        proactiveness_score=12.0,
        consistency_score=14.0,
        empathy_score=16.0,
        novelty_score=18.0,
        clarity_score=20.0,
        coolness_score=22.0,
        seriousness_score=24.0,
    )
    query = SimpleNamespace(
        filter=lambda *args, **kwargs: query,
        order_by=lambda *args, **kwargs: query,
        limit=lambda *args, **kwargs: query,
        all=lambda: [row1, row2],
    )
    db = SimpleNamespace(query=lambda *args, **kwargs: query)

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(main, "_find_editable_ai_chat_character", lambda **kwargs: character)
    monkeypatch.setattr(main, "normalize_speech_gender", lambda value: value)

    out = get_ai_chat_engagement_summary_service(
        character_id=10,
        request=SimpleNamespace(headers={}),
        db=db,
    )

    assert out.sample_size == 2
    assert out.average_engagement_score == 3.0
    assert out.average_latency_score == 5.0
    assert out.average_seriousness_score == 23.0
    assert len(out.recent) == 2
    assert out.recent[0].id == 1


def test_import_and_delete_ai_chat_messages_services(monkeypatch):
    user = SimpleNamespace(id=1)
    character = SimpleNamespace(id=10, name="Mina", personality="kind", is_r18=False)
    added = []
    commits = []

    class _Field:
        def __eq__(self, other):
            return True

        def __ge__(self, other):
            return True

    class _DummyAIChatMessage:
        user_id = _Field()
        character_id = _Field()
        is_deleted = _Field()
        id = _Field()

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    replace_query = SimpleNamespace(
        filter=lambda *args, **kwargs: replace_query,
        update=lambda values, synchronize_session=False: 2,
    )
    target_query = SimpleNamespace(
        filter=lambda *args, **kwargs: target_query,
        first=lambda: SimpleNamespace(id=5),
    )
    delete_query = SimpleNamespace(
        filter=lambda *args, **kwargs: delete_query,
        update=lambda values, synchronize_session=False: 3,
    )
    query_results = [replace_query, target_query, delete_query]

    def _query(*args, **kwargs):
        if not query_results:
            raise AssertionError(f"unexpected query args: {args}")
        return query_results.pop(0)

    db = SimpleNamespace(
        query=_query,
        add=lambda item: added.append(item),
        commit=lambda: commits.append(True),
    )

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(main, "_find_editable_ai_chat_character", lambda **kwargs: character)
    monkeypatch.setattr(public_chat_helpers, "_contains_public_chat_r18_hint", lambda content: content == "reply")
    monkeypatch.setattr(main.models, "AIChatMessage", _DummyAIChatMessage)

    imported = import_ai_chat_messages_service(
        character_id=10,
        payload=_MessageImportReq(),
        request=SimpleNamespace(headers={}),
        db=db,
    )
    deleted = delete_ai_chat_messages_from_point_service(
        character_id=10,
        message_id=5,
        request=SimpleNamespace(headers={}),
        db=db,
    )

    assert imported.ok is True
    assert imported.imported == 2
    assert imported.replaced == 2
    assert deleted.ok is True
    assert deleted.deleted == 3
    assert character.is_r18 is True
    assert len(added) == 3
    assert len(commits) == 2


def test_delete_ai_chat_message_image_service_updates_remaining_images(monkeypatch):
    user = SimpleNamespace(id=1)
    character = SimpleNamespace(id=10)
    target = SimpleNamespace(content="stored", is_deleted=False, deleted_at=None)
    query = SimpleNamespace(filter=lambda *args, **kwargs: query, first=lambda: target)
    db = SimpleNamespace(query=lambda *args, **kwargs: query, add=lambda item: None, commit=lambda: None)

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(main, "_find_editable_ai_chat_character", lambda **kwargs: character)
    monkeypatch.setattr(
        main,
        "_parse_ai_chat_image_message",
        lambda content: {
            "kind": "uploaded_images",
            "prompt": "a\nb",
            "images": [{"url": "/a.png", "filename": "a.png"}, {"url": "/b.png", "filename": "b.png"}],
            "meta": {"descriptions": ["a", "b"]},
        },
    )
    monkeypatch.setattr(main, "_serialize_ai_chat_image_message", lambda **kwargs: "serialized")

    out = delete_ai_chat_message_image_service(
        character_id=10,
        message_id=20,
        image_index=0,
        request=SimpleNamespace(headers={}),
        db=db,
    )

    assert out.ok is True
    assert out.deleted_message is False
    assert out.remaining_images == 1
    assert target.content == "serialized"


@pytest.mark.anyio
async def test_upload_ai_chat_message_images_service_saves_gif(monkeypatch, tmp_path):
    user = SimpleNamespace(id=1)
    character = SimpleNamespace(id=10, name="Mina", personality="kind")

    class _Field:
        def __eq__(self, other):
            return True

    class _DummyAIChatMessage:
        user_id = _Field()
        character_id = _Field()
        id = _Field()

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self.id = 99
            self.created_at = None

    class _File:
        content_type = "image/gif"

        async def read(self):
            return b"GIF89a"

    created = {}

    def _refresh(msg):
        created["msg"] = msg

    db = SimpleNamespace(add=lambda item: None, commit=lambda: None, refresh=_refresh)

    async def _describe_uploaded_chat_images(urls):
        return ["desc"]

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(main, "_find_editable_ai_chat_character", lambda **kwargs: character)
    monkeypatch.setattr(main, "AI_CHAT_MESSAGE_IMAGE_DIR", str(tmp_path))
    monkeypatch.setattr(main.secrets, "token_hex", lambda n: "abc123")
    monkeypatch.setattr(main, "_describe_uploaded_chat_images", _describe_uploaded_chat_images)
    monkeypatch.setattr(main, "_serialize_ai_chat_image_message", lambda **kwargs: "serialized-content")
    monkeypatch.setattr(main.models, "AIChatMessage", _DummyAIChatMessage)

    out = await upload_ai_chat_message_images_service(
        character_id=10,
        request=SimpleNamespace(headers={}),
        files=[_File()],
        db=db,
    )

    assert out.ok is True
    assert out.message_id == 99
    assert out.descriptions == ["desc"]
    assert out.images[0].url == "/static/ai_chat_message_images/chat_msg_10_1_abc123_0.gif"
    assert created["msg"].content == "serialized-content"


def test_get_ai_chat_latest_prompt_preview_service_builds_prompt(monkeypatch):
    user = SimpleNamespace(id=1)
    character = SimpleNamespace(id=10, name="Mina", personality="kind")
    latest_user_msg = SimpleNamespace(
        id=8,
        role="user",
        mode="say",
        content="hello",
        character_name_snapshot="Mina",
        personality_snapshot="kind",
        language_style_snapshot="normal",
    )
    history_rows = [
        SimpleNamespace(role="assistant", mode="say", content="hi"),
        latest_user_msg,
    ]
    latest_query = SimpleNamespace(
        filter=lambda *args, **kwargs: latest_query,
        order_by=lambda *args, **kwargs: latest_query,
        first=lambda: latest_user_msg,
    )
    history_query = SimpleNamespace(
        filter=lambda *args, **kwargs: history_query,
        order_by=lambda *args, **kwargs: history_query,
        limit=lambda *args, **kwargs: history_query,
        all=lambda: history_rows,
    )
    query_results = [latest_query, history_query]

    def _query(*args, **kwargs):
        if not query_results:
            raise AssertionError(f"unexpected query args: {args}")
        return query_results.pop(0)

    db = SimpleNamespace(query=_query)

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(main, "_find_editable_ai_chat_character", lambda **kwargs: character)
    monkeypatch.setattr(main, "_normalize_language_style", lambda style: style)
    monkeypatch.setattr(main, "_build_ai_chat_history_text", lambda history, character_name: "history")
    monkeypatch.setattr(main, "build_summary_text", lambda history, recent_limit=20, max_chars=1200: "summary")
    monkeypatch.setattr(main, "AI_CHAT_MEMORY_ENABLED", False)
    monkeypatch.setattr(main, "_build_language_style_rules", lambda language_style: "style-rules")
    monkeypatch.setattr(main, "_build_ai_chat_engagement_learning_instruction", lambda *args, **kwargs: "engage")
    monkeypatch.setattr(main, "_build_ai_chat_prompt", lambda **kwargs: "prompt-body")
    monkeypatch.setattr(main, "_build_ai_chat_system_instructions", lambda **kwargs: "system-body")

    out = get_ai_chat_latest_prompt_preview_service(
        character_id=10,
        request=SimpleNamespace(headers={}),
        db=db,
        r18=False,
    )

    assert out.source_message_id == 8
    assert out.prompt == "prompt-body"
    assert out.system_instructions == "system-body"
    assert out.summary_text == "summary"
    assert len(out.history) == 2
