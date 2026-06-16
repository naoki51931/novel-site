from functools import partial

import jwt
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from .. import models
from ..repositories import view_history_repository as repo
from ..runtime_config import ALGORITHM, SECRET_KEY, SITE_HOST_MAP, SITE_KEY_ALLOWED, SITE_KEY_DEFAULT
from ..schemas_api import (
    AIPublicChatViewHistoryItemOut,
    NovelViewHistoryItemOut,
    NovelViewHistoryListOut,
)
from ..site_helpers import normalize_site_key, resolve_site_key
from ..user_access_helpers import record_user_view_history, require_current_user


normalize_site_key = partial(
    normalize_site_key,
    site_key_default=SITE_KEY_DEFAULT,
    site_key_allowed=SITE_KEY_ALLOWED,
)
resolve_site_key = partial(
    resolve_site_key,
    normalize_site_key=normalize_site_key,
    site_key_default=SITE_KEY_DEFAULT,
    site_host_map=SITE_HOST_MAP,
)
require_current_user = partial(
    require_current_user,
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
    jwt_module=jwt,
    models=models,
    http_exception_cls=HTTPException,
)
record_user_view_history = partial(
    record_user_view_history,
    normalize_site_key=normalize_site_key,
    models=models,
)


def _require_current_user(request: Request, db: Session):
    return require_current_user(request, db)


def record_my_view_history_service(*, payload, request: Request, db: Session):
    user = _require_current_user(request, db)
    target_type = str(payload.target_type or "").strip()
    target_id = int(payload.target_id or 0)
    if target_id <= 0:
        raise HTTPException(400, "target_id が不正です")
    site_key = normalize_site_key(payload.site_key or resolve_site_key(request))

    if target_type == "novel":
        novel = repo.find_novel_in_site(db, novel_id=target_id, site_key=site_key)
        if not novel:
            raise HTTPException(404, "小説が存在しません")
    elif target_type == "ai_public_character":
        character = repo.find_public_ai_chat_character(db, character_id=target_id)
        if not character:
            raise HTTPException(404, "公開チャットが存在しません")
    else:
        raise HTTPException(400, "target_type が不正です")

    record_user_view_history(
        db,
        user_id=int(user.id),
        target_type=target_type,
        target_id=target_id,
        site_key=site_key,
    )
    db.commit()
    return {"ok": True}


def list_my_novel_view_history_service(*, request: Request, db: Session, limit: int, offset: int):
    user = _require_current_user(request, db)
    site_key = resolve_site_key(request)
    rows = repo.list_user_novel_view_history(
        db,
        user_id=int(user.id),
        site_key=site_key,
        limit=limit,
        offset=offset,
    )
    total = repo.count_user_novel_view_history(db, user_id=int(user.id), site_key=site_key)
    return NovelViewHistoryListOut(
        items=[
            NovelViewHistoryItemOut(
                target_id=int(hist.target_id),
                viewed_at=hist.last_viewed_at,
                view_count=int(hist.view_count or 0),
                site_key=str(hist.site_key or "main"),
                title=str(novel.title or "") if novel else None,
                author_username=str(username or "") if username else None,
                age_limit=str(getattr(novel, "age_limit", "") or "") if novel else None,
            )
            for hist, novel, username in rows
        ],
        total=int(total),
        limit=int(limit),
        offset=int(offset),
    )


def list_my_public_ai_chat_view_history_service(*, request: Request, db: Session, limit: int):
    user = _require_current_user(request, db)
    site_key = resolve_site_key(request)
    rows = repo.list_user_public_ai_chat_view_history(
        db,
        user_id=int(user.id),
        site_key=site_key,
        limit=limit,
    )
    return [
        AIPublicChatViewHistoryItemOut(
            target_id=int(hist.target_id),
            viewed_at=hist.last_viewed_at,
            view_count=int(hist.view_count or 0),
            site_key=str(hist.site_key or "main"),
            character_name=str(character.name or "") if character else None,
            author_username=str(username or "") if username else None,
            is_public=bool(getattr(character, "is_public", False)) if character else False,
            is_r18=bool(getattr(character, "is_r18", False)) if character else False,
        )
        for hist, character, username in rows
    ]
