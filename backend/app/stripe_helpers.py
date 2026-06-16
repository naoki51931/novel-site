import threading
from datetime import datetime, timedelta
from typing import Any, Callable
from .time_utils import utcnow


_monthly_stripe_premium_sync_started = False
_monthly_stripe_premium_sync_lock = threading.Lock()
_monthly_stripe_premium_sync_last_run_key: str | None = None


def is_manual_premium_subscription_id(subscription_id: str | None) -> bool:
    sid = str(subscription_id or "").strip()
    return sid in {"manual_premium_3000", "manual_premium_5000"}


def is_manual_moon_arcana_subscription_id(subscription_id: str | None) -> bool:
    sid = str(subscription_id or "").strip()
    return sid in {"manual_premium_3000", "manual_premium_5000"}


def manual_premium_plan_amount_yen(subscription_id: str | None) -> int | None:
    sid = str(subscription_id or "").strip()
    if sid == "manual_premium_3000":
        return 3000
    if sid == "manual_premium_5000":
        return 5000
    return None


def premium_plan_usage_multiplier_for_amount(amount_yen: int | None) -> float:
    amount = int(amount_yen or 1000)
    if amount >= 5000:
        return 6.0
    if amount >= 3000:
        return 3.5
    return 1.0


def premium_plan_amount_yen_for_user(
    user: Any,
    *,
    stripe_price_id_3000: str,
    stripe_price_id_5000: str,
    stripe_module: Any,
    stripe_obj_get: Callable[..., Any],
) -> int:
    subscription_id = str(getattr(user, "stripe_subscription_id", "") or "").strip()
    manual_amount = manual_premium_plan_amount_yen(subscription_id)
    if manual_amount is not None:
        return manual_amount
    allowed = {
        str(stripe_price_id_3000 or "").strip(): 3000,
        str(stripe_price_id_5000 or "").strip(): 5000,
    }
    allowed.pop("", None)
    if not subscription_id or not allowed:
        return 1000
    try:
        subscription = stripe_module.Subscription.retrieve(subscription_id)
    except Exception:
        return 1000
    items = stripe_obj_get(subscription, "items", {}) or {}
    rows = stripe_obj_get(items, "data", []) or []
    matched_amount = 1000
    for item in rows:
        price = stripe_obj_get(item, "price", {}) or {}
        price_id = str(stripe_obj_get(price, "id") or "").strip()
        matched_amount = max(matched_amount, int(allowed.get(price_id, 1000)))
    return matched_amount


def premium_plan_usage_multiplier_for_user(
    user: Any,
    *,
    stripe_price_id_3000: str,
    stripe_price_id_5000: str,
    stripe_module: Any,
    stripe_obj_get: Callable[..., Any],
) -> float:
    return premium_plan_usage_multiplier_for_amount(
        premium_plan_amount_yen_for_user(
            user,
            stripe_price_id_3000=stripe_price_id_3000,
            stripe_price_id_5000=stripe_price_id_5000,
            stripe_module=stripe_module,
            stripe_obj_get=stripe_obj_get,
        )
    )


def _stripe_checkout_customer_kwargs(user: Any) -> dict:
    customer_id = getattr(user, "stripe_customer_id", None) if user else None
    if customer_id:
        return {"customer": customer_id}
    customer_email = getattr(user, "email", None) if user else None
    if customer_email:
        return {"customer_email": customer_email}
    return {}


def _create_checkout_session_with_customer_fallback(
    db: Any,
    user: Any,
    *,
    stripe_module: Any,
    checkout_customer_kwargs: Callable[[Any], dict],
    **checkout_kwargs: Any,
):
    try:
        return stripe_module.checkout.Session.create(
            **checkout_kwargs,
            **checkout_customer_kwargs(user),
        )
    except stripe_module.error.InvalidRequestError as e:
        message = str(e)
        if "No such customer" not in message:
            raise
        if not user or not getattr(user, "stripe_customer_id", None):
            raise

        try:
            user.stripe_customer_id = None
            db.add(user)
            db.commit()
        except Exception:
            db.rollback()

        fallback_kwargs = dict(checkout_kwargs)
        customer_email = getattr(user, "email", None)
        if customer_email:
            fallback_kwargs["customer_email"] = customer_email
        return stripe_module.checkout.Session.create(**fallback_kwargs)


def _stripe_obj_get(obj: Any, key: str, default: Any = None):
    try:
        return obj.get(key, default)
    except Exception:
        return getattr(obj, key, default)


def _stripe_subscription_is_active(subscription: Any) -> bool:
    status = _stripe_obj_get(subscription, "status")
    return status in ("active", "trialing")


def _stripe_subscription_is_monthly(subscription: Any) -> bool:
    items = _stripe_obj_get(subscription, "items", {}) or {}
    data = _stripe_obj_get(items, "data", []) or []
    for item in data:
        price = _stripe_obj_get(item, "price", {}) or {}
        recurring = _stripe_obj_get(price, "recurring", {}) or {}
        interval = str(_stripe_obj_get(recurring, "interval", "") or "").strip().lower()
        try:
            interval_count = int(_stripe_obj_get(recurring, "interval_count", 1) or 1)
        except Exception:
            interval_count = 1
        if interval == "month" and interval_count == 1:
            return True
    return False


def _find_active_monthly_subscription_by_email(
    email: str,
    *,
    stripe_module: Any,
) -> tuple[str | None, str | None]:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return None, None
    customers = stripe_module.Customer.list(email=normalized_email, limit=10)
    customer_rows = _stripe_obj_get(customers, "data", []) or []
    for customer in customer_rows:
        customer_email = str(_stripe_obj_get(customer, "email", "") or "").strip().lower()
        if customer_email and customer_email != normalized_email:
            continue
        customer_id = str(_stripe_obj_get(customer, "id", "") or "").strip() or None
        if not customer_id:
            continue
        subs = stripe_module.Subscription.list(customer=customer_id, status="all", limit=20)
        sub_rows = _stripe_obj_get(subs, "data", []) or []
        for sub in sub_rows:
            if not _stripe_subscription_is_active(sub):
                continue
            if not _stripe_subscription_is_monthly(sub):
                continue
            sub_id = str(_stripe_obj_get(sub, "id", "") or "").strip() or None
            return customer_id, sub_id
    return None, None


def verify_premium_with_stripe(
    user: Any,
    *,
    stripe_secret_key: str,
    stripe_module: Any,
) -> tuple[bool, str | None, str | None]:
    if not stripe_secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY 未設定")

    sub_id = getattr(user, "stripe_subscription_id", None)
    if sub_id:
        if is_manual_premium_subscription_id(sub_id):
            return True, None, str(sub_id).strip()
        sub = stripe_module.Subscription.retrieve(sub_id)
        customer_id = _stripe_obj_get(sub, "customer")
        return _stripe_subscription_is_active(sub), customer_id, _stripe_obj_get(sub, "id")

    customer_id = getattr(user, "stripe_customer_id", None)
    if customer_id:
        subs = stripe_module.Subscription.list(customer=customer_id, status="all", limit=10)
        data = _stripe_obj_get(subs, "data", []) or []
        for sub in data:
            if _stripe_subscription_is_active(sub):
                return True, customer_id, _stripe_obj_get(sub, "id")
        return False, customer_id, None

    return False, None, None


def cancel_stripe_subscription_for_admin_delete(
    subscription_id: str | None,
    *,
    stripe_secret_key: str,
    stripe_module: Any,
    print_fn: Callable[[str], None],
) -> bool:
    sid = str(subscription_id or "").strip()
    if not sid:
        return False
    if is_manual_premium_subscription_id(sid):
        print_fn(f"[stripe] admin delete: manual premium marker, skip cancel sid={sid}")
        return False
    if not stripe_secret_key:
        print_fn(f"[stripe] admin delete: STRIPE_SECRET_KEY missing, skip cancel sid={sid}")
        return False

    try:
        sub = stripe_module.Subscription.retrieve(sid)
        status = str(_stripe_obj_get(sub, "status") or "").strip().lower()
        if status == "canceled":
            print_fn(f"[stripe] admin delete: already canceled sid={sid}")
            return True
    except Exception as e:
        print_fn(f"[stripe] admin delete: retrieve failed sid={sid} err={e!r}")

    try:
        stripe_module.Subscription.delete(sid)
        print_fn(f"[stripe] admin delete: canceled immediately sid={sid}")
        return True
    except Exception as e:
        print_fn(f"[stripe] admin delete: immediate cancel failed sid={sid} err={e!r}")

    try:
        stripe_module.Subscription.modify(sid, cancel_at_period_end=True)
        print_fn(f"[stripe] admin delete: set cancel_at_period_end sid={sid}")
        return True
    except Exception as e:
        print_fn(f"[stripe] admin delete: cancel_at_period_end failed sid={sid} err={e!r}")
        return False


def _run_monthly_stripe_premium_sync_once(
    *,
    stripe_secret_key: str,
    session_local: Callable[[], Any],
    models: Any,
    find_active_monthly_subscription_by_email: Callable[[str], tuple[str | None, str | None]],
    is_ai_chat_demo_bypass_user: Callable[[Any], bool],
    is_force_premium_username: Callable[[str | None], bool],
    logger: Any,
    user_email_query_filter: Callable[[Any], Any] | None = None,
) -> dict[str, int]:
    stats = {
        "checked_users": 0,
        "premium_applied_users": 0,
        "premium_removed_users": 0,
        "errors": 0,
    }
    if not stripe_secret_key:
        return stats
    db = session_local()
    try:
        users_q = (
            db.query(models.User)
            .filter(models.User.email.isnot(None))
        )
        if user_email_query_filter is not None:
            users_q = user_email_query_filter(users_q)
        users = users_q.all()
        now = utcnow()
        for user in users:
            if not user:
                continue
            if is_ai_chat_demo_bypass_user(user):
                continue
            if is_force_premium_username(getattr(user, "username", None)):
                continue
            if is_manual_premium_subscription_id(getattr(user, "stripe_subscription_id", None)):
                continue
            email = str(getattr(user, "email", "") or "").strip().lower()
            if not email:
                continue
            stats["checked_users"] += 1
            try:
                customer_id, sub_id = find_active_monthly_subscription_by_email(email)
            except Exception as e:
                stats["errors"] += 1
                logger.warning("stripe premium sync failed user=%s email=%s err=%r", user.id, email, e)
                continue

            is_premium = bool(getattr(user, "is_premium", False))
            has_active_subscription = bool(customer_id and sub_id)
            if has_active_subscription and is_premium:
                user.premium_checked_at = now
                user.stripe_customer_id = customer_id
                user.stripe_subscription_id = sub_id
                db.add(user)
                try:
                    db.commit()
                except Exception as e:
                    db.rollback()
                    stats["errors"] += 1
                    logger.warning("stripe premium refresh failed user=%s email=%s err=%r", user.id, email, e)
                continue
            if has_active_subscription and not is_premium:
                user.is_premium = True
                user.premium_checked_at = now
                user.stripe_customer_id = customer_id
                user.stripe_subscription_id = sub_id
                db.add(user)
                try:
                    db.commit()
                    stats["premium_applied_users"] += 1
                except Exception as e:
                    db.rollback()
                    stats["errors"] += 1
                    logger.warning("stripe premium apply failed user=%s email=%s err=%r", user.id, email, e)
                continue
            if not has_active_subscription and is_premium:
                user.is_premium = False
                user.premium_checked_at = now
                db.add(user)
                try:
                    db.commit()
                    stats["premium_removed_users"] += 1
                except Exception as e:
                    db.rollback()
                    stats["errors"] += 1
                    logger.warning("stripe premium remove failed user=%s email=%s err=%r", user.id, email, e)
    finally:
        db.close()
    return stats


def _monthly_stripe_premium_sync_loop(
    *,
    acquire_lock: Callable[[], bool] | None = None,
    release_lock: Callable[[], None] | None = None,
    get_last_run_key: Callable[[], str | None] | None = None,
    set_last_run_key: Callable[[str], None] | None = None,
    run_monthly_stripe_premium_sync_once: Callable[[], dict[str, int]],
    logger: Any,
    sync_day: int,
    sync_hour_utc: int,
    interval_seconds: int,
    time_module: Any,
    datetime_module: Any,
) -> None:
    acquire = acquire_lock or (lambda: _monthly_stripe_premium_sync_lock.acquire(blocking=False))
    release = release_lock or (lambda: _monthly_stripe_premium_sync_lock.release())
    get_last = get_last_run_key or (lambda: _monthly_stripe_premium_sync_last_run_key)
    set_last = set_last_run_key or (lambda key: globals().__setitem__("_monthly_stripe_premium_sync_last_run_key", key))
    while True:
        started = time_module.time()
        now_utc = utcnow()
        current_key = f"{now_utc.year:04d}-{now_utc.timetuple().tm_yday // 5:03d}"
        should_run_this_window = now_utc.hour >= sync_hour_utc
        if should_run_this_window and get_last() != current_key:
            if acquire():
                try:
                    stats = run_monthly_stripe_premium_sync_once()
                    set_last(current_key)
                    logger.info(
                        "stripe premium sync done checked=%s applied=%s removed=%s errors=%s",
                        stats["checked_users"],
                        stats["premium_applied_users"],
                        stats.get("premium_removed_users", 0),
                        stats["errors"],
                    )
                except Exception as e:
                    logger.warning("stripe premium sync crashed err=%r", e)
                finally:
                    release()
        elapsed = max(0, int(time_module.time() - started))
        sleep_seconds = max(300, interval_seconds - elapsed)
        time_module.sleep(sleep_seconds)


def _start_monthly_stripe_premium_sync_if_enabled(
    *,
    enabled: bool,
    started: bool | None = None,
    threading_module: Any,
    target: Callable[[], None],
    logger: Any,
    interval_seconds: int,
    sync_day: int,
    sync_hour_utc: int,
) -> bool:
    global _monthly_stripe_premium_sync_started
    if started is None:
        started = _monthly_stripe_premium_sync_started
    if not enabled or started:
        return started
    worker = threading_module.Thread(
        target=target,
        name="monthly-stripe-premium-sync",
        daemon=True,
    )
    worker.start()
    logger.info(
        "stripe premium sync started interval=%ss window_days=5 hour_utc=%s",
        interval_seconds,
        sync_hour_utc,
    )
    _monthly_stripe_premium_sync_started = True
    return True


def revalidate_premium_on_login(
    user: Any,
    db: Any,
    *,
    force_all_premium: bool,
    is_force_premium_username: Callable[[str | None], bool],
    premium_revalidate_days: int,
    stripe_secret_key: str,
    verify_premium_with_stripe: Callable[[Any], tuple[bool, str | None, str | None]],
    invalidate_user_cache: Callable[..., Any],
    cache_user_payload: Callable[[Any], Any],
    print_fn: Callable[..., None],
) -> None:
    if force_all_premium or is_force_premium_username(getattr(user, "username", None)):
        return

    now = utcnow()
    last = getattr(user, "premium_checked_at", None)
    if last and (now - last) < timedelta(days=premium_revalidate_days):
        return

    should_check = bool(getattr(user, "is_premium", False)) or bool(
        getattr(user, "stripe_customer_id", None) or getattr(user, "stripe_subscription_id", None)
    )
    if not should_check:
        return

    if not stripe_secret_key:
        return

    user.is_premium = False
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        active, customer_id, sub_id = verify_premium_with_stripe(user)
    except Exception as e:
        print_fn("[premium] stripe verify failed:", repr(e))
        return

    user.premium_checked_at = now
    if customer_id:
        user.stripe_customer_id = customer_id
    if sub_id:
        user.stripe_subscription_id = sub_id
    user.is_premium = bool(active)
    db.add(user)
    db.commit()
    invalidate_user_cache(user_id=user.id, username=user.username)
    cache_user_payload(user)
