from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from ..repositories import view_history_repository as repo


def _require_current_user(request: Request, db: Session):
    from .. import main as legacy

    return legacy.require_current_user(request, db)


def record_my_view_history_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    user = _require_current_user(request, db)
    target_type = str(payload.target_type or "").strip()
    target_id = int(payload.target_id or 0)
    if target_id <= 0:
        raise HTTPException(400, "target_id が不正です")
    site_key = legacy.normalize_site_key(payload.site_key or legacy.resolve_site_key(request))

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

    legacy.record_user_view_history(
        db,
        user_id=int(user.id),
        target_type=target_type,
        target_id=target_id,
        site_key=site_key,
    )
    db.commit()
    return {"ok": True}


def list_my_novel_view_history_service(*, request: Request, db: Session, limit: int, offset: int):
    from .. import main as legacy

    user = _require_current_user(request, db)
    site_key = legacy.resolve_site_key(request)
    rows = repo.list_user_novel_view_history(
        db,
        user_id=int(user.id),
        site_key=site_key,
        limit=limit,
        offset=offset,
    )
    total = repo.count_user_novel_view_history(db, user_id=int(user.id), site_key=site_key)
    return legacy.NovelViewHistoryListOut(
        items=[
            legacy.NovelViewHistoryItemOut(
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
    from .. import main as legacy

    user = _require_current_user(request, db)
    site_key = legacy.resolve_site_key(request)
    rows = repo.list_user_public_ai_chat_view_history(
        db,
        user_id=int(user.id),
        site_key=site_key,
        limit=limit,
    )
    return [
        legacy.AIPublicChatViewHistoryItemOut(
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
