import hashlib
from datetime import date, datetime, timedelta
from typing import Any

from .time_utils import utcnow


def verify_password(plain: str, hashed: str, *, pwd_context: Any) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str, *, pwd_context: Any) -> str:
    return pwd_context.hash(password)


def hash_reset_token(token: str, *, hashlib_module: Any = hashlib) -> str:
    return hashlib_module.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def hash_register_email_code(email: str, code: str, *, normalize_email: Any, hashlib_module: Any = hashlib) -> str:
    seed = f"{normalize_email(email)}:{(code or '').strip()}"
    return hashlib_module.sha256(seed.encode("utf-8")).hexdigest()


def create_access_token(
    data: dict,
    *,
    access_token_expire_minutes: int,
    secret_key: str,
    algorithm: str,
    datetime_cls: Any = datetime,
    timedelta_cls: Any = timedelta,
    jwt_module: Any,
) -> str:
    expire = utcnow() + timedelta_cls(minutes=access_token_expire_minutes)
    to_encode = {**data, "exp": expire}
    return jwt_module.encode(to_encode, secret_key, algorithm=algorithm)


def is_force_premium_username(username: str | None, *, force_premium_usernames: set[str]) -> bool:
    uname = str(username or "").strip().lower()
    return bool(uname) and uname in force_premium_usernames


def is_effective_premium_user(
    user: Any | None,
    *,
    force_all_premium: bool,
    is_force_premium_username: Any,
) -> bool:
    if force_all_premium:
        return True
    if not user:
        return False
    if is_force_premium_username(getattr(user, "username", None)):
        return True
    return bool(getattr(user, "is_premium", False))


def assert_premium_user(
    user: Any,
    detail: str = "この機能はプレミアム会員限定です",
    *,
    is_effective_premium_user: Any,
    http_exception_cls: Any,
) -> None:
    if not is_effective_premium_user(user):
        raise http_exception_cls(status_code=403, detail=detail)


def get_user_by_username(
    db: Any,
    username: str,
    *,
    redis_json_get: Any,
    cache_key_user_by_name: Any,
    cache_user_payload: Any,
    models: Any,
):
    uname = (username or "").strip()
    if not uname:
        return None
    cached = redis_json_get(cache_key_user_by_name(uname))
    if isinstance(cached, dict):
        try:
            cached_id = int(cached.get("id") or 0)
        except Exception:
            cached_id = 0
        if cached_id > 0:
            user = db.get(models.User, cached_id)
            if user:
                cache_user_payload(user)
                return user
    user = db.query(models.User).filter(models.User.username == uname).first()
    if user:
        cache_user_payload(user)
    return user


def get_follow_counts(db: Any, user_id: int, *, models: Any, func: Any) -> tuple[int, int]:
    follower_count = (
        db.query(func.count(models.UserFollow.id))
        .filter(models.UserFollow.followed_user_id == user_id)
        .scalar()
        or 0
    )
    following_count = (
        db.query(func.count(models.UserFollow.id))
        .filter(models.UserFollow.follower_user_id == user_id)
        .scalar()
        or 0
    )
    return int(follower_count), int(following_count)


def is_following_user(db: Any, follower_user_id: int, followed_user_id: int, *, models: Any) -> bool:
    if follower_user_id <= 0 or followed_user_id <= 0 or follower_user_id == followed_user_id:
        return False
    return (
        db.query(models.UserFollow.id)
        .filter(models.UserFollow.follower_user_id == follower_user_id)
        .filter(models.UserFollow.followed_user_id == followed_user_id)
        .first()
        is not None
    )


def normalize_dm_pair(user_id: int, target_id: int, *, http_exception_cls: Any) -> tuple[int, int]:
    if user_id == target_id:
        raise http_exception_cls(400, "自分自身にはDMできません")
    return (user_id, target_id) if user_id < target_id else (target_id, user_id)


def require_current_user(
    request: Any,
    db: Any,
    *,
    secret_key: str,
    algorithm: str,
    jwt_module: Any,
    models: Any,
    http_exception_cls: Any,
):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise http_exception_cls(401, "認証が必要です")
    token = auth.split()[1]
    try:
        payload = jwt_module.decode(token, secret_key, algorithms=[algorithm])
        uid = payload.get("sub")
    except Exception:
        raise http_exception_cls(401, "トークンが不正です")
    user = db.get(models.User, int(uid))
    if not user:
        raise http_exception_cls(401, "ユーザーが存在しません")
    return user


def read_token_user_id(
    request: Any,
    *,
    secret_key: str,
    algorithm: str,
    jwt_module: Any,
    http_exception_cls: Any,
) -> int:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise http_exception_cls(401, "認証が必要です")
    token = auth.split()[1]
    try:
        payload = jwt_module.decode(token, secret_key, algorithms=[algorithm])
        uid = int(payload.get("sub"))
    except Exception:
        raise http_exception_cls(401, "トークンが不正です")
    if uid <= 0:
        raise http_exception_cls(401, "トークンが不正です")
    return uid


def record_user_view_history(
    db: Any,
    *,
    user_id: int,
    target_type: str,
    target_id: int,
    site_key: str = "main",
    normalize_site_key: Any,
    datetime_cls: Any = datetime,
    models: Any,
) -> None:
    if user_id <= 0 or target_id <= 0:
        return
    if target_type not in {"novel", "ai_public_character"}:
        return
    now = utcnow()
    normalized_site_key = normalize_site_key(site_key or "main")
    row = (
        db.query(models.UserViewHistory)
        .filter(
            models.UserViewHistory.user_id == int(user_id),
            models.UserViewHistory.target_type == str(target_type),
            models.UserViewHistory.target_id == int(target_id),
            models.UserViewHistory.site_key == normalized_site_key,
        )
        .first()
    )
    if row:
        row.view_count = int(getattr(row, "view_count", 0) or 0) + 1
        row.last_viewed_at = now
        db.add(row)
    else:
        db.add(
            models.UserViewHistory(
                user_id=int(user_id),
                target_type=str(target_type),
                target_id=int(target_id),
                site_key=normalized_site_key,
                view_count=1,
                first_viewed_at=now,
                last_viewed_at=now,
            )
        )


def calc_age(birth_date: date | None, *, date_cls: Any = date) -> int | None:
    if not birth_date:
        return None
    today = date_cls.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def require_premium_user(
    request: Any,
    db: Any,
    *,
    require_current_user: Any,
    is_effective_premium_user: Any,
    http_exception_cls: Any,
    payment_required_code: int,
):
    user = require_current_user(request, db)
    if not is_effective_premium_user(user):
        raise http_exception_cls(
            status_code=payment_required_code,
            detail="この機能は有料プラン専用です。",
        )
    return user
