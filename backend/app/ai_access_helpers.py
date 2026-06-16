import hashlib
import re
import secrets
from datetime import date, datetime, timedelta
from typing import Any

import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from . import models
from .time_utils import utcnow


def _legacy():
    from . import main as legacy

    return legacy


def _record_ai_chat_tokens(
    db: Session,
    user: models.User | None,
    guest_usage: models.AIChatGuestUsage | None,
    tokens_used: int | None,
) -> None:
    legacy = _legacy()
    if tokens_used is None:
        return
    n = int(tokens_used or 0)
    if n <= 0:
        return
    if user is not None:
        legacy._sync_user_ai_chat_monthly_usage(user)
        user.ai_chat_tokens_used = int(getattr(user, "ai_chat_tokens_used", 0) or 0) + n
        user.ai_chat_tokens_total_used = int(getattr(user, "ai_chat_tokens_total_used", 0) or 0) + n
        db.add(user)
        db.add(
            models.AIChatTokenUsageLog(
                user_id=int(getattr(user, "id", 0) or 0) or None,
                guest_id=None,
                tokens_used=n,
            )
        )
        db.commit()
        return
    if guest_usage is not None:
        guest_usage.tokens_used = int(getattr(guest_usage, "tokens_used", 0) or 0) + n
        guest_usage.last_used_at = utcnow()
        db.add(guest_usage)
        db.add(
            models.AIChatTokenUsageLog(
                user_id=None,
                guest_id=str(getattr(guest_usage, "guest_id", "") or "")[:64] or None,
                tokens_used=n,
            )
        )
        db.commit()


def get_optional_current_user(request: Any, db: Session) -> models.User | None:
    legacy = _legacy()
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "トークンが不正です")
    token = auth.split()[1]

    try:
        payload = jwt.decode(token, legacy.SECRET_KEY, algorithms=[legacy.ALGORITHM])
        uid = payload.get("sub")
    except Exception:
        raise HTTPException(401, "トークンが不正です")

    user = db.get(models.User, int(uid))
    if not user:
        raise HTTPException(401, "ユーザーが存在しません")
    return user


def get_optional_current_user_soft(request: Any, db: Session) -> models.User | None:
    try:
        return get_optional_current_user(request, db)
    except HTTPException:
        return None


def _get_client_ip_for_guest(request: Any) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        for part in xff.split(","):
            candidate = (part or "").strip()
            if candidate and candidate.lower() != "unknown":
                return candidate[:64]
    xri = (request.headers.get("x-real-ip") or "").strip()
    if xri and xri.lower() != "unknown":
        return xri[:64]
    client = getattr(request, "client", None)
    host = str(getattr(client, "host", "") or "").strip()
    if host and host.lower() != "unknown":
        return host[:64]
    return ""


def get_or_set_ai_guest_id(request: Any, response: Any) -> str:
    legacy = _legacy()
    client_ip = _get_client_ip_for_guest(request)
    if client_ip:
        digest = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:40]
        guest_id = f"gip_{digest}"
        response.set_cookie(
            key=legacy.AI_GUEST_COOKIE_NAME,
            value=guest_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
        )
        return guest_id

    raw = request.cookies.get(legacy.AI_GUEST_COOKIE_NAME)
    if isinstance(raw, str):
        cookie_guest_id = raw.strip()
        if 1 <= len(cookie_guest_id) <= 64 and re.fullmatch(r"[A-Za-z0-9_-]+", cookie_guest_id):
            return cookie_guest_id

    guest_id = secrets.token_urlsafe(24)[:64]
    response.set_cookie(
        key=legacy.AI_GUEST_COOKIE_NAME,
        value=guest_id,
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return guest_id


def get_guest_ai_usage(db: Session, guest_id: str) -> models.AIGuestGenerateUsage:
    usage = (
        db.query(models.AIGuestGenerateUsage)
        .filter(models.AIGuestGenerateUsage.guest_id == guest_id)
        .first()
    )
    if not usage:
        usage = models.AIGuestGenerateUsage(guest_id=guest_id, generate_count=0)
        db.add(usage)
        db.commit()
        db.refresh(usage)
    return usage


def get_ai_chat_guest_usage(db: Session, guest_id: str) -> models.AIChatGuestUsage:
    usage = (
        db.query(models.AIChatGuestUsage)
        .filter(models.AIChatGuestUsage.guest_id == guest_id)
        .first()
    )
    if not usage:
        usage = models.AIChatGuestUsage(guest_id=guest_id, tokens_used=0)
        db.add(usage)
        db.commit()
        db.refresh(usage)
    return usage


def require_guest_ai_quota(db: Session, guest_id: str) -> models.AIGuestGenerateUsage:
    usage = get_guest_ai_usage(db, guest_id)
    if int(getattr(usage, "generate_count", 0) or 0) >= _legacy().AI_GUEST_FREE_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"無料の AI 小説生成の上限（{_legacy().AI_GUEST_FREE_MAX}回）に達しました。",
        )
    return usage


def check_ai_quota(db: Session, user_id: int, limit_per_day: int = 10):
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = start + timedelta(days=1)

    count = (
        db.query(models.AIGenerateLog)
        .filter(
            models.AIGenerateLog.user_id == user_id,
            models.AIGenerateLog.created_at >= start,
            models.AIGenerateLog.created_at < end,
        )
        .count()
    )

    if count >= limit_per_day:
        raise HTTPException(
            status_code=429,
            detail="本日の AI 小説生成の上限回数に達しました。",
        )


def save_ai_log(
    db: Session,
    *,
    user_id: int | None,
    guest_id: str | None,
    prompt_summary: str | None,
    tokens_used: int | None,
    model: str | None,
    commit: bool = True,
):
    if user_id is None and not str(guest_id or "").strip():
        return
    log = models.AIGenerateLog(
        user_id=user_id,
        guest_id=str(guest_id or "").strip()[:64] or None,
        prompt_summary=(str(prompt_summary or "").strip()[:200] or None),
        tokens_used=tokens_used,
        model=(str(model or "").strip()[:64] or None),
    )
    db.add(log)
    if commit:
        db.commit()


def save_ai_novel_request_log(
    db: Session,
    *,
    user_id: int | None,
    guest_id: str | None,
    req: Any,
    resp: Any,
):
    summary_src = req.title_hint or req.genre or req.characters or ""
    save_ai_log(
        db,
        user_id=user_id,
        guest_id=guest_id,
        prompt_summary=str(summary_src or "").strip()[:200] or None,
        tokens_used=getattr(resp, "used_tokens", None),
        model=getattr(resp, "model", None) or getattr(req, "model", None),
    )


def _is_ai_chat_demo_bypass_user(user: Any, *, ai_chat_demo_bypass_username: str) -> bool:
    if not user:
        return False
    marker = (ai_chat_demo_bypass_username or "").strip()
    if not marker:
        return False
    return str(getattr(user, "username", "") or "").strip().lower() == marker.lower()


def _is_ai_chat_demo_bypass_username(username: str | None, *, ai_chat_demo_bypass_username: str) -> bool:
    marker = (ai_chat_demo_bypass_username or "").strip()
    if not marker:
        return False
    return str(username or "").strip().lower() == marker.lower()


def _can_edit_ai_chat_character(
    *,
    viewer: Any,
    owner_user_id: int | None,
    owner_username: str | None = None,
    db: Session | None = None,
    is_ai_chat_demo_bypass_username: Any,
    ai_chat_demo_bypass_username: str,
    models_module: Any,
    func_module: Any,
) -> bool:
    if viewer is None or owner_user_id is None:
        return False
    if int(owner_user_id) == int(getattr(viewer, "id", 0) or 0):
        return True
    if is_ai_chat_demo_bypass_username(owner_username):
        return True
    if db is None:
        return False
    marker = (ai_chat_demo_bypass_username or "").strip()
    if not marker:
        return False
    row = (
        db.query(models_module.User.id)
        .filter(func_module.lower(models_module.User.username) == marker.lower())
        .first()
    )
    if not row:
        return False
    demo_owner_id = int(row[0] or 0)
    return demo_owner_id > 0 and int(owner_user_id) == demo_owner_id


def _find_editable_ai_chat_character(
    *,
    db: Session,
    viewer: Any,
    character_id: int,
    can_edit_ai_chat_character: Any,
    models_module: Any,
):
    item = (
        db.query(models_module.AIChatCharacter)
        .filter(
            models_module.AIChatCharacter.id == character_id,
            models_module.AIChatCharacter.is_deleted == False,
        )
        .first()
    )
    if not item:
        return None
    if can_edit_ai_chat_character(
        viewer=viewer,
        owner_user_id=getattr(item, "user_id", None),
        owner_username=str(getattr(getattr(item, "user", None), "username", "") or "").strip() or None,
        db=db,
    ):
        return item
    return None


def _find_accessible_ai_chat_character(
    *,
    db: Session,
    viewer: Any,
    character_id: int,
    can_edit_ai_chat_character: Any,
    is_ai_chat_demo_bypass_user: Any,
    models_module: Any,
):
    item = (
        db.query(models_module.AIChatCharacter)
        .filter(
            models_module.AIChatCharacter.id == character_id,
            models_module.AIChatCharacter.is_deleted == False,
        )
        .first()
    )
    if not item:
        return None
    can_edit = can_edit_ai_chat_character(
        viewer=viewer,
        owner_user_id=getattr(item, "user_id", None),
        owner_username=str(getattr(getattr(item, "user", None), "username", "") or "").strip() or None,
        db=db,
    )
    is_demo_reader = is_ai_chat_demo_bypass_user(viewer)
    if can_edit or bool(getattr(item, "is_public", False)) or is_demo_reader:
        return item
    return None


def _compute_ai_chat_name_duplicate_index(
    *,
    db: Session,
    character: Any,
    models_module: Any,
    func_module: Any,
) -> int:
    if character is None:
        return 1
    cid = int(getattr(character, "id", 0) or 0)
    owner_id = int(getattr(character, "user_id", 0) or 0)
    name = str(getattr(character, "name", "") or "").strip()
    if cid <= 0 or owner_id <= 0 or not name:
        return 1
    count = (
        db.query(func_module.count(models_module.AIChatCharacter.id))
        .filter(
            models_module.AIChatCharacter.user_id == owner_id,
            models_module.AIChatCharacter.name == name,
            models_module.AIChatCharacter.is_deleted == False,
            models_module.AIChatCharacter.id <= cid,
        )
        .scalar()
    )
    return max(1, int(count or 1))


def _ai_chat_allowed_tokens(
    user: Any,
    *,
    is_effective_premium_user: Any,
    ai_chat_premium_included_blocks: int,
    premium_plan_usage_multiplier_for_user: Any,
    ai_chat_free_tokens: int,
    ai_chat_block_tokens: int,
) -> int:
    is_premium = is_effective_premium_user(user)
    paid_blocks = max(0, int(getattr(user, "ai_chat_paid_blocks", 0) or 0))
    if not is_premium:
        return max(0, ai_chat_free_tokens) + paid_blocks * max(1, ai_chat_block_tokens)
    premium_included_blocks = max(0, ai_chat_premium_included_blocks)
    base_tokens = max(0, ai_chat_free_tokens) + premium_included_blocks * max(1, ai_chat_block_tokens)
    multiplier = max(1.0, float(premium_plan_usage_multiplier_for_user(user) or 1.0))
    return int(base_tokens * multiplier) + paid_blocks * max(1, ai_chat_block_tokens)


def _current_ai_chat_month_key_utc(now: datetime | None = None) -> int:
    ref = now or utcnow()
    return int(ref.year * 100 + ref.month)


def _sync_user_ai_chat_monthly_usage(user: Any, *, current_ai_chat_month_key_utc: Any) -> bool:
    month_key = current_ai_chat_month_key_utc()
    stored_key = int(getattr(user, "ai_chat_tokens_month_key", 0) or 0)
    month_used = max(0, int(getattr(user, "ai_chat_tokens_used", 0) or 0))
    total_used = max(0, int(getattr(user, "ai_chat_tokens_total_used", 0) or 0))
    if stored_key <= 0:
        user.ai_chat_tokens_total_used = total_used + month_used
        user.ai_chat_tokens_used = 0
        user.ai_chat_tokens_month_key = month_key
        return True
    if stored_key != month_key:
        user.ai_chat_tokens_used = 0
        user.ai_chat_tokens_month_key = month_key
        return True
    return False


def _ensure_ai_chat_access(
    user: Any,
    db: Session | None = None,
    *,
    is_ai_chat_demo_bypass_user: Any,
    sync_user_ai_chat_monthly_usage: Any,
    is_effective_premium_user: Any,
    ai_chat_allowed_tokens: Any,
    ai_chat_free_tokens: int,
    premium_plan_usage_multiplier_for_user: Any,
    ai_chat_premium_included_blocks: int,
    ai_chat_block_tokens: int,
    ai_chat_block_price_yen: int,
    http_exception_cls: Any,
    payment_required_code: int,
) -> None:
    if is_ai_chat_demo_bypass_user(user):
        return
    rotated = sync_user_ai_chat_monthly_usage(user)
    if db is not None and rotated:
        db.add(user)
        db.commit()

    is_premium = is_effective_premium_user(user)
    used = max(0, int(getattr(user, "ai_chat_tokens_used", 0) or 0))
    allowed = ai_chat_allowed_tokens(user)
    if used < allowed:
        return

    if not is_premium:
        detail = (
            f"AIチャットの無料枠（{max(0, ai_chat_free_tokens):,}トークン）に達しました。"
            "継続するにはプレミアム登録が必要です。"
            f"プレミアム登録後は追加で{ai_chat_block_tokens:,}トークンの利用枠が付与されます。"
        )
    else:
        multiplier = max(1.0, float(premium_plan_usage_multiplier_for_user(user) or 1.0))
        premium_base = int((max(0, ai_chat_free_tokens) + max(0, ai_chat_premium_included_blocks) * max(1, ai_chat_block_tokens)) * multiplier)
        over = max(0, used - premium_base)
        consumed_paid_blocks = over // max(1, ai_chat_block_tokens)
        next_required_block = consumed_paid_blocks + 1
        detail = (
            f"プレミアム分を含む利用枠（{allowed:,}トークン）に達しました。"
            f"追加課金（{ai_chat_block_tokens:,}トークンごとに{ai_chat_block_price_yen:,}円）で継続できます。"
            f"次回解放に必要な追加ブロック: {next_required_block}"
        )
    raise http_exception_cls(status_code=payment_required_code, detail=detail)


def _ensure_ai_chat_guest_access(
    usage: Any,
    *,
    ai_chat_guest_tokens: int,
    http_exception_cls: Any,
    payment_required_code: int,
) -> None:
    used = max(0, int(getattr(usage, "tokens_used", 0) or 0))
    allowed = max(0, int(ai_chat_guest_tokens or 0))
    if used < allowed:
        return
    raise http_exception_cls(
        status_code=payment_required_code,
        detail=(
            f"ゲスト利用の上限（{allowed:,}トークン）に達しました。"
            "継続するにはログインしてください。"
        ),
    )
