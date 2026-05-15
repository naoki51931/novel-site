from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main, models
from app.cover_schemas import CoverGenerateRequest, NovelCoverAdoptRequest
from app.features import covers_routes


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_user(db, username: str, *, is_premium: bool = True):
    user = models.User(username=username, password_hash="x", is_premium=is_premium)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_novel(db, author_id: int):
    novel = models.Novel(
        title="t",
        description="d",
        author_id=author_id,
        site_key="main",
        is_public=True,
    )
    db.add(novel)
    db.commit()
    db.refresh(novel)
    return novel


def test_generate_cover_success(db_session, monkeypatch):
    user = _make_user(db_session, "u1")
    novel = _make_novel(db_session, user.id)

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")
    monkeypatch.setattr(
        covers_routes,
        "_cover_config",
        lambda: SimpleNamespace(
            api_key="k",
            model="gpt-image-1",
            size="1024x1536",
            quality="medium",
            output_format="jpeg",
            upload_dir="/tmp",
            public_base_url="https://example.com",
            timeout_seconds=1.0,
        ),
    )
    monkeypatch.setattr(
        covers_routes,
        "generate_cover_image",
        lambda prompt, config: {
            "image_path": "/uploads/covers/2026/03/sample.jpeg",
            "image_url": "https://example.com/uploads/covers/2026/03/sample.jpeg",
        },
    )

    out = covers_routes.generate_cover(
        payload=CoverGenerateRequest(novel_id=novel.id, title="a"),
        request=SimpleNamespace(headers={}),
        db=db_session,
    )
    assert out.status == "succeeded"
    assert out.image_path == "/uploads/covers/2026/03/sample.jpeg"


def test_generate_cover_failure_marks_failed(db_session, monkeypatch):
    user = _make_user(db_session, "u2")
    novel = _make_novel(db_session, user.id)

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")
    monkeypatch.setattr(
        covers_routes,
        "_cover_config",
        lambda: SimpleNamespace(
            api_key="k",
            model="gpt-image-1",
            size="1024x1536",
            quality="medium",
            output_format="jpeg",
            upload_dir="/tmp",
            public_base_url="https://example.com",
            timeout_seconds=1.0,
        ),
    )

    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(covers_routes, "generate_cover_image", _raise)

    with pytest.raises(Exception):
        covers_routes.generate_cover(
            payload=CoverGenerateRequest(novel_id=novel.id, title="a"),
            request=SimpleNamespace(headers={}),
            db=db_session,
        )
    row = db_session.query(models.CoverGeneration).order_by(models.CoverGeneration.id.desc()).first()
    assert row is not None
    assert row.status == "failed"


def test_set_novel_cover_permission(db_session, monkeypatch):
    owner = _make_user(db_session, "owner")
    other = _make_user(db_session, "other")
    novel = _make_novel(db_session, owner.id)
    db_session.add(
        models.CoverGeneration(
            user_id=other.id,
            novel_id=novel.id,
            prompt="p",
            model="gpt-image-1",
            status="succeeded",
            image_path="/uploads/covers/2026/03/other.jpeg",
        )
    )
    db_session.commit()

    monkeypatch.setattr(main, "require_current_user", lambda request, db: owner)
    monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")

    with pytest.raises(Exception):
        covers_routes.set_novel_cover(
            novel_id=novel.id,
            payload=NovelCoverAdoptRequest(image_path="/uploads/covers/2026/03/other.jpeg"),
            request=SimpleNamespace(headers={}),
            db=db_session,
        )
