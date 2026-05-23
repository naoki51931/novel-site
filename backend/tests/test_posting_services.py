import importlib
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import asyncio
from datetime import date, datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import author_dashboard_helpers, google_indexing_helpers, main, models, notification_helpers
from app.ai_novel import AINovelRequest, AINovelResponse
from app.features.ai_feature_service import generate_ai_novel_service
from app.services.episodes_core_service import update_episode_service
from app.services.episodes_write_service import create_episode_service
from app.services.comments_service import (
    delete_episode_comment_service,
    post_comment_service,
)
from app.services.author_dashboard_service import get_author_dashboard_service
from app.services.auth_service import (
    login_service,
    password_reset_confirm_service,
)
from app.services.novel_assets_service import (
    generate_novel_summary_candidates_service,
    generate_novel_tag_candidates_service,
    generate_novel_title_candidates_service,
)
from app.services.novels_write_service import update_novel_service
from app.services.public_profile_service import (
    get_author_stats_service,
    read_public_user_service,
)
from app.services.admin_payouts_service import (
    admin_supports_timeline_service,
    mark_payout_failed_service,
)
from app.services.admin_i18n_service import (
    admin_cancel_i18n_job_service,
    admin_i18n_job_status_service,
    admin_list_i18n_jobs_service,
    admin_retranslate_remaining_i18n_service,
    admin_start_i18n_job_service,
)
from app.services.admin_indexing_service import (
    admin_indexing_carryover_clear_service,
    admin_indexing_carryover_service,
    admin_indexing_submit_service,
    admin_indexing_urls_service,
    admin_indexnow_submit_service,
)
from app.services.admin_maintenance_service import (
    admin_backfill_translations_service,
    admin_delete_board_post_service,
)
from app.services.admin_service import (
    admin_delete_user_service,
    admin_get_ai_logs_service,
    admin_list_users_service,
    admin_login_service,
)
from app.services.ai_chat_usage_service import get_my_ai_logs_service
from app.services.payments_service import (
    create_support_plan_service,
    get_author_balance_service,
    stripe_checkout_service,
    stripe_webhook_service,
)
from app.services.public_contact_service import public_create_contact_message_service
from app.services.other_service import (
    list_series_overview_service,
    list_trending_tags_service,
)
from app.services.other_pages_service import (
    share_episode_page_service,
    sitemap_tags_xml_service,
)


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

        out = asyncio.run(generate_novel_summary_candidates_service(
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

        out = asyncio.run(generate_novel_tag_candidates_service(
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

        out = asyncio.run(generate_novel_title_candidates_service(
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


def test_post_comment_service_creates_comment_and_notification(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        commenter = _make_user(db, "commenter")
        novel = _make_novel(db, author.id, title="novel title")

        monkeypatch.setattr(main, "require_current_user", lambda request, db: commenter)
        monkeypatch.setattr(main, "get_novel_in_site_or_404", lambda db, request, novel_id: db.get(models.Novel, novel_id))
        monkeypatch.setattr(main, "_truncate_text", lambda body, limit: body[:limit])

        notifications = []
        emails = []

        def _fake_create_notification(db, **kwargs):
            notifications.append(kwargs)

        def _fake_send_notification_email_if_enabled(db, **kwargs):
            emails.append(kwargs)

        monkeypatch.setattr(notification_helpers, "create_notification", _fake_create_notification)
        monkeypatch.setattr(
            notification_helpers,
            "send_notification_email_if_enabled",
            _fake_send_notification_email_if_enabled,
        )

        out = post_comment_service(
            novel_id=novel.id,
            payload={"body": " hello comment "},
            request=_request(f"/api/novels/{novel.id}/comments"),
            db=db,
        )

        comment = db.query(models.NovelComment).filter(models.NovelComment.id == out["id"]).first()
        assert out["ok"] is True
        assert comment is not None
        assert comment.body == "hello comment"
        assert len(notifications) == 1
        assert notifications[0]["notif_type"] == "novel_comment"
        assert notifications[0]["user_id"] == author.id
        assert len(emails) == 1
        assert emails[0]["user_id"] == author.id
    finally:
        db.close()


def test_delete_episode_comment_service_allows_author_to_remove_comment(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        commenter = _make_user(db, "commenter")
        novel = _make_novel(db, author.id)
        episode = _make_episode(db, novel.id)
        comment = models.EpisodeComment(episode_id=episode.id, user_id=commenter.id, body="body")
        db.add(comment)
        db.commit()
        db.refresh(comment)

        monkeypatch.setattr(main, "require_current_user", lambda request, db: author)
        monkeypatch.setattr(main, "get_episode_in_site_or_404", lambda db, request, episode_id: db.get(models.Episode, episode_id))
        monkeypatch.setattr(main, "get_novel_in_site_or_404", lambda db, request, novel_id: db.get(models.Novel, novel_id))

        out = delete_episode_comment_service(
            episode_id=episode.id,
            comment_id=comment.id,
            request=_request(f"/api/episodes/{episode.id}/comments/{comment.id}"),
            db=db,
        )

        remaining = db.query(models.EpisodeComment).filter(models.EpisodeComment.id == comment.id).first()
        assert out == {"ok": True}
        assert remaining is None
    finally:
        db.close()


def test_read_public_user_service_returns_cached_profile(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")
        cached_payload = {"id": user.id, "username": user.username, "cached": True}

        monkeypatch.setattr(main, "build_public_cache_key", lambda namespace, payload: f"{namespace}:{payload['username']}")
        monkeypatch.setattr(main, "redis_json_get", lambda key: cached_payload)

        out = read_public_user_service(username="author", db=db)

        assert out == cached_payload
    finally:
        db.close()


def test_get_author_stats_service_aggregates_public_counts(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        novel1 = _make_novel(db, author.id, view_count=10, like_count=3)
        novel2 = _make_novel(db, author.id, view_count=5, like_count=7)
        db.add(models.NovelFavorite(user_id=author.id, novel_id=novel1.id))
        db.add(models.NovelFavorite(user_id=author.id, novel_id=novel2.id))
        db.commit()

        monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")
        monkeypatch.setattr(main, "require_current_user", lambda request, db: None)
        monkeypatch.setattr(main, "_apply_public_novel_age_filter", lambda query, viewer_age: query)
        monkeypatch.setattr(main, "get_follow_counts", lambda db, user_id: (8, 2))

        out = get_author_stats_service(author_id=author.id, request=_request(f"/api/authors/{author.id}/stats"), db=db)

        assert out["author_id"] == author.id
        assert out["novels"] == 2
        assert out["views"] == 15
        assert out["likes"] == 10
        assert out["favorites"] == 2
        assert out["followers"] == 8
        assert out["following"] == 2
    finally:
        db.close()


def test_get_author_dashboard_service_sorts_by_views(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")

        monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
        monkeypatch.setattr(main, "assert_premium_user", lambda user, message: None)
        monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")
        monkeypatch.setattr(
            author_dashboard_helpers,
            "_collect_author_dashboard_rows",
            lambda db, user_id, site_key: [
                {
                    "novel_id": 2,
                    "title": "B",
                    "view_count": 5,
                    "like_count": 1,
                    "favorite_count": 0,
                    "episode_count": 2,
                    "updated_at": None,
                },
                {
                    "novel_id": 1,
                    "title": "A",
                    "view_count": 10,
                    "like_count": 3,
                    "favorite_count": 4,
                    "episode_count": 1,
                    "updated_at": None,
                },
            ],
        )

        out = get_author_dashboard_service(request=_request("/api/author/dashboard"), db=db)

        assert out["summary"] == {
            "novel_count": 2,
            "total_views": 15,
            "total_likes": 4,
            "total_favorites": 4,
            "total_episodes": 3,
        }
        assert [row["novel_id"] for row in out["novels"]] == [1, 2]
    finally:
        db.close()


def test_login_service_returns_access_token(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")
        user.password_hash = "hashed"
        db.add(user)
        db.commit()

        monkeypatch.setattr(main, "get_user_by_username", lambda db, username: user)
        monkeypatch.setattr(main, "verify_password", lambda plain, hashed: plain == "secret" and hashed == "hashed")
        monkeypatch.setattr(main, "revalidate_premium_on_login", lambda user, db: None)
        monkeypatch.setattr(main, "cache_user_payload", lambda user: None)
        monkeypatch.setattr(main, "create_access_token", lambda data: f"token-for-{data['sub']}")

        out = login_service(payload=main.UserLogin(username="author", password="secret"), db=db)

        assert out.access_token == f"token-for-{user.id}"
    finally:
        db.close()


def test_password_reset_confirm_service_updates_password_and_consumes_token(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")
        user.password_hash = "old-hash"
        db.add(user)
        db.commit()

        raw_token = "reset-token"
        reset = models.PasswordResetToken(
            user_id=user.id,
            email="author@example.com",
            token_hash="hashed-token",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            consumed=False,
        )
        db.add(reset)
        db.commit()

        monkeypatch.setattr(main, "_hash_reset_token", lambda token: "hashed-token" if token == raw_token else "other")
        monkeypatch.setattr(main, "hash_password", lambda password: f"hashed:{password}")

        out = password_reset_confirm_service(
            payload=main.PasswordResetConfirm(token=raw_token, new_password="new-secret"),
            db=db,
        )

        db.refresh(user)
        db.refresh(reset)
        assert out == {"ok": True}
        assert user.password_hash == "hashed:new-secret"
        assert reset.consumed is True
    finally:
        db.close()


def test_create_support_plan_service_creates_default_name(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")
        monkeypatch.setattr(main, "require_current_user", lambda request, db: user)

        payload = main.SupportPlanCreate(name="", amount_yen=500, stripe_price_id="price_123")
        out = create_support_plan_service(payload=payload, request=_request("/api/authors/me/support_plans"), db=db)

        assert out.author_user_id == user.id
        assert out.amount_yen == 500
        assert out.name == "月額500円"
        assert out.stripe_price_id == "price_123"
    finally:
        db.close()


def test_get_author_balance_service_uses_profile_and_next_month(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")
        monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
        monkeypatch.setattr(main, "get_or_create_author_balance", lambda db, user_id: SimpleNamespace(available_yen=1200, pending_yen=3400))
        monkeypatch.setattr(
            main,
            "get_or_create_payout_profile",
            lambda db, user_id: SimpleNamespace(payout_minimum_yen=2500, payout_enabled=True),
        )

        out = get_author_balance_service(request=_request("/api/authors/me/balance"), db=db)

        assert out["available_yen"] == 1200
        assert out["pending_yen"] == 3400
        assert out["payout_minimum_yen"] == 3000
        assert out["payout_enabled"] is True
        assert out["next_payout_date"].day == 1
    finally:
        db.close()


def test_stripe_checkout_service_returns_checkout_url(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "premium-user")
        monkeypatch.setattr(main, "STRIPE_SECRET_KEY", "sk_test")
        monkeypatch.setattr(main, "STRIPE_PRICE_ID", "price_premium")
        monkeypatch.setattr(main, "FRONTEND_ORIGIN", "https://example.com")
        monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
        monkeypatch.setattr(
            main,
            "_create_checkout_session_with_customer_fallback",
            lambda db, user, **kwargs: SimpleNamespace(url="https://checkout.example/session"),
        )

        out = stripe_checkout_service(request=_request("/api/stripe/create-checkout-session"), db=db)

        assert out == {"url": "https://checkout.example/session"}
    finally:
        db.close()


def test_stripe_webhook_service_marks_support_paid(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        supporter = _make_user(db, "supporter")
        notifications = []
        emails = []
        balance_deltas = []

        monkeypatch.setattr(main, "STRIPE_WEBHOOK_SECRET", "whsec_test")
        monkeypatch.setattr(
            main.stripe.Webhook,
            "construct_event",
            lambda payload, sig_header, secret: {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_support_123",
                        "payment_intent": "pi_support_123",
                        "amount_total": 1200,
                        "metadata": {
                            "type": "support",
                            "author_user_id": str(author.id),
                            "supporter_user_id": str(supporter.id),
                            "novel_id": "77",
                        },
                    }
                },
            },
        )
        monkeypatch.setattr(main, "calc_author_share", lambda amount: (200, 1000))
        monkeypatch.setattr(
            main,
            "apply_author_balance_delta",
            lambda db, user_id, delta_available: balance_deltas.append((user_id, delta_available)),
        )
        monkeypatch.setattr(notification_helpers, "create_notification", lambda db, **kwargs: notifications.append(kwargs))
        monkeypatch.setattr(
            notification_helpers,
            "send_notification_email_if_enabled",
            lambda db, **kwargs: emails.append(kwargs),
        )

        class _WebhookRequest:
            async def body(self):
                return b'{"id":"evt_test"}'

        out = asyncio.run(
            stripe_webhook_service(
                request=_WebhookRequest(),
                stripe_signature="sig_test",
                db=db,
            )
        )

        support = db.query(models.Support).filter(models.Support.stripe_checkout_session_id == "cs_support_123").first()
        assert out == {"ok": True}
        assert support is not None
        assert support.status == "paid"
        assert support.amount_yen == 1200
        assert support.author_user_id == author.id
        assert support.supporter_user_id == supporter.id
        assert balance_deltas == [(author.id, 1000)]
        assert notifications[0]["notif_type"] == "support_paid"
        assert notifications[0]["user_id"] == author.id
        assert emails[0]["user_id"] == author.id
    finally:
        db.close()


def test_admin_supports_timeline_service_groups_paid_supports(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        supporter = _make_user(db, "supporter")
        paid_at = datetime.utcnow()
        db.add(
            models.Support(
                supporter_user_id=supporter.id,
                author_user_id=author.id,
                amount_yen=1500,
                platform_fee_yen=300,
                author_share_yen=1200,
                status="paid",
                stripe_checkout_session_id="cs_support_timeline",
                paid_at=paid_at,
            )
        )
        db.commit()

        monkeypatch.setattr(main, "require_admin", lambda request: None)

        out = admin_supports_timeline_service(
            request=_request("/api/admin/supports/timeline"),
            db=db,
            days=7,
            limit=5,
            by="author",
        )

        assert out["by"] == "author"
        assert out["days"] == 7
        assert len(out["users"]) == 1
        assert out["users"][0]["user_id"] == author.id
        assert out["users"][0]["username"] == "author"
        assert out["users"][0]["total_amount_yen"] == 1500
        assert out["users"][0]["total_count"] == 1
    finally:
        db.close()


def test_mark_payout_failed_service_restores_balance_and_note(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        payout = models.Payout(
            author_user_id=author.id,
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
            amount_yen=4200,
            status="scheduled",
        )
        db.add(payout)
        db.commit()
        db.refresh(payout)

        restored = []
        monkeypatch.setattr(main, "require_admin", lambda request: None)
        monkeypatch.setattr(
            main,
            "apply_author_balance_delta",
            lambda db, user_id, delta_available: restored.append((user_id, delta_available)),
        )

        out = mark_payout_failed_service(
            payout_id=payout.id,
            req=main.PayoutMarkRequest(note="bank error"),
            request=_request(f"/api/admin/payouts/{payout.id}/mark_failed"),
            db=db,
        )

        db.refresh(payout)
        assert out == {"ok": True}
        assert payout.status == "failed"
        assert payout.note == "bank error"
        assert restored == [(author.id, 4200)]
    finally:
        db.close()


def test_admin_login_service_issues_cookie(monkeypatch):
    cookies = []
    monkeypatch.setattr(main, "ADMIN_USERNAME", "admin")
    monkeypatch.setattr(main, "ADMIN_PASSWORD_HASH", "hashed")
    monkeypatch.setattr(main, "_enforce_admin_login_rate_limit", lambda request, username, response: "rl:key")
    monkeypatch.setattr(main, "_record_admin_login_failure", lambda key: None)
    monkeypatch.setattr(main, "_clear_admin_login_rate_limit_state", lambda key: None)
    monkeypatch.setattr(main, "create_admin_token", lambda username: f"token:{username}")
    monkeypatch.setattr(main, "_set_admin_cookie", lambda response, token: cookies.append(token))
    monkeypatch.setattr(
        main,
        "admin_pwd_context",
        SimpleNamespace(verify=lambda raw_password, password_hash: raw_password == "secret" and password_hash == "hashed"),
    )

    out = admin_login_service(
        payload=main.AdminLoginRequest(username="admin", password="secret"),
        request=_request("/api/admin/auth/login"),
        response=SimpleNamespace(),
    )

    assert out == {"ok": True}
    assert cookies == ["token:admin"]


def test_admin_list_users_service_returns_novel_counts(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        reader = _make_user(db, "reader", is_premium=False)
        _make_novel(db, author.id, title="n1")
        _make_novel(db, author.id, title="n2")

        monkeypatch.setattr(main, "require_admin", lambda request: None)
        monkeypatch.setattr(main, "is_effective_premium_user", lambda user: bool(getattr(user, "is_premium", False)))

        out = admin_list_users_service(
            request=_request("/api/admin/users"),
            limit=10,
            offset=0,
            db=db,
        )

        by_name = {user.username: user for user in out.users}
        assert out.total_users == 2
        assert by_name["author"].novel_count == 2
        assert by_name["author"].is_premium is True
        assert by_name["reader"].novel_count == 0
        assert by_name["reader"].is_premium is False
    finally:
        db.close()


def test_admin_delete_user_service_removes_user_and_owned_novels(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        author_id = author.id
        _make_novel(db, author_id, title="owned")
        plan = models.SupportPlan(author_user_id=author.id, name="plan", amount_yen=500, stripe_price_id="price_1")
        db.add(plan)
        db.commit()
        db.refresh(plan)
        db.add(
            models.Membership(
                author_user_id=author_id,
                supporter_user_id=author_id,
                plan_id=plan.id,
                stripe_subscription_id="sub_membership",
            )
        )
        db.commit()

        cancelled = []
        monkeypatch.setattr(main, "require_admin", lambda request: None)
        monkeypatch.setattr(main, "cancel_stripe_subscription_for_admin_delete", lambda subscription_id: cancelled.append(subscription_id) or True)

        out = admin_delete_user_service(
            user_id=author.id,
            request=_request(f"/api/admin/users/{author.id}"),
            db=db,
        )

        assert out.ok is True
        assert out.user_id == author_id
        assert cancelled == ["sub_membership"]
        assert db.query(models.User).filter(models.User.id == author_id).first() is None
        assert db.query(models.Novel).filter(models.Novel.author_id == author_id).count() == 0
    finally:
        db.close()


def test_admin_get_ai_logs_service_returns_latest_logs(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")
        older = models.AIGenerateLog(
            user_id=user.id,
            prompt_summary="old",
            tokens_used=10,
            model="m1",
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
        newer = models.AIGenerateLog(
            user_id=user.id,
            prompt_summary="new",
            tokens_used=20,
            model="m2",
            created_at=datetime.utcnow(),
        )
        db.add_all([older, newer])
        db.commit()

        monkeypatch.setattr(main, "require_admin", lambda request: None)

        out = admin_get_ai_logs_service(
            request=_request("/api/admin/ai/logs"),
            limit=10,
            db=db,
        )

        assert [item["prompt_summary"] for item in out] == ["new", "old"]
        assert out[0]["username"] == "author"
        assert out[0]["tokens_used"] == 20
    finally:
        db.close()


def test_admin_start_i18n_job_service_starts_background_job(monkeypatch):
    created_jobs = []
    thread_calls = []

    class _Thread:
        def __init__(self, *, target=None, kwargs=None, name=None, daemon=None):
            thread_calls.append(
                {
                    "target": target,
                    "kwargs": kwargs or {},
                    "name": name,
                    "daemon": daemon,
                }
            )

        def start(self):
            return None

    monkeypatch.setattr(main, "require_admin", lambda request: None)
    monkeypatch.setattr(main, "_create_ui_i18n_job_row", lambda job, source_items: created_jobs.append((job, source_items)))
    monkeypatch.setattr(main, "_run_ui_i18n_background_job", lambda **kwargs: None)
    monkeypatch.setattr(main, "_normalize_ui_i18n_source_items", lambda raw_items: [("ja", "hello"), ("en", "world")])
    monkeypatch.setattr(main, "normalize_language", lambda value: str(value).lower())
    monkeypatch.setattr(main, "_UI_I18N_JOBS", {})
    monkeypatch.setattr(main, "_UI_I18N_JOB_ORDER", [])
    monkeypatch.setattr(main, "_UI_I18N_JOB_MAX_KEEP", 10)
    monkeypatch.setattr("app.services.admin_i18n_service.secrets.token_hex", lambda n: "job1234567890abcd")
    monkeypatch.setattr("app.services.admin_i18n_service.threading.Thread", _Thread)

    payload = main.AdminUiI18nJobStartRequest(
        source_items=[main.AdminUiI18nSourceItem(source_lang="ja", text="hello")],
        target_langs=["zh-cn", "ko"],
        batch_size=7,
        notify_username="admin",
    )
    out = admin_start_i18n_job_service(
        payload=payload,
        request=_request("/api/admin/i18n/jobs/start"),
        db=None,
    )

    assert out == {"job_id": "job1234567890abcd", "status": "pending"}
    assert created_jobs[0][0]["source_item_count"] == 2
    assert created_jobs[0][0]["target_langs"] == ["zh-cn", "ko"]
    assert thread_calls[0]["kwargs"]["job_id"] == "job1234567890abcd"
    assert "job1234567890abcd" in main._UI_I18N_JOBS


def test_admin_i18n_job_status_and_cancel_services(monkeypatch):
    monkeypatch.setattr(main, "require_admin", lambda request: None)
    monkeypatch.setattr(main, "_ui_i18n_job_snapshot", lambda job_id: {"job_id": job_id, "status": "running"})

    updates = []
    monkeypatch.setattr(main, "_set_ui_i18n_job", lambda job_id, **updates_map: updates.append((job_id, updates_map)))

    status_out = admin_i18n_job_status_service(
        job_id="job1",
        request=_request("/api/admin/i18n/jobs/job1"),
    )
    cancel_out = admin_cancel_i18n_job_service(
        job_id="job1",
        request=_request("/api/admin/i18n/jobs/job1/cancel"),
    )

    assert status_out == {"job_id": "job1", "status": "running"}
    assert cancel_out == {"ok": True}
    assert updates == [("job1", {"cancel_requested": True})]


def test_admin_list_i18n_jobs_service_uses_legacy_listing(monkeypatch):
    monkeypatch.setattr(main, "require_admin", lambda request: None)
    monkeypatch.setattr(main, "_ui_i18n_list_jobs", lambda limit: [{"job_id": "job1", "limit": limit}])

    out = admin_list_i18n_jobs_service(
        request=_request("/api/admin/i18n/jobs"),
        limit=12,
    )

    assert out == [{"job_id": "job1", "limit": 12}]


def test_admin_retranslate_remaining_i18n_service_dry_run(monkeypatch):
    db = _make_session()
    try:
        row1 = models.UII18nDictionary(
            target_lang="zh-cn",
            source_text="こんにちは",
            translated_text="こんにちは",
        )
        row2 = models.UII18nDictionary(
            target_lang="ko",
            source_text="さようなら",
            translated_text="さようなら",
        )
        db.add_all([row1, row2])
        db.commit()

        monkeypatch.setattr(main, "require_admin", lambda request: None)
        monkeypatch.setattr(main, "normalize_language", lambda value: str(value).lower())

        payload = main.AdminUiI18nRetranslateRemainingRequest(
            target_langs=["zh-cn", "ko"],
            dry_run=True,
            include_same_as_source=True,
            include_kana=False,
        )
        out = admin_retranslate_remaining_i18n_service(
            payload=payload,
            request=_request("/api/admin/i18n/retranslate_remaining"),
            db=db,
        )

        assert out["ok"] is True
        assert out["matched"] == 2
        assert out["dry_run"] is True
        assert out["per_lang"] == {"zh-cn": 1, "ko": 1}
    finally:
        db.close()


def test_admin_delete_board_post_service_deletes_replies(monkeypatch):
    db = _make_session()
    try:
        parent = models.BoardPost(title="parent", body="body", site_key="main")
        db.add(parent)
        db.commit()
        db.refresh(parent)
        reply = models.BoardPost(title="reply", body="body", site_key="main", parent_post_id=parent.id)
        db.add(reply)
        db.commit()

        monkeypatch.setattr(main, "require_admin", lambda request: None)
        monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")

        out = admin_delete_board_post_service(
            post_id=parent.id,
            request=_request("/api/admin/board/posts/1"),
            db=db,
        )

        assert out == {"ok": True}
        assert db.query(models.BoardPost).count() == 0
    finally:
        db.close()


def test_admin_backfill_translations_service_processes_novel_and_episode(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        novel = _make_novel(db, author.id, language="ja", status="public")
        episode = _make_episode(db, novel.id, language="ja", status="public")

        monkeypatch.setattr(main, "require_admin", lambda request: None)
        monkeypatch.setattr(main, "translation_target_languages", lambda source: ["en"])
        monkeypatch.setattr(main, "get_novel_tag_names", lambda db, novel_id: ["tag1"])
        monkeypatch.setattr(main, "normalize_language", lambda value: (value or "ja"))
        monkeypatch.setattr(main, "_is_episode_translation_complete", lambda db, episode, source_language: False)

        created_novel_translations = []
        created_episode_translations = []

        def _upsert_novel_translation(db, *, novel, source_language, tag_names):
            created_novel_translations.append((novel.id, source_language, tuple(tag_names)))
            db.add(models.NovelTranslation(novel_id=novel.id, language="en", title="t", description="d"))

        def _upsert_episode_translation(db, *, episode, source_language):
            created_episode_translations.append((episode.id, source_language))

        episode_completion = {"count": 0}

        def _episode_complete(db, episode, source_language):
            episode_completion["count"] += 1
            return episode_completion["count"] > 1

        monkeypatch.setattr(main, "upsert_novel_translation", _upsert_novel_translation)
        monkeypatch.setattr(main, "upsert_episode_translation", _upsert_episode_translation)
        monkeypatch.setattr(main, "_is_episode_translation_complete", _episode_complete)

        out = admin_backfill_translations_service(
            request=_request("/api/admin/translations/backfill"),
            payload={"max_novels": 1, "max_episodes": 1},
            db=db,
        )

        assert out["novels_translated"] == 1
        assert out["episodes_translated"] == 1
        assert out["novels_failed"] == 0
        assert out["episodes_failed"] == 0
        assert created_novel_translations == [(novel.id, "ja", ("tag1",))]
        assert created_episode_translations == [(episode.id, "ja")]
    finally:
        db.close()


def test_admin_indexing_urls_service_returns_scored_items(monkeypatch):
    monkeypatch.setattr(main, "require_admin", lambda request: None)
    monkeypatch.setattr(main, "_get_indexing_carryover_payload", lambda: {"urls": ["https://example.com/a"], "updated_at": "ts"})
    monkeypatch.setattr(
        main,
        "_build_indexing_target_items",
        lambda db, request: [
            {"url": "https://example.com/a", "page_type": "novel", "view_count": 11, "lastmod": None},
            {"url": "https://example.com/b", "page_type": "episode", "view_count": 5, "lastmod": None},
        ],
    )
    monkeypatch.setattr(main, "_indexing_importance_weight", lambda page_type: 1.5 if page_type == "novel" else 1.0)
    monkeypatch.setattr(main, "_calc_indexing_priority_score", lambda page_type, view_count, lastmod: view_count + 10)

    out = admin_indexing_urls_service(
        request=_request("/api/admin/indexing/urls"),
        limit=1,
        inspect=False,
        db=None,
    )

    assert out.total == 2
    assert out.urls == ["https://example.com/a"]
    assert out.carryover_count == 1
    assert out.items[0].url == "https://example.com/a"
    assert out.items[0].score == 21


def test_admin_indexing_submit_service_handles_quota_carryover(monkeypatch):
    monkeypatch.setattr(main, "require_admin", lambda request: None)
    monkeypatch.setattr(main, "_get_indexing_carryover_payload", lambda: {"urls": [], "updated_at": None})
    monkeypatch.setattr(main, "_merge_indexing_urls_prioritize_carryover", lambda queued, target: (target, []))
    monkeypatch.setattr(main, "_filter_frontend_origin_urls", lambda urls: (urls, []))
    monkeypatch.setattr(main, "GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT", 10)
    monkeypatch.setattr(google_indexing_helpers, "_build_google_indexing_access_token", lambda: "token")
    monkeypatch.setattr(
        google_indexing_helpers,
        "_should_retry_google_indexing_publish",
        lambda status_code, error: False,
    )
    monkeypatch.setattr(main, "_set_indexing_carryover_urls", lambda urls: setattr(test_admin_indexing_submit_service_handles_quota_carryover, "carryover", list(urls)))
    monkeypatch.setattr(
        google_indexing_helpers,
        "_publish_google_indexing_url",
        lambda url, access_token: (False, 429, "quota") if url.endswith("/a") else (True, 200, None),
    )
    monkeypatch.setattr(
        main,
        "_dedupe_urls_keep_order",
        lambda urls: list(dict.fromkeys(urls)),
    )
    monkeypatch.setattr(
        main,
        "_get_indexing_carryover_payload",
        lambda: {
            "urls": getattr(test_admin_indexing_submit_service_handles_quota_carryover, "carryover", []),
            "updated_at": "updated",
        },
    )

    payload = main.AdminIndexingSubmitRequest(urls=["https://example.com/a", "https://example.com/b"], all_pages=False)
    out = admin_indexing_submit_service(
        payload=payload,
        request=_request("/api/admin/indexing/submit"),
        db=None,
    )

    assert out.submitted == 2
    assert out.failed == 1
    assert out.attempted == 1
    assert out.carryover_urls == ["https://example.com/a", "https://example.com/b"]


def test_admin_indexing_carryover_services(monkeypatch):
    monkeypatch.setattr(main, "require_admin", lambda request: None)
    monkeypatch.setattr(main, "_get_indexing_carryover_payload", lambda: {"urls": ["u1", "u2"], "updated_at": "now"})
    out = admin_indexing_carryover_service(request=_request("/api/admin/indexing/carryover"))
    assert out.carryover_count == 2
    assert out.carryover_urls == ["u1", "u2"]

    cleared = []
    monkeypatch.setattr(main, "_clear_indexing_carryover_urls", lambda: cleared.append(True))
    out2 = admin_indexing_carryover_clear_service(request=_request("/api/admin/indexing/carryover"))
    assert out2.carryover_count == 0
    assert cleared == [True]


def test_admin_indexnow_submit_service_returns_success(monkeypatch):
    monkeypatch.setattr(main, "require_admin", lambda request: None)
    monkeypatch.setattr(main, "INDEXNOW_ENABLED", True)
    monkeypatch.setattr(main, "INDEXNOW_KEY", "key123")
    monkeypatch.setattr(main, "INDEXNOW_ENDPOINT", "https://indexnow.example/submit")
    monkeypatch.setattr(main, "_dedupe_urls_keep_order", lambda urls: urls)
    monkeypatch.setattr(main, "_is_frontend_origin_url", lambda url: True)
    monkeypatch.setattr(main, "_indexnow_host_from_request", lambda request: "example.com")
    monkeypatch.setattr(main, "_indexnow_key_location", lambda request: "https://example.com/key123.txt")

    class _Resp:
        status_code = 200
        text = ""

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, endpoint, json, headers):
            return _Resp()

    monkeypatch.setattr("app.services.admin_indexing_service.httpx.Client", lambda timeout=20.0: _Client())

    payload = main.AdminIndexNowSubmitRequest(urls=["https://example.com/a"], event="urlUpdated")
    out = admin_indexnow_submit_service(
        payload=payload,
        request=_request("/api/admin/indexnow/submit"),
    )

    assert out.submitted == 1
    assert out.success == 1
    assert out.failed == 0
    assert out.host == "example.com"


def test_public_create_contact_message_service_records_guest_message(monkeypatch):
    db = _make_session()
    try:
        monkeypatch.setattr(main, "get_optional_current_user", lambda request, db: None)
        monkeypatch.setattr(main, "verify_recaptcha_token", lambda token, remote_ip, expected_action: True)
        monkeypatch.setattr(main, "_public_contact_remote_ip", lambda request: "127.0.0.1")
        monkeypatch.setattr(main, "_enforce_public_contact_abuse_guards", lambda request, subject, body: None)
        emails = []
        monkeypatch.setattr(notification_helpers, "send_public_contact_email", lambda subject, body: emails.append((subject, body)))
        recorded = []
        monkeypatch.setattr(main, "_record_public_contact_submission", lambda remote_ip, subject, body: recorded.append((remote_ip, subject, body)))

        payload = main.PublicContactRequest(
            subject="hello",
            body="world",
            name="guest",
            email="guest@example.com",
            recaptcha_token="tok",
        )
        out = public_create_contact_message_service(
            request=_request("/api/contact/messages"),
            payload=payload,
            db=db,
        )

        assert out.subject == "hello"
        assert "Name: guest" in out.body
        assert emails[0][0] == "hello"
        assert recorded == [("127.0.0.1", "hello", "world")]
    finally:
        db.close()


def test_get_my_ai_logs_service_returns_user_logs(monkeypatch):
    db = _make_session()
    try:
        user = _make_user(db, "author")
        other = _make_user(db, "other")
        db.add_all(
            [
                models.AIGenerateLog(user_id=user.id, prompt_summary="mine", tokens_used=12, model="m1"),
                models.AIGenerateLog(user_id=other.id, prompt_summary="other", tokens_used=99, model="m2"),
            ]
        )
        db.commit()

        monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
        out = get_my_ai_logs_service(
            request=_request("/api/ai/logs/me"),
            db=db,
            limit=10,
        )

        assert len(out) == 1
        assert out[0]["prompt_summary"] == "mine"
        assert out[0]["tokens_used"] == 12
    finally:
        db.close()


def test_list_series_overview_service_aggregates_series(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        _make_novel(db, author.id, title="n1", series_name="Saga", is_public=True)
        _make_novel(db, author.id, title="n2", series_name="Saga", is_public=True)
        _make_novel(db, author.id, title="n3", series_name="Solo", is_public=True)

        monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")
        monkeypatch.setattr(main, "_resolve_public_viewer_age", lambda request, db: (None, None))
        monkeypatch.setattr(main, "_apply_public_novel_age_filter", lambda query, viewer_age: query)

        out = list_series_overview_service(
            request=_request("/api/series"),
            db=db,
            q=None,
            limit=10,
        )

        assert out[0]["series_name"] == "Saga"
        assert out[0]["novel_count"] == 2
        assert any(item["series_name"] == "Solo" for item in out)
    finally:
        db.close()


def test_list_trending_tags_service_returns_scored_tags(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        novel = _make_novel(db, author.id, title="n1", is_public=True)
        tag = models.Tag(name="battle")
        db.add(tag)
        db.commit()
        db.refresh(tag)
        db.add(models.NovelTag(novel_id=novel.id, tag_id=tag.id))
        db.add(
            models.NovelDailyMetric(
                novel_id=novel.id,
                date=date.today(),
                view_count=10,
                like_count=2,
                favorite_count=1,
            )
        )
        db.commit()

        monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")
        monkeypatch.setattr(main, "_resolve_public_viewer_age", lambda request, db: (None, None))
        monkeypatch.setattr(main, "_apply_public_novel_age_filter", lambda query, viewer_age: query)

        out = list_trending_tags_service(
            request=_request("/api/trending-tags"),
            db=db,
            days=7,
            limit=10,
        )

        assert out[0]["name"] == "battle"
        assert out[0]["trend_score"] == 21
        assert out[0]["novel_count"] == 1
    finally:
        db.close()


def test_sitemap_tags_excludes_episode_only_tags(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        novel = _make_novel(db, author.id, title="novel", is_public=True, status="public")
        episode = _make_episode(db, novel.id, title="ep", body="body", is_public=True, status="public")

        novel_tag = models.Tag(name="novel-tag")
        episode_only_tag = models.Tag(name="episode-only-tag")
        db.add_all([novel_tag, episode_only_tag])
        db.commit()
        db.refresh(novel_tag)
        db.refresh(episode_only_tag)

        db.add(models.NovelTag(novel_id=novel.id, tag_id=novel_tag.id))
        db.add(models.EpisodeTag(episode_id=episode.id, tag_id=episode_only_tag.id))
        db.commit()

        monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")
        monkeypatch.setattr(main, "_request_origin", lambda request, fallback: "https://example.com")

        response = sitemap_tags_xml_service(request=_request("/sitemap-tags.xml"), db=db)
        body = response.body.decode("utf-8")

        assert "https://example.com/tags/novel-tag" in body
        assert "episode-only-tag" not in body
    finally:
        db.close()


def test_share_episode_page_is_noindex(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        novel = _make_novel(db, author.id, title="novel", description="desc", is_public=True, status="public")
        episode = _make_episode(db, novel.id, title="ep", body="episode body", is_public=True, status="public")

        monkeypatch.setattr(main, "get_episode_in_site_or_404", lambda db, request, episode_id: episode)
        monkeypatch.setattr(main, "is_episode_draft", lambda ep: False)
        monkeypatch.setattr(main, "get_novel_in_site_or_404", lambda db, request, novel_id: novel)
        monkeypatch.setattr(main, "get_episode_number", lambda ep: 1)
        monkeypatch.setattr(main, "PIL_AVAILABLE", False)

        request = SimpleNamespace(
            headers={"host": "example.com", "x-forwarded-proto": "https"},
            url=SimpleNamespace(scheme="https", netloc="example.com"),
        )

        response = share_episode_page_service(episode_id=episode.id, request=request, db=db)
        body = response.body.decode("utf-8")

        assert response.headers["x-robots-tag"] == "noindex, nofollow"
        assert '<meta name="robots" content="noindex,nofollow" />' in body
        assert '<meta name="googlebot" content="noindex,nofollow" />' in body
    finally:
        db.close()


def test_resolve_public_novel_card_translations_uses_partial_title_translation(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        novel = _make_novel(
            db,
            author.id,
            title="狂三の甘い誘惑と影の戯れ",
            description="元の説明",
            is_public=True,
            status="public",
            language="ja",
        )
        db.add(
            models.NovelTranslation(
                novel_id=novel.id,
                language="en",
                title="Kurumi's Sweet Temptation and Shadow Play",
                description="",
                tag_names=None,
            )
        )
        db.commit()

        monkeypatch.setattr(main, "translation_target_languages", lambda source_language: ["en"])
        monkeypatch.setattr(main, "_can_translate_novel", lambda db, novel: True)
        monkeypatch.setattr(main, "_should_enqueue_feed_novel_translation", lambda novel_id, lang: False)

        out = main._resolve_public_novel_card_translations(
            db,
            novels=[novel],
            target_language="en",
            background_tasks=BackgroundTasks(),
        )

        assert out[novel.id]["title"] == "Kurumi's Sweet Temptation and Shadow Play"
        assert out[novel.id]["description"] == "元の説明"
    finally:
        db.close()


def test_list_trending_feed_uses_translated_title_when_lang_requested(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        novel = _make_novel(
            db,
            author.id,
            title="影の戯れ",
            description="説明",
            is_public=True,
            status="public",
            language="ja",
        )
        db.add(
            models.NovelTranslation(
                novel_id=novel.id,
                language="en",
                title="Shadow Play",
                description="Description",
                tag_names=None,
            )
        )
        db.add(
            models.NovelDailyMetric(
                novel_id=novel.id,
                date=date.today(),
                view_count=50,
                like_count=4,
                favorite_count=2,
            )
        )
        db.commit()

        monkeypatch.setattr(main, "get_optional_current_user_soft", lambda request, db: None)
        monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")
        monkeypatch.setattr(main, "calc_age", lambda birth_date: None)
        monkeypatch.setattr(main, "_apply_public_novel_age_filter", lambda query, user_age: query)
        monkeypatch.setattr(main, "_build_public_cover_map", lambda db, novel_ids, site_key: {})
        monkeypatch.setattr(main, "_build_public_latest_episode_activity_map", lambda db, novel_ids, site_key: {})
        monkeypatch.setattr(main, "_build_public_comment_count_map", lambda db, novel_ids, site_key: {})
        monkeypatch.setattr(main, "get_novel_char_counts", lambda db, novel_ids, public_only=True: {novel.id: 0})
        monkeypatch.setattr(main, "translation_target_languages", lambda source_language: ["en"])
        monkeypatch.setattr(main, "_can_translate_novel", lambda db, novel: True)
        monkeypatch.setattr(main, "_should_enqueue_feed_novel_translation", lambda novel_id, lang: False)

        out = main.list_trending_feed(
            request=_request("/api/feed/trending"),
            background_tasks=BackgroundTasks(),
            db=db,
            limit=8,
            lang="en",
        )

        assert out[0]["title"] == "Shadow Play"
        assert out[0]["description"] == "Description"
    finally:
        db.close()


def test_me_and_profile_routes_are_registered():
    paths = {route.path for route in main.app.routes}

    assert "/api/me/favorites" in paths
    assert "/api/me/ai/chat/favorites" in paths
    assert "/api/me/view-history/novels" in paths
    assert "/api/me/analytics/novels" in paths
    assert "/api/users/me" in paths
    assert "/api/admin/auth/login" in paths
    assert "/api/admin/users" in paths
    assert "/api/admin/ai/logs" in paths
    assert "/api/admin/i18n/jobs/start" in paths
    assert "/api/admin/translations/backfill" in paths
    assert "/api/admin/board/posts/{post_id}" in paths
    assert "/api/admin/indexing/urls" in paths
    assert "/api/admin/indexnow/submit" in paths
    assert "/api/contact/messages" in paths
    assert "/api/ai/logs/me" in paths
    assert "/api/series" in paths
    assert "/api/trending-tags" in paths


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
