from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from ..repositories import profile_repository as repo


def _normalize_profile_url(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if len(raw) > 255:
        raw = raw[:255]
    lowered = raw.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return raw
    return f"https://{raw}"


def read_profile_service(*, request: Request, db: Session):
    from .. import main as legacy

    uid = legacy._read_token_user_id(request)
    cached = legacy.redis_json_get(legacy._cache_key_user_profile(uid))
    if isinstance(cached, dict):
        return cached
    user = repo.get_user_by_id(db, user_id=uid)
    if not user:
        raise HTTPException(401, "ユーザーが存在しません")
    return legacy.cache_user_payload(user)


def read_me_service(*, request: Request, db: Session):
    return read_profile_service(request=request, db=db)


def update_profile_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    old_username = str(user.username or "")

    if payload.username is not None:
        new_username = payload.username.strip()
        if not new_username:
            raise HTTPException(400, "ユーザー名を空にすることはできません")

        if new_username != user.username:
            exists = repo.find_user_by_username_except_id(
                db,
                username=new_username,
                excluded_user_id=int(user.id),
            )
            if exists:
                raise HTTPException(400, "このユーザー名は既に使用されています")

            user.username = new_username

    if payload.email is not None:
        email = payload.email.strip()
        user.email = email or None
        user.email_address_invalid = False
        user.email_2fa_skip_until = None

    if payload.birth_date is not None:
        user.birth_date = payload.birth_date

    if payload.email_notifications_enabled is not None:
        user.email_notifications_enabled = payload.email_notifications_enabled
    if payload.favorite_visibility is not None:
        normalized_visibility = str(payload.favorite_visibility or "").strip().lower()
        if normalized_visibility not in ("public", "private"):
            raise HTTPException(400, "favorite_visibility は public/private のみ指定できます")
        user.favorite_visibility = normalized_visibility
    if payload.profile_bio is not None:
        user.profile_bio = str(payload.profile_bio or "").strip()[:4000] or None
    if payload.profile_icon_url is not None:
        user.profile_icon_url = _normalize_profile_url(payload.profile_icon_url)
    if payload.profile_header_url is not None:
        user.profile_header_url = _normalize_profile_url(payload.profile_header_url)
    if payload.profile_website_url is not None:
        user.profile_website_url = _normalize_profile_url(payload.profile_website_url)
    if payload.profile_x_url is not None:
        user.profile_x_url = _normalize_profile_url(payload.profile_x_url)
    if payload.ai_summary_model is not None:
        user.ai_summary_model = legacy._normalize_optional_ai_model(payload.ai_summary_model)
    if payload.ai_title_model is not None:
        user.ai_title_model = legacy._normalize_optional_ai_model(payload.ai_title_model)
    if payload.ai_tag_model is not None:
        user.ai_tag_model = legacy._normalize_optional_ai_model(payload.ai_tag_model)
    if payload.ai_story_agent_model is not None:
        user.ai_story_agent_model = legacy._normalize_optional_ai_model(payload.ai_story_agent_model)
    if payload.ai_comment_revision_model is not None:
        user.ai_comment_revision_model = legacy._normalize_optional_ai_model(payload.ai_comment_revision_model)
    if payload.ai_story_agent_visible is not None:
        user.ai_story_agent_visible = bool(payload.ai_story_agent_visible)

    db.add(user)
    db.commit()
    db.refresh(user)
    legacy.invalidate_user_cache(
        user_id=user.id,
        username=user.username,
        old_username=old_username if old_username != user.username else None,
    )
    return legacy.cache_user_payload(user)
