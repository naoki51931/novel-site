import importlib
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main, models
from app.ai_novel import AINovelRequest, AINovelResponse
from app.features.ai_feature_service import generate_ai_novel_service
from app.services.episodes_core_service import update_episode_service
from app.services.episodes_write_service import create_episode_service
from app.services.novels_write_service import update_novel_service


def _request(path: str = "/api/test"):
    return SimpleNamespace(url=SimpleNamespace(path=path), headers={})


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _make_user(db, username: str, *, is_premium: bool = True):
    user = models.User(username=username, password_hash="x", is_premium=is_premium)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_novel(db, author_id: int, **overrides):
    novel = models.Novel(
        title=overrides.pop("title", "novel"),
        description=overrides.pop("description", "desc"),
        author_id=author_id,
        site_key=overrides.pop("site_key", "main"),
        is_public=overrides.pop("is_public", True),
        language=overrides.pop("language", "ja"),
        **overrides,
    )
    db.add(novel)
    db.commit()
    db.refresh(novel)
    return novel


def _make_episode(db, novel_id: int, **overrides):
    episode = models.Episode(
        novel_id=novel_id,
        title=overrides.pop("title", "ep"),
        body=overrides.pop("body", "body"),
        site_key=overrides.pop("site_key", "main"),
        status=overrides.pop("status", "public"),
        is_public=overrides.pop("is_public", True),
        language=overrides.pop("language", "ja"),
        episode_number=overrides.pop("episode_number", 1),
        **overrides,
    )
    db.add(episode)
    db.commit()
    db.refresh(episode)
    return episode


def _install_common_legacy_patches(monkeypatch):
    monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")
    monkeypatch.setattr(main, "normalize_language", lambda value: (value or "ja"))
    monkeypatch.setattr(main, "normalize_optional_datetime", lambda value: value)
    monkeypatch.setattr(main, "normalize_illust_tag", lambda value: (value or "").strip() or None)
    monkeypatch.setattr(main, "normalize_meta_tags", lambda value: value)
    monkeypatch.setattr(main, "serialize_meta_tags", lambda value: value)
    monkeypatch.setattr(main, "get_novel_tag_names", lambda db, novel_id: [])
    monkeypatch.setattr(main, "get_episode_tag_names", lambda db, episode_id: [])
    monkeypatch.setattr(main, "_request_origin", lambda request, fallback: "https://example.com")
    monkeypatch.setattr(main, "FRONTEND_ORIGIN", "https://example.com")
    monkeypatch.setattr(main, "AUTO_TRANSLATION_REQUIRED", False)
    monkeypatch.setattr(main, "_background_upsert_novel_translation", lambda novel_id: None)
    monkeypatch.setattr(main, "_background_upsert_episode_and_novel_translation", lambda episode_id: None)
    monkeypatch.setattr(main, "_background_notify_episode_published", lambda novel_id, episode_id, site_key: None)
    monkeypatch.setattr(main, "invalidate_public_list_caches", lambda: None)
    monkeypatch.setattr(main, "notify_recommended_users_new_novel", lambda db, novel: None)
    monkeypatch.setattr(main, "notify_followers_author_new_novel", lambda db, novel: None)
    monkeypatch.setattr(main, "notify_tag_followers_new_novel", lambda db, novel: None)


def _install_tag_helper(monkeypatch):
    def _get_or_create_tags(db, names):
        tags = {}
        for name in names:
            clean = (name or "").strip()
            if not clean:
                continue
            tag = db.query(models.Tag).filter(models.Tag.name == clean).first()
            if not tag:
                tag = models.Tag(name=clean)
                db.add(tag)
                db.flush()
            tags[clean] = tag
        return tags

    monkeypatch.setattr(main, "_get_or_create_tags", _get_or_create_tags)


def test_create_episode_service_persists_episode_tags_and_illusts(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")
        novel = _make_novel(db, user.id)
        background_tasks = BackgroundTasks()
        enqueued = []

        _install_common_legacy_patches(monkeypatch)
        _install_tag_helper(monkeypatch)
        monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
        monkeypatch.setattr(main, "assert_premium_user", lambda user, message: None)
        monkeypatch.setattr(main, "resolve_episode_publish_mode", lambda *args, **kwargs: "public")
        monkeypatch.setattr(
            main,
            "apply_episode_publish_mode",
            lambda episode, publish_mode, scheduled_publish_at: (
                setattr(episode, "status", "public"),
                setattr(episode, "is_public", True),
                setattr(episode, "scheduled_publish_at", scheduled_publish_at),
            ),
        )
        monkeypatch.setattr(main, "is_episode_draft", lambda episode: not bool(getattr(episode, "is_public", False)))
        monkeypatch.setattr(main, "_is_episode_indexable_for_search", lambda episode, novel: True)
        monkeypatch.setattr(
            main,
            "_enqueue_indexnow_urls",
            lambda **kwargs: enqueued.append((kwargs["event"], kwargs["urls"])),
        )

        payload = SimpleNamespace(
            title="episode title",
            body="episode body",
            cover_image_url="/cover.png",
            episode_number=3,
            is_free_public=True,
            language="ja",
            publish_mode="public",
            status=None,
            scheduled_publish_at=None,
            tag_names=["battle", "hero"],
            illusts=[
                SimpleNamespace(
                    image_url="/illust.png",
                    position=1,
                    caption="cap",
                    illust_tag="hero-face",
                    meta_tags="m1,m2",
                )
            ],
        )

        episode = create_episode_service(
            novel_id=novel.id,
            payload=payload,
            background_tasks=background_tasks,
            request=_request("/api/novels/1/episodes"),
            db=db,
        )

        db.refresh(episode)
        assert episode.title == "episode title"
        assert episode.is_public is True
        assert episode.status == "public"
        assert episode.episode_number == 3
        assert len(episode.illusts) == 1
        assert {tag.name for tag in db.query(models.Tag).all()} == {"battle", "hero"}
        assert len(db.query(models.EpisodeTag).filter(models.EpisodeTag.episode_id == episode.id).all()) == 2
        assert enqueued == [("urlUpdated", [f"https://example.com/episodes/{episode.id}"])]
        assert len(background_tasks.tasks) == 2
    finally:
        db.close()


def test_update_episode_service_updates_content_and_tags(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")
        novel = _make_novel(db, user.id)
        episode = _make_episode(db, novel.id, title="before", body="old body", is_public=True, status="public")
        background_tasks = BackgroundTasks()
        enqueued = []

        _install_common_legacy_patches(monkeypatch)
        _install_tag_helper(monkeypatch)
        monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
        monkeypatch.setattr(main, "get_episode_in_site_or_404", lambda db, request, episode_id: db.get(models.Episode, episode_id))
        monkeypatch.setattr(main, "get_novel_in_site_or_404", lambda db, request, novel_id: db.get(models.Novel, novel_id))
        monkeypatch.setattr(main, "resolve_episode_publish_mode", lambda *args, **kwargs: None)
        monkeypatch.setattr(main, "apply_episode_publish_mode", lambda episode, publish_mode, scheduled_publish_at: None)
        monkeypatch.setattr(main, "assert_premium_user", lambda user, message: None)
        monkeypatch.setattr(main, "is_episode_draft", lambda episode: not bool(getattr(episode, "is_public", False)))
        monkeypatch.setattr(main, "_is_episode_indexable_for_search", lambda episode, novel: True)
        monkeypatch.setattr(
            main,
            "_enqueue_indexnow_urls",
            lambda **kwargs: enqueued.append((kwargs["event"], kwargs["urls"])),
        )

        updated = update_episode_service(
            episode_id=episode.id,
            background_tasks=background_tasks,
            request=_request(f"/api/episodes/{episode.id}"),
            payload={
                "title": "after",
                "body": "new body",
                "tag_names": ["magic", "school"],
            },
            db=db,
        )

        db.refresh(updated)
        assert updated.title == "after"
        assert updated.body == "new body"
        assert {tag.name for tag in db.query(models.Tag).all()} == {"magic", "school"}
        assert len(db.query(models.EpisodeTag).filter(models.EpisodeTag.episode_id == episode.id).all()) == 2
        assert enqueued == [("urlUpdated", [f"https://example.com/episodes/{episode.id}"])]
        assert len(background_tasks.tasks) == 1
    finally:
        db.close()


def test_update_novel_service_updates_fields_and_tags(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")
        novel = _make_novel(db, user.id, title="before", description="old desc", is_public=True)
        background_tasks = BackgroundTasks()
        enqueued = []

        _install_common_legacy_patches(monkeypatch)
        monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
        monkeypatch.setattr(main, "_is_novel_indexable_for_search", lambda novel: bool(getattr(novel, "is_public", False)))
        monkeypatch.setattr(
            main,
            "_enqueue_indexnow_urls",
            lambda **kwargs: enqueued.append((kwargs["event"], kwargs["urls"])),
        )

        payload = SimpleNamespace(
            language="ja",
            title="after",
            description="new desc",
            age_limit=None,
            is_ai_generated=None,
            creative_type=None,
            is_public=True,
            fanfic_source_title=None,
            fanfic_characters=None,
            fanfic_coupling=None,
            fanfic_notes=None,
            series_name=None,
            series_order=None,
            tag_names=["fantasy", "adventure"],
        )

        updated = update_novel_service(
            novel_id=novel.id,
            payload=payload,
            request=_request(f"/api/novels/{novel.id}"),
            background_tasks=background_tasks,
            db=db,
        )

        db.refresh(updated)
        assert updated.title == "after"
        assert updated.description == "new desc"
        assert {tag.name for tag in db.query(models.Tag).all()} == {"fantasy", "adventure"}
        assert len(db.query(models.NovelTag).filter(models.NovelTag.novel_id == novel.id).all()) == 2
        assert enqueued == [("urlUpdated", [f"https://example.com/novels/{novel.id}"])]
        assert len(background_tasks.tasks) == 1
    finally:
        db.close()


def test_generate_novel_summary_candidates_uses_first_episode(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")
        novel = _make_novel(db, user.id)
        _make_episode(db, novel.id, title="ep1", body="first body", episode_number=1)
        _make_episode(db, novel.id, title="ep2", body="second body", episode_number=2)

        monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
        monkeypatch.setattr(main, "get_novel_in_site_or_404", lambda db, request, novel_id: db.get(models.Novel, novel_id))
        monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")

        seen = {}

        async def _fake_summary(source_text, model=None):
            seen["source_text"] = source_text
            seen["model"] = model
            return (["sum1", "sum2"], 12, "summary-model")

        monkeypatch.setattr(main, "call_openai_summary_candidates", _fake_summary)

        out = asyncio.run(main.generate_novel_summary_candidates(
            novel_id=novel.id,
            request=_request(f"/api/novels/{novel.id}/summary_candidates"),
            db=db,
        ))

        assert seen["source_text"] == "first body"
        assert out.candidates == ["sum1", "sum2"]
        assert out.model == "summary-model"
        assert out.used_tokens == 12
    finally:
        db.close()


def test_generate_novel_tag_candidates_uses_first_episode(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")
        novel = _make_novel(db, user.id)
        _make_episode(db, novel.id, title="ep1", body="tag source", episode_number=1)

        monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
        monkeypatch.setattr(main, "get_novel_in_site_or_404", lambda db, request, novel_id: db.get(models.Novel, novel_id))
        monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")

        seen = {}

        async def _fake_tags(source_text, model=None):
            seen["source_text"] = source_text
            seen["model"] = model
            return (["tag-a", "tag-b"], 9, "tag-model")

        monkeypatch.setattr(main, "call_openai_tag_candidates", _fake_tags)

        out = asyncio.run(main.generate_novel_tag_candidates(
            novel_id=novel.id,
            request=_request(f"/api/novels/{novel.id}/tag_candidates"),
            db=db,
        ))

        assert seen["source_text"] == "tag source"
        assert out.candidates == ["tag-a", "tag-b"]
        assert out.model == "tag-model"
        assert out.used_tokens == 9
    finally:
        db.close()


def test_generate_novel_title_candidates_uses_first_episode(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")
        novel = _make_novel(db, user.id)
        _make_episode(db, novel.id, title="ep1", body="title source body", episode_number=1)

        monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
        monkeypatch.setattr(main, "get_novel_in_site_or_404", lambda db, request, novel_id: db.get(models.Novel, novel_id))
        monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")

        seen = {}

        async def _fake_titles(source_text, model=None, suggestions_count=None):
            seen["source_text"] = source_text
            seen["model"] = model
            seen["suggestions_count"] = suggestions_count
            return (["title-a", "title-b"], 15, "title-model")

        monkeypatch.setattr(main, "call_openai_title_candidates", _fake_titles)

        out = asyncio.run(main.generate_novel_title_candidates(
            novel_id=novel.id,
            request=_request(f"/api/novels/{novel.id}/title_candidates"),
            db=db,
        ))

        assert seen["source_text"] == "title source body"
        assert seen["suggestions_count"] == 5
        assert out.candidates == ["title-a", "title-b"]
        assert out.model == "title-model"
        assert out.used_tokens == 15
    finally:
        db.close()


def test_me_and_profile_routes_are_registered():
    paths = {route.path for route in main.app.routes}

    assert "/api/me/favorites" in paths
    assert "/api/me/ai/chat/favorites" in paths
    assert "/api/me/view-history/novels" in paths
    assert "/api/me/analytics/novels" in paths
    assert "/api/users/me" in paths


def test_all_router_module_paths_are_mounted():
    mounted = {route.path for route in main.app.routes}
    router_dir = Path(__file__).resolve().parents[1] / "app" / "routers"
    missing_by_module = {}

    for entry in sorted(os.listdir(router_dir)):
        if not entry.endswith(".py") or entry == "__init__.py":
            continue
        module = importlib.import_module(f"app.routers.{entry[:-3]}")
        router = getattr(module, "router", None)
        if router is None:
            continue
        missing = sorted({route.path for route in router.routes if route.path not in mounted})
        if missing:
            missing_by_module[entry] = missing

    assert missing_by_module == {}


def test_generate_ai_novel_service_logs_guest_usage(monkeypatch):
    db = _make_session()
    try:
        class _Response:
            def set_cookie(self, *args, **kwargs):
                return None

        response = _Response()
        req = AINovelRequest(
            title_hint="guest title",
            genre="fantasy",
            characters="hero",
            tone="calm",
        )

        monkeypatch.setattr(main, "get_optional_current_user", lambda request, db: None)
        monkeypatch.setattr(main, "is_effective_premium_user", lambda user: False)
        monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")
        monkeypatch.setattr(main, "AI_WEAVIATE_FEATURES_ENABLED", False)
        monkeypatch.setattr(main, "get_or_set_ai_guest_id", lambda request, response: "guest_test_1")
        monkeypatch.setattr(
            main,
            "require_guest_ai_quota",
            lambda db, guest_id: models.AIGuestGenerateUsage(guest_id=guest_id, generate_count=0),
        )
        monkeypatch.setattr(main, "provider_from_request", lambda req: "openai")

        async def _fake_call(req_for_ai):
            return AINovelResponse(
                generated_title="generated",
                body="body",
                used_tokens=123,
                model="gpt-4.1-mini",
            )

        monkeypatch.setattr(main, "call_openai_novel_api", _fake_call)
        monkeypatch.setattr(main, "_format_ai_log_model", lambda provider, model: f"{provider}:{model}")
        monkeypatch.setattr(main, "AI_GUEST_FREE_MAX", 10)

        out = asyncio.run(
            generate_ai_novel_service(
                req=req,
                request=_request("/api/ai/novels/generate"),
                response=response,
                db=db,
            )
        )

        logs = db.query(models.AIGenerateLog).all()
        assert len(logs) == 1
        assert logs[0].guest_id == "guest_test_1"
        assert logs[0].user_id is None
        assert logs[0].tokens_used == 123
        assert logs[0].model == "openai:gpt-4.1-mini"
        assert out.guest_remaining == 9
    finally:
        db.close()
