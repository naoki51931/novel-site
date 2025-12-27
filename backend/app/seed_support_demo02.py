import os
from datetime import datetime

from app.database import SessionLocal
from app import models


def main() -> None:
    amount_yen = 4500
    fee_rate = float(os.getenv("PLATFORM_FEE_RATE", "0.2"))
    fee_yen = int(amount_yen * fee_rate)
    share_yen = amount_yen - fee_yen

    session = SessionLocal()
    try:
        user = session.query(models.User).filter(models.User.username == "demo02").first()
        if not user:
            raise SystemExit("demo02 user not found")

        existing = (
            session.query(models.Support)
            .filter(models.Support.author_user_id == user.id)
            .filter(models.Support.amount_yen == amount_yen)
            .filter(models.Support.status == "paid")
            .filter(models.Support.stripe_checkout_session_id.like("test_support_demo02_4500%"))
            .first()
        )
        if existing:
            print(f"exists support id={existing.id}")
            return

        session_id = f"test_support_demo02_4500_{int(datetime.utcnow().timestamp())}"
        support = models.Support(
            supporter_user_id=None,
            author_user_id=user.id,
            novel_id=None,
            episode_id=None,
            amount_yen=amount_yen,
            platform_fee_yen=fee_yen,
            author_share_yen=share_yen,
            status="paid",
            stripe_checkout_session_id=session_id,
            stripe_payment_intent_id=f"pi_{session_id}",
            paid_at=datetime.utcnow(),
        )
        session.add(support)

        balance = (
            session.query(models.AuthorBalance)
            .filter(models.AuthorBalance.author_user_id == user.id)
            .first()
        )
        if not balance:
            balance = models.AuthorBalance(author_user_id=user.id, available_yen=0, pending_yen=0)
            session.add(balance)
            session.flush()
        balance.available_yen = int(balance.available_yen or 0) + share_yen
        session.add(balance)

        session.commit()
        print(f"inserted support id={support.id}, author_user_id={user.id}, share={share_yen}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
