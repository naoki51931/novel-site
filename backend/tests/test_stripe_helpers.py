import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.stripe_helpers import _run_monthly_stripe_premium_sync_once


class FakeQuery:
    def __init__(self, users):
        self.users = users

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.users)


class FakeSession:
    def __init__(self, users):
        self.users = users
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def query(self, model):
        return FakeQuery(self.users)

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class UserModel:
    email = SimpleNamespace(isnot=lambda value: True)


class Models:
    User = UserModel


class Logger:
    def warning(self, *args, **kwargs):
        raise AssertionError(f"unexpected warning: {args}")


def run_sync(users, finder):
    session = FakeSession(users)
    stats = _run_monthly_stripe_premium_sync_once(
        stripe_secret_key="sk_test",
        session_local=lambda: session,
        models=Models,
        find_active_monthly_subscription_by_email=finder,
        is_ai_chat_demo_bypass_user=lambda user: False,
        is_force_premium_username=lambda username: False,
        logger=Logger(),
    )
    return stats, session


def test_stripe_premium_sync_removes_premium_without_active_subscription():
    user = SimpleNamespace(
        id=1,
        username="alice",
        email="alice@example.com",
        is_premium=True,
        premium_checked_at=None,
        stripe_customer_id=None,
        stripe_subscription_id=None,
    )

    stats, session = run_sync([user], lambda email: (None, None))

    assert user.is_premium is False
    assert user.premium_checked_at is not None
    assert stats["checked_users"] == 1
    assert stats["premium_removed_users"] == 1
    assert stats["premium_applied_users"] == 0
    assert session.commits == 1
    assert session.closed is True


def test_stripe_premium_sync_applies_active_subscription():
    user = SimpleNamespace(
        id=2,
        username="bob",
        email="bob@example.com",
        is_premium=False,
        premium_checked_at=None,
        stripe_customer_id=None,
        stripe_subscription_id=None,
    )

    stats, session = run_sync([user], lambda email: ("cus_123", "sub_123"))

    assert user.is_premium is True
    assert user.stripe_customer_id == "cus_123"
    assert user.stripe_subscription_id == "sub_123"
    assert user.premium_checked_at is not None
    assert stats["checked_users"] == 1
    assert stats["premium_applied_users"] == 1
    assert stats["premium_removed_users"] == 0
    assert session.commits == 1


def test_stripe_premium_sync_skips_manual_premium_markers():
    user = SimpleNamespace(
        id=3,
        username="manual",
        email="manual@example.com",
        is_premium=True,
        premium_checked_at=None,
        stripe_customer_id=None,
        stripe_subscription_id="manual_premium_3000",
    )

    stats, session = run_sync([user], lambda email: (_ for _ in ()).throw(AssertionError("should not call stripe")))

    assert user.is_premium is True
    assert user.premium_checked_at is None
    assert stats["checked_users"] == 0
    assert stats["premium_removed_users"] == 0
    assert session.commits == 0
