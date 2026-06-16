#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
CONTAINER_APP_DIR = Path("/app")
for candidate in (BACKEND_DIR, CONTAINER_APP_DIR):
    if (candidate / "app").is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import stripe  # noqa: E402

from app import models  # noqa: E402
from app.cache_helpers import invalidate_user_cache  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.runtime_config import STRIPE_SECRET_KEY  # noqa: E402
from app.stripe_helpers import (  # noqa: E402
    _stripe_obj_get,
    is_manual_premium_subscription_id,
)
from app.time_utils import utcnow  # noqa: E402


ACTIVE_OR_BILLABLE_STATUSES = {
    "active",
    "trialing",
    "past_due",
    "unpaid",
    "incomplete",
}


def _subscription_status(subscription: Any) -> str:
    return str(_stripe_obj_get(subscription, "status") or "").strip().lower()


def _subscription_id(subscription: Any) -> str:
    return str(_stripe_obj_get(subscription, "id") or "").strip()


def _customer_id(subscription: Any) -> str | None:
    value = str(_stripe_obj_get(subscription, "customer") or "").strip()
    return value or None


def _find_stripe_subscriptions(email: str, existing_subscription_id: str | None) -> list[Any]:
    subscriptions: list[Any] = []
    seen: set[str] = set()

    sid = str(existing_subscription_id or "").strip()
    if sid and not is_manual_premium_subscription_id(sid):
        try:
            sub = stripe.Subscription.retrieve(sid)
            sub_id = _subscription_id(sub)
            if sub_id:
                subscriptions.append(sub)
                seen.add(sub_id)
        except Exception as exc:
            print(f"stripe subscription retrieve failed sid={sid}: {exc!r}", file=sys.stderr)

    customers = stripe.Customer.list(email=email, limit=10)
    for customer in _stripe_obj_get(customers, "data", []) or []:
        customer_email = str(_stripe_obj_get(customer, "email") or "").strip().lower()
        if customer_email and customer_email != email:
            continue
        customer_id = str(_stripe_obj_get(customer, "id") or "").strip()
        if not customer_id:
            continue
        rows = stripe.Subscription.list(customer=customer_id, status="all", limit=100)
        for sub in _stripe_obj_get(rows, "data", []) or []:
            sub_id = _subscription_id(sub)
            if sub_id and sub_id not in seen:
                subscriptions.append(sub)
                seen.add(sub_id)

    return subscriptions


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cancel Stripe premium subscriptions by email and disable local premium access."
    )
    parser.add_argument("email", help="Target user email address")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually cancel Stripe subscriptions and update the local database",
    )
    args = parser.parse_args()

    email = args.email.strip().lower()
    if not email:
        print("email is required", file=sys.stderr)
        return 2

    if not STRIPE_SECRET_KEY:
        print("STRIPE_SECRET_KEY is not configured", file=sys.stderr)
        return 2
    stripe.api_key = STRIPE_SECRET_KEY

    db = SessionLocal()
    try:
        user = (
            db.query(models.User)
            .filter(models.User.email.isnot(None))
            .filter(models.User.email.ilike(email))
            .first()
        )
        if not user:
            print(f"user not found email={email}")
            return 1

        existing_sid = str(getattr(user, "stripe_subscription_id", "") or "").strip() or None
        subscriptions = _find_stripe_subscriptions(email, existing_sid)
        billable_subscriptions = [
            sub for sub in subscriptions if _subscription_status(sub) in ACTIVE_OR_BILLABLE_STATUSES
        ]

        print(
            "user",
            f"id={user.id}",
            f"username={user.username}",
            f"email={user.email}",
            f"is_premium={bool(user.is_premium)}",
            f"stripe_customer_id={user.stripe_customer_id or ''}",
            f"stripe_subscription_id={user.stripe_subscription_id or ''}",
        )
        print(f"stripe_subscriptions_found={len(subscriptions)}")
        for sub in subscriptions:
            print(
                "subscription",
                f"id={_subscription_id(sub)}",
                f"status={_subscription_status(sub)}",
                f"customer={_customer_id(sub) or ''}",
                f"cancel_at_period_end={bool(_stripe_obj_get(sub, 'cancel_at_period_end'))}",
            )
        print(f"billable_subscriptions={len(billable_subscriptions)}")

        if not args.apply:
            print("dry_run=true")
            return 0

        canceled = 0
        for sub in billable_subscriptions:
            sub_id = _subscription_id(sub)
            if not sub_id:
                continue
            stripe.Subscription.delete(sub_id)
            canceled += 1
            print(f"canceled_subscription={sub_id}")

        token_rows = (
            db.query(models.ExternalAccessToken)
            .filter(models.ExternalAccessToken.user_id == user.id)
            .filter(models.ExternalAccessToken.is_active.is_(True))
            .all()
        )
        for token in token_rows:
            token.is_active = False
            db.add(token)

        user.is_premium = False
        user.premium_checked_at = utcnow()
        if billable_subscriptions:
            first = billable_subscriptions[0]
            user.stripe_subscription_id = _subscription_id(first) or user.stripe_subscription_id
            user.stripe_customer_id = _customer_id(first) or user.stripe_customer_id
        db.add(user)
        db.commit()
        invalidate_user_cache(user_id=user.id, username=user.username)

        print(
            "updated",
            f"user_id={user.id}",
            "is_premium=false",
            f"canceled={canceled}",
            f"disabled_external_tokens={len(token_rows)}",
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
