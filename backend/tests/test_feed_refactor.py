import sys
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main, models
from app.features import feed_service


def _request(path: str = "/api/feed/following"):
    return SimpleNamespace(url=SimpleNamespace(path=path), headers={})


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _make_user(db, username: str):
    user = models.User(username=username, password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_novel(db, author_id: int):
    novel = models.Novel(
        title="novel",
        description="desc",
        author_id=author_id,
        site_key="main",
        is_public=True,
    )
    db.add(novel)
    db.commit()
    db.refresh(novel)
    return novel


def test_feed_routes_are_mounted_via_router():
    route = next(
        r
        for r in main.app.routes
        if getattr(r, "path", None) == "/api/feed/new" and "GET" in getattr(r, "methods", set())
    )
    assert route.endpoint.__module__ == "app.routers.feed"


def test_board_routes_are_mounted_via_router():
    route = next(
        r
        for r in main.app.routes
        if getattr(r, "path", None) == "/api/board/posts" and "GET" in getattr(r, "methods", set())
    )
    assert route.endpoint.__module__ == "app.routers.board"


def test_list_following_feed_service_returns_followed_novel(monkeypatch):
    db = _make_session()
    try:
        author = _make_user(db, "author")
        follower = _make_user(db, "reader")
        novel = _make_novel(db, author.id)
        db.add(
            models.UserFollow(
                follower_user_id=follower.id,
                followed_user_id=author.id,
            )
        )
        db.commit()

        monkeypatch.setattr(main, "require_current_user", lambda request, db: follower)
        monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")
        monkeypatch.setattr(main, "calc_age", lambda birth_date: None)
        monkeypatch.setattr(main, "_apply_public_novel_age_filter", lambda q, user_age: q)
        monkeypatch.setattr(main, "_build_public_cover_map", lambda db, novel_ids, site_key: {})
        monkeypatch.setattr(
            main,
            "_build_public_latest_episode_activity_map",
            lambda db, novel_ids, site_key: {},
        )
        monkeypatch.setattr(main, "_build_public_comment_count_map", lambda db, novel_ids, site_key: {})
        monkeypatch.setattr(main, "get_novel_char_counts", lambda db, novel_ids, public_only=False: {})
        monkeypatch.setattr(
            main,
            "_resolve_public_novel_card_translations",
            lambda db, novels, target_language=None, background_tasks=None: {},
        )

        out = feed_service.list_following_feed_service(request=_request(), db=db, limit=10)

        assert len(out) == 1
        assert out[0]["id"] == novel.id
        assert out[0]["author_username"] == author.username
    finally:
        db.close()
