import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas import ProfileRead
from app.schemas_api import AdminContactMessageOut, SupportPlanAuthorOut, SupportPlanOut


def test_profile_read_accepts_attribute_objects():
    user = SimpleNamespace(
        id=7,
        username="author",
        email="author@example.com",
        birth_date=date(1990, 4, 3),
        email_notifications_enabled=True,
        favorite_visibility="public",
        profile_bio="bio",
        profile_icon_url="https://example.com/icon.png",
        profile_header_url=None,
        profile_website_url="https://example.com",
        profile_x_url="https://x.com/author",
        ai_summary_model="gpt-test",
        ai_title_model=None,
        ai_tag_model=None,
        ai_story_agent_model=None,
        ai_comment_revision_model=None,
        ai_story_agent_visible=True,
    )

    out = ProfileRead.model_validate(user)

    assert out.id == 7
    assert out.username == "author"
    assert out.email == "author@example.com"
    assert out.birth_date == date(1990, 4, 3)
    assert out.profile_icon_url == "https://example.com/icon.png"


def test_support_plan_out_keeps_explicit_field_mapping():
    out = SupportPlanOut(
        id=3,
        author_user_id=9,
        name="monthly",
        price_yen=500,
        is_active=True,
    )

    assert out.id == 3
    assert out.author_user_id == 9
    assert out.price_yen == 500
    assert out.is_active is True


def test_support_plan_author_out_accepts_attribute_objects():
    plan = SimpleNamespace(
        id=4,
        author_user_id=12,
        name="supporter",
        amount_yen=1200,
        stripe_price_id="price_123",
        is_active=False,
    )

    out = SupportPlanAuthorOut.model_validate(plan)

    assert out.id == 4
    assert out.author_user_id == 12
    assert out.amount_yen == 1200
    assert out.stripe_price_id == "price_123"
    assert out.is_active is False


def test_admin_contact_message_out_accepts_attribute_objects():
    message = SimpleNamespace(
        id=5,
        admin_username="admin",
        subject="hello",
        body="world",
        created_at=datetime(2026, 5, 26, 12, 0, 0),
    )

    out = AdminContactMessageOut.model_validate(message)

    assert out.id == 5
    assert out.admin_username == "admin"
    assert out.subject == "hello"
    assert out.body == "world"
    assert out.created_at == datetime(2026, 5, 26, 12, 0, 0)
