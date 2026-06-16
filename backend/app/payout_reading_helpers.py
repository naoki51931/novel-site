from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from .time_utils import ensure_utc, utcnow


def calc_platform_fee(amount_yen: int, *, platform_fee_rate: float) -> int:
    if amount_yen <= 0:
        return 0
    return int(amount_yen * platform_fee_rate)


def calc_author_share(amount_yen: int, *, calc_platform_fee: Any) -> tuple[int, int]:
    fee = calc_platform_fee(amount_yen)
    return fee, amount_yen - fee


def get_or_create_author_balance(db: Any, author_user_id: int, *, models: Any):
    balance = (
        db.query(models.AuthorBalance)
        .filter(models.AuthorBalance.author_user_id == author_user_id)
        .first()
    )
    if balance:
        return balance
    balance = models.AuthorBalance(author_user_id=author_user_id, available_yen=0, pending_yen=0)
    db.add(balance)
    db.flush()
    return balance


def apply_author_balance_delta(
    db: Any,
    author_user_id: int,
    delta_available: int = 0,
    delta_pending: int = 0,
    *,
    get_or_create_author_balance: Any,
):
    balance = get_or_create_author_balance(db, author_user_id)
    balance.available_yen = int(balance.available_yen or 0) + int(delta_available)
    balance.pending_yen = int(balance.pending_yen or 0) + int(delta_pending)
    db.add(balance)
    return balance


def get_or_create_payout_profile(db: Any, author_user_id: int, *, models: Any):
    profile = (
        db.query(models.AuthorPayoutProfile)
        .filter(models.AuthorPayoutProfile.user_id == author_user_id)
        .first()
    )
    if profile:
        if profile.payout_minimum_yen is None:
            profile.payout_minimum_yen = 3000
            db.add(profile)
            db.flush()
        return profile
    profile = models.AuthorPayoutProfile(user_id=author_user_id, payout_minimum_yen=3000)
    db.add(profile)
    db.flush()
    return profile


def parse_payout_period(
    period: str,
    *,
    http_exception_cls: Any,
    date_cls: Any = date,
    timedelta_cls: Any = timedelta,
) -> tuple[date, date]:
    try:
        year_str, month_str = period.split("-")
        year = int(year_str)
        month = int(month_str)
        if not (1 <= month <= 12):
            raise ValueError("month out of range")
    except Exception:
        raise http_exception_cls(400, "period は YYYY-MM 形式で指定してください")

    start = date_cls(year, month, 1)
    next_month = date_cls(year + 1, 1, 1) if month == 12 else date_cls(year, month + 1, 1)
    return start, next_month - timedelta_cls(days=1)


def truncate_for_free(body: str | None, ratio: float = 0.3) -> str | None:
    if not body:
        return body
    return body[: max(1, int(len(body) * ratio))]


@lru_cache(maxsize=8)
def _jp_holidays(year: int) -> set[date]:
    def nth_weekday(month: int, weekday: int, n: int) -> date:
        first = date(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        return first + timedelta(days=offset + 7 * (n - 1))

    def vernal_equinox_day() -> int:
        return int(20.8431 + 0.242194 * (year - 1980) - ((year - 1980) // 4))

    def autumn_equinox_day() -> int:
        return int(23.2488 + 0.242194 * (year - 1980) - ((year - 1980) // 4))

    holidays = {
        date(year, 1, 1),
        nth_weekday(1, 0, 2),
        date(year, 2, 11),
        date(year, 2, 23),
        date(year, 3, vernal_equinox_day()),
        date(year, 4, 29),
        date(year, 5, 3),
        date(year, 5, 4),
        date(year, 5, 5),
        nth_weekday(7, 0, 3),
        date(year, 8, 11),
        nth_weekday(9, 0, 3),
        date(year, 9, autumn_equinox_day()),
        nth_weekday(10, 0, 2),
        date(year, 11, 3),
        date(year, 11, 23),
    }

    observed = set(holidays)
    for holiday in sorted(holidays):
        if holiday.weekday() == 6:
            substitute = holiday + timedelta(days=1)
            while substitute in observed:
                substitute += timedelta(days=1)
            observed.add(substitute)

    current = date(year, 1, 1)
    end = date(year, 12, 31)
    while current <= end:
        if current not in observed:
            if (
                current.weekday() < 5
                and (current - timedelta(days=1)) in observed
                and (current + timedelta(days=1)) in observed
            ):
                observed.add(current)
        current += timedelta(days=1)
    return observed


def is_jp_holiday(target_date: date) -> bool:
    return target_date in _jp_holidays(target_date.year)


def is_free_reading_time(
    now_utc: datetime | None = None,
    *,
    datetime_cls: Any = datetime,
    timedelta_cls: Any = timedelta,
    is_jp_holiday: Any,
) -> bool:
    base_utc = ensure_utc(now_utc) or utcnow()
    now_jst = base_utc.astimezone(timezone(timedelta(hours=9)))
    current_date = now_jst.date()
    is_weekend_or_holiday = current_date.weekday() >= 5 or is_jp_holiday(current_date)
    start_hour = 14 if is_weekend_or_holiday else 17
    current_hour = now_jst.hour + (now_jst.minute / 60)
    return start_hour <= current_hour < 19


def get_episode_number(ep: Any):
    if hasattr(ep, "episode_number"):
        return ep.episode_number
    if hasattr(ep, "number"):
        return ep.number
    return None


def set_episode_number(ep: Any, val: int) -> None:
    if hasattr(ep, "episode_number"):
        ep.episode_number = val
    elif hasattr(ep, "number"):
        ep.number = val
