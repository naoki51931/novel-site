import logging
from functools import partial

import jwt
from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models
from ..cache_helpers import invalidate_public_list_caches
from ..content_helpers import normalize_language
from ..notification_helpers import (
    notify_followers_author_new_novel,
    notify_recommended_users_new_novel,
    notify_tag_followers_new_novel,
)
from ..oauth_helpers import _request_origin
from ..public_indexing_helpers import _enqueue_indexnow_urls, _is_novel_indexable_for_search
from ..read_time import sync_novel_estimated_read_minutes
from ..repositories import novels_write_repository as repo
from ..runtime_config import (
    ALGORITHM,
    AUTO_TRANSLATION_REQUIRED,
    FRONTEND_ORIGIN,
    SECRET_KEY,
    SITE_HOST_MAP,
    SITE_KEY_ALLOWED,
    SITE_KEY_DEFAULT,
)
from ..site_helpers import normalize_site_key as normalize_site_key_impl, resolve_site_key as resolve_site_key_impl
from ..translation_helpers import _background_upsert_novel_translation, upsert_novel_translation
from ..user_access_helpers import require_current_user as require_current_user_impl

logger = logging.getLogger("uvicorn.error")
normalize_site_key = partial(
    normalize_site_key_impl,
    site_key_default=SITE_KEY_DEFAULT,
    site_key_allowed=SITE_KEY_ALLOWED,
)
resolve_site_key = partial(
    resolve_site_key_impl,
    normalize_site_key=normalize_site_key,
    site_key_default=SITE_KEY_DEFAULT,
    site_host_map=SITE_HOST_MAP,
)
require_current_user = partial(
    require_current_user_impl,
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
    jwt_module=jwt,
    models=models,
    http_exception_cls=HTTPException,
)


def get_novel_tag_names(db: Session, novel_id: int) -> list[str]:
    rows = (
        db.query(models.Tag.name)
        .join(models.NovelTag, models.NovelTag.tag_id == models.Tag.id)
        .filter(models.NovelTag.novel_id == novel_id)
        .order_by(models.Tag.name.asc(), models.Tag.id.asc())
        .all()
    )
    return [str(name or "").strip() for (name,) in rows if str(name or "").strip()]


def create_novel_service(
    *,
    payload,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session,
):
    user = require_current_user(request, db)
    site_key = resolve_site_key(request)
    language = normalize_language(getattr(payload, "language", None))
    fanfic_source_title = str(getattr(payload, "fanfic_source_title", "") or "").strip()[:120] or None
    fanfic_characters = str(getattr(payload, "fanfic_characters", "") or "").strip()[:4000] or None
    fanfic_coupling = str(getattr(payload, "fanfic_coupling", "") or "").strip()[:120] or None
    fanfic_notes = str(getattr(payload, "fanfic_notes", "") or "").strip()[:4000] or None
    series_name = str(getattr(payload, "series_name", "") or "").strip()[:120] or None
    raw_series_order = getattr(payload, "series_order", None)
    series_order = int(raw_series_order) if raw_series_order is not None else None

    novel = repo.create_novel(
        db,
        title=payload.title,
        description=payload.description,
        author_id=user.id,
        is_ai_generated=getattr(payload, "is_ai_generated", False),
        age_limit=getattr(payload, "age_limit", "all"),
        creative_type=getattr(payload, "creative_type", "original"),
        like_count=0,
        is_public=getattr(payload, "is_public", True),
        language=language,
        site_key=site_key,
        fanfic_source_title=fanfic_source_title,
        fanfic_characters=fanfic_characters,
        fanfic_coupling=fanfic_coupling,
        fanfic_notes=fanfic_notes,
        series_name=series_name,
        series_order=series_order,
        estimated_read_minutes=0,
    )
    db.commit()
    db.refresh(novel)

    normalized_tag_names = repo.replace_novel_tags(db, novel_id=novel.id, tag_names=getattr(payload, "tag_names", []) or [])
    db.commit()
    db.refresh(novel)

    if AUTO_TRANSLATION_REQUIRED:
        upsert_novel_translation(
            db,
            novel=novel,
            source_language=language,
            tag_names=normalized_tag_names,
        )
        db.commit()
        db.refresh(novel)
    else:
        background_tasks.add_task(_background_upsert_novel_translation, novel.id)

    if bool(getattr(novel, "is_public", True)):
        notify_recommended_users_new_novel(db, novel=novel)
        notify_followers_author_new_novel(db, novel=novel)
        notify_tag_followers_new_novel(db, novel=novel)
    if _is_novel_indexable_for_search(novel):
        base_origin = _request_origin(request, fallback=FRONTEND_ORIGIN.rstrip("/"))
        _enqueue_indexnow_urls(
            background_tasks=background_tasks,
            request=request,
            event="urlUpdated",
            urls=[f"{base_origin.rstrip('/')}/novels/{novel.id}"],
        )
    invalidate_public_list_caches()
    return novel


def update_novel_service(
    *,
    novel_id: int,
    payload,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session,
):
    user = require_current_user(request, db)
    novel = repo.find_novel_in_site(db, novel_id=novel_id, site_key=resolve_site_key(request))
    if not novel:
        raise HTTPException(404, "小説が存在しません")

    was_public = bool(getattr(novel, "is_public", True))
    was_indexable = _is_novel_indexable_for_search(novel)
    has_non_tag_change = False
    if payload.language is not None and normalize_language(payload.language) != normalize_language(
        getattr(novel, "language", None)
    ):
        has_non_tag_change = True
    if payload.title is not None and payload.title != novel.title:
        has_non_tag_change = True
    if payload.description is not None and payload.description != novel.description:
        has_non_tag_change = True
    if payload.age_limit is not None and payload.age_limit != getattr(novel, "age_limit", None):
        has_non_tag_change = True
    if payload.is_ai_generated is not None and payload.is_ai_generated != getattr(novel, "is_ai_generated", None):
        has_non_tag_change = True
    if payload.creative_type is not None and payload.creative_type != getattr(novel, "creative_type", None):
        has_non_tag_change = True
    if payload.is_public is not None and payload.is_public != getattr(novel, "is_public", None):
        has_non_tag_change = True
    if payload.fanfic_source_title is not None and payload.fanfic_source_title != getattr(novel, "fanfic_source_title", None):
        has_non_tag_change = True
    if payload.fanfic_characters is not None and payload.fanfic_characters != getattr(novel, "fanfic_characters", None):
        has_non_tag_change = True
    if payload.fanfic_coupling is not None and payload.fanfic_coupling != getattr(novel, "fanfic_coupling", None):
        has_non_tag_change = True
    if payload.fanfic_notes is not None and payload.fanfic_notes != getattr(novel, "fanfic_notes", None):
        has_non_tag_change = True
    if payload.series_name is not None and payload.series_name != getattr(novel, "series_name", None):
        has_non_tag_change = True
    if payload.series_order is not None and int(payload.series_order) != int(getattr(novel, "series_order", 0) or 0):
        has_non_tag_change = True

    tag_only_update = payload.tag_names is not None and not has_non_tag_change
    if hasattr(novel, "is_public") and not novel.is_public:
        if (not user) or (novel.author_id != user.id and not tag_only_update):
            raise HTTPException(404, "小説が存在しません")

    is_author = novel.author_id == user.id
    if not is_author and not tag_only_update:
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "編集権限がありません",
            getattr(request.url, "path", None),
            getattr(user, "id", None),
            novel_id,
            None,
        )
        raise HTTPException(403, "編集権限がありません")

    needs_translation = False
    if is_author and payload.language is not None:
        novel.language = normalize_language(payload.language)
        needs_translation = True
    if is_author and payload.title is not None:
        novel.title = payload.title
        needs_translation = True
    if is_author and payload.description is not None:
        novel.description = payload.description
        needs_translation = True
    if is_author and payload.age_limit is not None:
        novel.age_limit = payload.age_limit
    if is_author and payload.is_ai_generated is not None:
        novel.is_ai_generated = payload.is_ai_generated
    if is_author and payload.is_public is not None:
        novel.is_public = payload.is_public
    if is_author and payload.creative_type is not None:
        novel.creative_type = payload.creative_type
    if is_author and payload.fanfic_source_title is not None:
        novel.fanfic_source_title = str(payload.fanfic_source_title or "").strip()[:120] or None
    if is_author and payload.fanfic_characters is not None:
        novel.fanfic_characters = str(payload.fanfic_characters or "").strip()[:4000] or None
    if is_author and payload.fanfic_coupling is not None:
        novel.fanfic_coupling = str(payload.fanfic_coupling or "").strip()[:120] or None
    if is_author and payload.fanfic_notes is not None:
        novel.fanfic_notes = str(payload.fanfic_notes or "").strip()[:4000] or None
    if is_author and payload.series_name is not None:
        novel.series_name = str(payload.series_name or "").strip()[:120] or None
    if is_author and payload.series_order is not None:
        novel.series_order = int(payload.series_order)

    updated_tag_names: list[str] | None = None
    if payload.tag_names is not None and (is_author or tag_only_update):
        updated_tag_names = repo.replace_novel_tags(db, novel_id=novel_id, tag_names=payload.tag_names)
        needs_translation = True
    sync_novel_estimated_read_minutes(db, novel_id=novel.id, models=models)

    if needs_translation:
        if AUTO_TRANSLATION_REQUIRED:
            tag_names_for_translation = (
                updated_tag_names if updated_tag_names is not None else get_novel_tag_names(db, novel.id)
            )
            upsert_novel_translation(
                db,
                novel=novel,
                source_language=normalize_language(getattr(novel, "language", None)),
                tag_names=tag_names_for_translation,
            )
        else:
            background_tasks.add_task(_background_upsert_novel_translation, novel.id)

    db.commit()
    db.refresh(novel)
    is_indexable = _is_novel_indexable_for_search(novel)
    base_origin = _request_origin(request, fallback=FRONTEND_ORIGIN.rstrip("/"))
    novel_url = f"{base_origin.rstrip('/')}/novels/{novel.id}"
    should_notify_indexnow_update = bool(has_non_tag_change or payload.tag_names is not None)
    if not was_indexable and is_indexable:
        _enqueue_indexnow_urls(background_tasks=background_tasks, request=request, event="urlUpdated", urls=[novel_url])
    elif was_indexable and not is_indexable:
        _enqueue_indexnow_urls(background_tasks=background_tasks, request=request, event="urlDeleted", urls=[novel_url])
    elif was_indexable and is_indexable and should_notify_indexnow_update:
        _enqueue_indexnow_urls(background_tasks=background_tasks, request=request, event="urlUpdated", urls=[novel_url])
    if (not was_public) and bool(getattr(novel, "is_public", True)):
        notify_recommended_users_new_novel(db, novel=novel)
        notify_followers_author_new_novel(db, novel=novel)
        notify_tag_followers_new_novel(db, novel=novel)
    invalidate_public_list_caches()
    return novel


def delete_novel_service(
    *,
    novel_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session,
):
    user = require_current_user(request, db)
    site_key = resolve_site_key(request)
    novel = repo.find_novel_in_site(db, novel_id=novel_id, site_key=site_key)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    if novel.author_id != user.id:
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "削除権限がありません",
            getattr(request.url, "path", None),
            getattr(user, "id", None),
            novel_id,
            None,
        )
        raise HTTPException(403, "削除権限がありません")

    should_indexnow_delete = _is_novel_indexable_for_search(novel)
    base_origin = _request_origin(request, fallback=FRONTEND_ORIGIN.rstrip("/"))
    novel_url = f"{base_origin.rstrip('/')}/novels/{novel_id}"
    repo.delete_novel_with_children(db, novel_id=novel_id, site_key=site_key)
    db.commit()
    if should_indexnow_delete:
        _enqueue_indexnow_urls(
            background_tasks=background_tasks,
            request=request,
            event="urlDeleted",
            urls=[novel_url],
        )
    invalidate_public_list_caches()
    return {"ok": True}
