from datetime import date, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..time_utils import utcnow


def admin_supports_timeline_service(
    *,
    request: Request,
    db: Session,
    days: int,
    limit: int,
    by: str,
):
    from .. import main as legacy

    legacy.require_admin(request)
    if by not in ("author", "supporter"):
        raise HTTPException(400, "by は author または supporter を指定してください")

    today = date.today()
    start_date = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(today + timedelta(days=1), datetime.min.time())

    user_field = (
        legacy.models.Support.author_user_id if by == "author" else legacy.models.Support.supporter_user_id
    )
    day_col = func.date(legacy.models.Support.paid_at)
    base_query = db.query(
        user_field.label("user_id"),
        day_col.label("day"),
        func.count(legacy.models.Support.id).label("count"),
        func.sum(legacy.models.Support.amount_yen).label("amount"),
    ).filter(
        legacy.models.Support.status == "paid",
        legacy.models.Support.paid_at >= start_dt,
        legacy.models.Support.paid_at < end_dt,
    )
    if by == "supporter":
        base_query = base_query.filter(legacy.models.Support.supporter_user_id.isnot(None))

    rows = base_query.group_by(user_field, day_col).all()

    user_series: dict[int, dict[str, list | int]] = {}
    for user_id, day, count, amount in rows:
        if not user_id or not day:
            continue
        if isinstance(day, str):
            day = date.fromisoformat(day)
        day_index = (day - start_date).days
        if day_index < 0 or day_index >= days:
            continue
        entry = user_series.setdefault(
            int(user_id),
            {
                "amounts": [0] * days,
                "counts": [0] * days,
                "total_amount_yen": 0,
                "total_count": 0,
            },
        )
        entry["amounts"][day_index] = int(amount or 0)
        entry["counts"][day_index] = int(count or 0)
        entry["total_amount_yen"] += int(amount or 0)
        entry["total_count"] += int(count or 0)

    user_ids = list(user_series.keys())
    name_map: dict[int, str] = {}
    if user_ids:
        for uid, username in db.query(legacy.models.User.id, legacy.models.User.username).filter(
            legacy.models.User.id.in_(user_ids)
        ):
            name_map[int(uid)] = username

    sorted_users = sorted(
        user_series.items(),
        key=lambda item: item[1]["total_amount_yen"],
        reverse=True,
    )[:limit]

    return {
        "by": by,
        "start_date": start_date.isoformat(),
        "days": days,
        "users": [
            {
                "user_id": user_id,
                "username": name_map.get(user_id, f"user:{user_id}"),
                "amounts": data["amounts"],
                "counts": data["counts"],
                "total_amount_yen": data["total_amount_yen"],
                "total_count": data["total_count"],
            }
            for user_id, data in sorted_users
        ],
    }


def admin_payouts_timeline_service(*, request: Request, db: Session, days: int):
    from .. import main as legacy

    legacy.require_admin(request)
    today = date.today()
    start_date = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(today + timedelta(days=1), datetime.min.time())

    day_col = func.date(legacy.models.Payout.paid_at)
    paid_rows = (
        db.query(
            day_col.label("day"),
            func.count(legacy.models.Payout.id).label("count"),
            func.sum(legacy.models.Payout.amount_yen).label("amount"),
        )
        .filter(
            legacy.models.Payout.status == "paid",
            legacy.models.Payout.paid_at >= start_dt,
            legacy.models.Payout.paid_at < end_dt,
        )
        .group_by(day_col)
        .all()
    )

    amounts = [0] * days
    counts = [0] * days
    for day, count, amount in paid_rows:
        if not day:
            continue
        if isinstance(day, str):
            day = date.fromisoformat(day)
        day_index = (day - start_date).days
        if day_index < 0 or day_index >= days:
            continue
        amounts[day_index] = int(amount or 0)
        counts[day_index] = int(count or 0)

    upcoming_rows = (
        db.query(legacy.models.Payout, legacy.models.User.username)
        .join(legacy.models.User, legacy.models.User.id == legacy.models.Payout.author_user_id)
        .filter(legacy.models.Payout.status.in_(["scheduled", "processing"]))
        .order_by(legacy.models.Payout.created_at.asc())
        .limit(50)
        .all()
    )
    upcoming = [
        {
            "payout_id": payout.id,
            "author_user_id": payout.author_user_id,
            "username": username,
            "amount_yen": payout.amount_yen,
            "status": payout.status,
            "period_start": payout.period_start.isoformat(),
            "period_end": payout.period_end.isoformat(),
            "created_at": legacy.to_jst_isoformat(payout.created_at),
        }
        for payout, username in upcoming_rows
    ]

    recent_paid_rows = (
        db.query(legacy.models.Payout, legacy.models.User.username)
        .join(legacy.models.User, legacy.models.User.id == legacy.models.Payout.author_user_id)
        .filter(legacy.models.Payout.status == "paid")
        .order_by(legacy.models.Payout.paid_at.desc())
        .limit(20)
        .all()
    )
    recent_paid = [
        {
            "payout_id": payout.id,
            "author_user_id": payout.author_user_id,
            "username": username,
            "amount_yen": payout.amount_yen,
            "paid_at": legacy.to_jst_isoformat(payout.paid_at),
            "period_start": payout.period_start.isoformat(),
            "period_end": payout.period_end.isoformat(),
        }
        for payout, username in recent_paid_rows
    ]

    return {
        "start_date": start_date.isoformat(),
        "days": days,
        "paid_amounts": amounts,
        "paid_counts": counts,
        "upcoming": upcoming,
        "recent_paid": recent_paid,
        "payout_minimum_yen": 3000,
    }


def admin_list_payouts_service(*, request: Request, db: Session, status: str | None, limit: int):
    from .. import main as legacy

    legacy.require_admin(request)
    statuses = None
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]

    query = (
        db.query(legacy.models.Payout, legacy.models.User.username)
        .join(legacy.models.User, legacy.models.User.id == legacy.models.Payout.author_user_id)
    )
    if statuses:
        query = query.filter(legacy.models.Payout.status.in_(statuses))

    rows = query.order_by(legacy.models.Payout.created_at.desc(), legacy.models.Payout.id.desc()).limit(limit).all()
    return {
        "items": [
            {
                "payout_id": payout.id,
                "author_user_id": payout.author_user_id,
                "username": username,
                "amount_yen": payout.amount_yen,
                "status": payout.status,
                "period_start": payout.period_start.isoformat(),
                "period_end": payout.period_end.isoformat(),
                "created_at": legacy.to_jst_isoformat(payout.created_at),
            }
            for payout, username in rows
        ]
    }


def admin_author_payout_profile_service(*, author_user_id: int, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    profile = legacy.get_or_create_payout_profile(db, author_user_id)
    user = db.get(legacy.models.User, author_user_id)
    if not user:
        raise HTTPException(404, "ユーザーが見つかりません")
    return {
        "author_user_id": author_user_id,
        "username": user.username,
        "payout_enabled": bool(profile.payout_enabled),
        "payout_minimum_yen": max(3000, int(profile.payout_minimum_yen or 0)),
        "bank_name": profile.bank_name,
        "bank_branch": profile.bank_branch,
        "bank_account_type": profile.bank_account_type,
        "bank_account_number": profile.bank_account_number,
        "bank_account_holder": profile.bank_account_holder,
    }


def generate_payouts_service(*, period: str, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    period_start, period_end = legacy.parse_payout_period(period)
    start_dt = datetime.combine(period_start, datetime.min.time())
    end_dt = datetime.combine(period_end + timedelta(days=1), datetime.min.time())

    support_payout_subq = (
        db.query(legacy.models.PayoutItem.source_id)
        .filter(legacy.models.PayoutItem.source_type == "support")
        .subquery()
    )
    supports = (
        db.query(legacy.models.Support)
        .filter(
            legacy.models.Support.status == "paid",
            legacy.models.Support.paid_at >= start_dt,
            legacy.models.Support.paid_at < end_dt,
            ~legacy.models.Support.id.in_(support_payout_subq),
        )
        .all()
    )

    invoice_payout_subq = (
        db.query(legacy.models.PayoutItem.source_id)
        .filter(legacy.models.PayoutItem.source_type == "membership_invoice")
        .subquery()
    )
    invoice_rows = (
        db.query(legacy.models.MembershipInvoice, legacy.models.Membership.author_user_id)
        .join(legacy.models.Membership, legacy.models.Membership.id == legacy.models.MembershipInvoice.membership_id)
        .filter(
            legacy.models.MembershipInvoice.status == "paid",
            legacy.models.MembershipInvoice.paid_at >= start_dt,
            legacy.models.MembershipInvoice.paid_at < end_dt,
            ~legacy.models.MembershipInvoice.id.in_(invoice_payout_subq),
        )
        .all()
    )

    author_items: dict[int, dict[str, list]] = {}
    for support in supports:
        author_items.setdefault(support.author_user_id, {"supports": [], "invoices": []})
        author_items[support.author_user_id]["supports"].append(support)
    for invoice, author_user_id in invoice_rows:
        author_items.setdefault(author_user_id, {"supports": [], "invoices": []})
        author_items[author_user_id]["invoices"].append(invoice)

    created_count = 0
    total_amount = 0
    for author_id, items in author_items.items():
        profile = legacy.get_or_create_payout_profile(db, author_id)
        if not profile.payout_enabled:
            continue
        payout_minimum = max(3000, int(profile.payout_minimum_yen or 0))
        supports_list = items["supports"]
        invoices_list = items["invoices"]
        amount = sum(s.author_share_yen for s in supports_list) + sum(i.author_share_yen for i in invoices_list)
        if amount <= 0 or amount < payout_minimum:
            continue

        payout = legacy.models.Payout(
            author_user_id=author_id,
            period_start=period_start,
            period_end=period_end,
            amount_yen=amount,
            status="scheduled",
        )
        db.add(payout)
        db.flush()

        for support in supports_list:
            db.add(
                legacy.models.PayoutItem(
                    payout_id=payout.id,
                    source_type="support",
                    source_id=support.id,
                    author_share_yen=support.author_share_yen,
                )
            )
        for invoice in invoices_list:
            db.add(
                legacy.models.PayoutItem(
                    payout_id=payout.id,
                    source_type="membership_invoice",
                    source_id=invoice.id,
                    author_share_yen=invoice.author_share_yen,
                )
            )

        legacy.apply_author_balance_delta(db, author_id, delta_available=-amount)
        created_count += 1
        total_amount += amount

    db.commit()
    return {"count": created_count, "total_amount_yen": total_amount}


def preview_payouts_service(*, period: str, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    period_start, period_end = legacy.parse_payout_period(period)
    start_dt = datetime.combine(period_start, datetime.min.time())
    end_dt = datetime.combine(period_end + timedelta(days=1), datetime.min.time())

    support_payout_subq = (
        db.query(legacy.models.PayoutItem.source_id)
        .filter(legacy.models.PayoutItem.source_type == "support")
        .subquery()
    )
    supports = (
        db.query(legacy.models.Support)
        .filter(
            legacy.models.Support.status == "paid",
            legacy.models.Support.paid_at >= start_dt,
            legacy.models.Support.paid_at < end_dt,
            ~legacy.models.Support.id.in_(support_payout_subq),
        )
        .all()
    )

    invoice_payout_subq = (
        db.query(legacy.models.PayoutItem.source_id)
        .filter(legacy.models.PayoutItem.source_type == "membership_invoice")
        .subquery()
    )
    invoice_rows = (
        db.query(legacy.models.MembershipInvoice, legacy.models.Membership.author_user_id)
        .join(legacy.models.Membership, legacy.models.Membership.id == legacy.models.MembershipInvoice.membership_id)
        .filter(
            legacy.models.MembershipInvoice.status == "paid",
            legacy.models.MembershipInvoice.paid_at >= start_dt,
            legacy.models.MembershipInvoice.paid_at < end_dt,
            ~legacy.models.MembershipInvoice.id.in_(invoice_payout_subq),
        )
        .all()
    )

    author_items: dict[int, dict[str, list]] = {}
    for support in supports:
        author_items.setdefault(support.author_user_id, {"supports": [], "invoices": []})
        author_items[support.author_user_id]["supports"].append(support)
    for invoice, author_user_id in invoice_rows:
        author_items.setdefault(author_user_id, {"supports": [], "invoices": []})
        author_items[author_user_id]["invoices"].append(invoice)

    if author_items:
        users = db.query(legacy.models.User.id, legacy.models.User.username).filter(
            legacy.models.User.id.in_(author_items.keys())
        ).all()
        user_map = {int(uid): username for uid, username in users}
    else:
        user_map = {}

    authors = []
    for author_id, items in author_items.items():
        profile = legacy.get_or_create_payout_profile(db, author_id)
        payout_minimum = max(3000, int(profile.payout_minimum_yen or 0))
        supports_list = items["supports"]
        invoices_list = items["invoices"]
        support_amount = sum(s.author_share_yen for s in supports_list)
        invoice_amount = sum(i.author_share_yen for i in invoices_list)
        amount = support_amount + invoice_amount

        eligible = True
        reason = ""
        if not profile.payout_enabled:
            eligible = False
            reason = "payout_disabled"
        elif amount <= 0:
            eligible = False
            reason = "zero_amount"
        elif amount < payout_minimum:
            eligible = False
            reason = "below_minimum"

        authors.append(
            {
                "author_user_id": author_id,
                "username": user_map.get(author_id, f"user:{author_id}"),
                "payout_enabled": bool(profile.payout_enabled),
                "payout_minimum_yen": payout_minimum,
                "support_amount_yen": int(support_amount),
                "support_count": len(supports_list),
                "invoice_amount_yen": int(invoice_amount),
                "invoice_count": len(invoices_list),
                "total_amount_yen": int(amount),
                "eligible": eligible,
                "reason": reason,
            }
        )
    authors.sort(key=lambda row: row["total_amount_yen"], reverse=True)

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "authors": authors,
        "support_count": len(supports),
        "invoice_count": len(invoice_rows),
    }


def mark_payout_paid_service(*, payout_id: int, req, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    payout = db.get(legacy.models.Payout, payout_id)
    if not payout:
        raise HTTPException(404, "payout が見つかりません")

    payout.status = "paid"
    payout.paid_at = utcnow()
    if req.note is not None:
        payout.note = req.note
    db.add(payout)
    db.commit()
    return {"ok": True}


def mark_payout_failed_service(*, payout_id: int, req, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    payout = db.get(legacy.models.Payout, payout_id)
    if not payout:
        raise HTTPException(404, "payout が見つかりません")

    if payout.status != "failed":
        legacy.apply_author_balance_delta(db, payout.author_user_id, delta_available=payout.amount_yen)
    payout.status = "failed"
    if req.note is not None:
        payout.note = req.note
    db.add(payout)
    db.commit()
    return {"ok": True}
