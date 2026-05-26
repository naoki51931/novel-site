from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy.types import DateTime as SADateTime
from sqlalchemy.types import TypeDecorator


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_naive_utc(value: datetime | None) -> datetime | None:
    aware = ensure_utc(value)
    if aware is None:
        return None
    return aware.replace(tzinfo=None)


def utcnow() -> datetime:
    return datetime.now(UTC)


JST = timezone(timedelta(hours=9), name="JST")
UTC_MIN = datetime.min.replace(tzinfo=UTC)
UTC_MAX = datetime.max.replace(tzinfo=UTC)


def to_jst(value: datetime | None) -> datetime | None:
    aware = ensure_utc(value)
    if aware is None:
        return None
    return aware.astimezone(JST)


def to_jst_isoformat(value: datetime | None) -> str | None:
    converted = to_jst(value)
    if converted is None:
        return None
    return converted.isoformat()


def display_payload_in_jst(value):
    if isinstance(value, datetime):
        return to_jst_isoformat(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: display_payload_in_jst(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [display_payload_in_jst(v) for v in value]
    return value


class UTCDateTime(TypeDecorator):
    impl = SADateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return to_naive_utc(value)

    def process_result_value(self, value, dialect):
        return ensure_utc(value)
