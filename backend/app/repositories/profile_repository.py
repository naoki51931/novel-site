from sqlalchemy.orm import Session

from .. import models


def get_user_by_id(db: Session, *, user_id: int) -> models.User | None:
    return db.get(models.User, user_id)


def find_user_by_username_except_id(
    db: Session,
    *,
    username: str,
    excluded_user_id: int,
) -> models.User | None:
    return (
        db.query(models.User)
        .filter(models.User.username == username, models.User.id != excluded_user_id)
        .first()
    )
