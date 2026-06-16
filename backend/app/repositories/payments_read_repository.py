from sqlalchemy.orm import Session

from .. import models


def get_user(db: Session, *, user_id: int) -> models.User | None:
    return db.get(models.User, user_id)


def find_user_by_stripe_customer_id(db: Session, *, stripe_customer_id: str) -> models.User | None:
    return (
        db.query(models.User)
        .filter(models.User.stripe_customer_id == stripe_customer_id)
        .first()
    )


def find_user_by_email(db: Session, *, email: str) -> models.User | None:
    return db.query(models.User).filter(models.User.email == email).first()


def list_active_support_plans(db: Session, *, author_user_id: int) -> list[models.SupportPlan]:
    return (
        db.query(models.SupportPlan)
        .filter(models.SupportPlan.author_user_id == author_user_id)
        .filter(models.SupportPlan.is_active == True)
        .order_by(models.SupportPlan.amount_yen.asc(), models.SupportPlan.id.asc())
        .all()
    )


def list_author_support_plans(db: Session, *, author_user_id: int) -> list[models.SupportPlan]:
    return (
        db.query(models.SupportPlan)
        .filter(models.SupportPlan.author_user_id == author_user_id)
        .order_by(
            models.SupportPlan.is_active.desc(),
            models.SupportPlan.amount_yen.asc(),
            models.SupportPlan.id.asc(),
        )
        .all()
    )


def find_support_plan(db: Session, *, plan_id: int) -> models.SupportPlan | None:
    return db.get(models.SupportPlan, plan_id)


def find_active_support_plan_duplicate(
    db: Session,
    *,
    author_user_id: int,
    amount_yen: int,
    exclude_plan_id: int | None = None,
) -> models.SupportPlan | None:
    query = (
        db.query(models.SupportPlan)
        .filter(
            models.SupportPlan.author_user_id == author_user_id,
            models.SupportPlan.amount_yen == amount_yen,
            models.SupportPlan.is_active == True,
        )
    )
    if exclude_plan_id is not None:
        query = query.filter(models.SupportPlan.id != exclude_plan_id)
    return query.first()


def find_support_by_checkout_session_id(db: Session, *, session_id: str) -> models.Support | None:
    return (
        db.query(models.Support)
        .filter(models.Support.stripe_checkout_session_id == session_id)
        .first()
    )


def find_support_by_payment_intent_id(db: Session, *, payment_intent_id: str) -> models.Support | None:
    return (
        db.query(models.Support)
        .filter(models.Support.stripe_payment_intent_id == payment_intent_id)
        .first()
    )


def find_membership_by_subscription_id(db: Session, *, subscription_id: str) -> models.Membership | None:
    return (
        db.query(models.Membership)
        .filter(models.Membership.stripe_subscription_id == subscription_id)
        .first()
    )


def find_membership_invoice_by_stripe_invoice_id(
    db: Session,
    *,
    stripe_invoice_id: str,
) -> models.MembershipInvoice | None:
    return (
        db.query(models.MembershipInvoice)
        .filter(models.MembershipInvoice.stripe_invoice_id == stripe_invoice_id)
        .first()
    )


def find_ai_chat_addon_purchase_by_session_id(
    db: Session,
    *,
    session_id: str,
) -> models.AIChatAddonPurchase | None:
    return (
        db.query(models.AIChatAddonPurchase)
        .filter(models.AIChatAddonPurchase.stripe_checkout_session_id == session_id)
        .first()
    )


def find_ai_novel_addon_purchase_by_session_id(
    db: Session,
    *,
    session_id: str,
) -> models.AINovelAddonPurchase | None:
    return (
        db.query(models.AINovelAddonPurchase)
        .filter(models.AINovelAddonPurchase.stripe_checkout_session_id == session_id)
        .first()
    )
