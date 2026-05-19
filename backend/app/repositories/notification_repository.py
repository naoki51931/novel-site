from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from .. import models


def find_push_subscription_by_endpoint(db: Session, *, endpoint: str) -> models.PushSubscription | None:
    return (
        db.query(models.PushSubscription)
        .filter(models.PushSubscription.endpoint == endpoint)
        .first()
    )


def delete_push_subscription_for_user(db: Session, *, user_id: int, endpoint: str) -> int:
    return int(
        db.query(models.PushSubscription)
        .filter(
            models.PushSubscription.user_id == user_id,
            models.PushSubscription.endpoint == endpoint,
        )
        .delete(synchronize_session=False)
        or 0
    )


def find_mobile_push_token(db: Session, *, token: str) -> models.MobilePushToken | None:
    return db.query(models.MobilePushToken).filter(models.MobilePushToken.token == token).first()


def delete_mobile_push_token_for_user(db: Session, *, user_id: int, token: str) -> int:
    return int(
        db.query(models.MobilePushToken)
        .filter(models.MobilePushToken.user_id == user_id)
        .filter(models.MobilePushToken.token == token)
        .delete(synchronize_session=False)
        or 0
    )


def notification_query_for_user(db: Session, *, user_id: int):
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id)
        .options(selectinload(models.Notification.actor))
        .order_by(models.Notification.created_at.desc(), models.Notification.id.desc())
    )


def unread_notification_query_for_user(db: Session, *, user_id: int):
    return db.query(models.Notification).filter(
        models.Notification.user_id == user_id,
        models.Notification.is_read == False,
    )


def notification_type_counts_query_for_user(db: Session, *, user_id: int, unread_only: bool):
    query = db.query(models.Notification.type, func.count(models.Notification.id)).filter(
        models.Notification.user_id == user_id
    )
    if unread_only:
        query = query.filter(models.Notification.is_read == False)
    return query.group_by(models.Notification.type)


def find_notification_for_user(db: Session, *, notification_id: int, user_id: int) -> models.Notification | None:
    return (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == user_id,
        )
        .first()
    )


def mark_all_notifications_read_for_user(db: Session, *, user_id: int) -> int:
    return int(
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == user_id,
            models.Notification.is_read == False,
        )
        .update({"is_read": True})
        or 0
    )
