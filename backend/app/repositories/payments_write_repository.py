from sqlalchemy.orm import Session

from .. import models


def create_support(db: Session, **kwargs) -> models.Support:
    row = models.Support(**kwargs)
    db.add(row)
    db.flush()
    return row


def create_support_plan(db: Session, **kwargs) -> models.SupportPlan:
    row = models.SupportPlan(**kwargs)
    db.add(row)
    db.flush()
    return row


def create_membership(db: Session, **kwargs) -> models.Membership:
    row = models.Membership(**kwargs)
    db.add(row)
    db.flush()
    return row


def create_membership_invoice(db: Session, **kwargs) -> models.MembershipInvoice:
    row = models.MembershipInvoice(**kwargs)
    db.add(row)
    db.flush()
    return row


def create_ai_chat_addon_purchase(db: Session, **kwargs) -> models.AIChatAddonPurchase:
    row = models.AIChatAddonPurchase(**kwargs)
    db.add(row)
    db.flush()
    return row


def create_ai_novel_addon_purchase(db: Session, **kwargs) -> models.AINovelAddonPurchase:
    row = models.AINovelAddonPurchase(**kwargs)
    db.add(row)
    db.flush()
    return row
