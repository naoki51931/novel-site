import logging
from functools import partial

import jwt
from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models
from ..content_helpers import normalize_illust_tag, normalize_language, normalize_meta_tags, serialize_meta_tags
from ..episode_publish_helpers import (
    apply_episode_publish_mode,
    is_episode_draft,
    normalize_optional_datetime,
    resolve_episode_publish_mode,
)
from ..legacy_helpers import get_novel_tag_names
from ..notification_helpers import _background_notify_episode_published
from ..oauth_helpers import _request_origin
from ..public_indexing_helpers import _enqueue_indexnow_urls, _is_episode_indexable_for_search
from ..read_time import sync_episode_estimated_read_minutes, sync_novel_estimated_read_minutes
from ..repositories import episodes_write_repository as repo
from ..runtime_config import (
    ALGORITHM,
    AUTO_TRANSLATION_REQUIRED,
    FORCE_ALL_PREMIUM,
    FORCE_PREMIUM_USERNAMES,
    FRONTEND_ORIGIN,
    SECRET_KEY,
    SITE_HOST_MAP,
    SITE_KEY_ALLOWED,
    SITE_KEY_DEFAULT,
)
from ..site_helpers import normalize_site_key as normalize_site_key_impl, resolve_site_key as resolve_site_key_impl
from ..translation_helpers import _background_upsert_episode_and_novel_translation, upsert_episode_translation, upsert_novel_translation
from ..user_access_helpers import (
    assert_premium_user as assert_premium_user_impl,
    is_effective_premium_user as is_effective_premium_user_impl,
    is_force_premium_username as is_force_premium_username_impl,
    require_current_user as require_current_user_impl,
)

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
assert_premium_user = partial(
    assert_premium_user_impl,
    is_effective_premium_user=partial(
        is_effective_premium_user_impl,
        force_all_premium=FORCE_ALL_PREMIUM,
        is_force_premium_username=partial(
            is_force_premium_username_impl,
            force_premium_usernames=FORCE_PREMIUM_USERNAMES,
        ),
    ),
    http_exception_cls=HTTPException,
)


def _get_or_create_tags(db: Session, names: list[str]) -> dict[str, models.Tag]:
    normalized_names: list[str] = []
    for raw in names:
        name = (raw or "").strip()
        if name and name not in normalized_names:
            normalized_names.append(name)
    if not normalized_names:
        return {}
    existing = db.query(models.Tag).filter(models.Tag.name.in_(normalized_names)).all()
    by_name = {str(tag.name): tag for tag in existing if tag and getattr(tag, "name", None)}
    for name in normalized_names:
        if name in by_name:
            continue
        tag = models.Tag(name=name)
        db.add(tag)
        db.flush()
        by_name[name] = tag
    return by_name


def create_episode_service(
    *,
    novel_id: int,
    payload,
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
            "追加権限がありません",
            getattr(request.url, "path", None),
            getattr(user, "id", None),
            novel_id,
            None,
        )
        raise HTTPException(403, "追加権限がありません")

    publish_mode = resolve_episode_publish_mode(
        getattr(payload, "publish_mode", None),
        getattr(payload, "status", None),
        None,
        default_mode="public",
    )
    if publish_mode is None:
        publish_mode = "public"
    if publish_mode == "scheduled":
        assert_premium_user(user, "投稿予約はプレミアム会員限定です")
    scheduled_publish_at = normalize_optional_datetime(
        getattr(payload, "scheduled_publish_at", None)
    )
    language = normalize_language(
        getattr(payload, "language", None) or getattr(novel, "language", None)
    )

    episode = repo.create_episode(
        db,
        novel_id=novel_id,
        title=payload.title,
        body=payload.body,
        cover_image_url=payload.cover_image_url,
        episode_number=payload.episode_number,
        is_free_public=bool(getattr(payload, "is_free_public", False)),
        language=language,
        site_key=site_key,
    )
    sync_episode_estimated_read_minutes(episode)
    sync_novel_estimated_read_minutes(db, novel_id=novel_id, models=models)
    apply_episode_publish_mode(
        episode,
        publish_mode=publish_mode,
        scheduled_publish_at=scheduled_publish_at,
    )

    for illust in payload.illusts:
        repo.add_episode_illust(
            db,
            episode_id=episode.id,
            image_url=illust.image_url,
            position=illust.position,
            caption=illust.caption,
            illust_tag=normalize_illust_tag(getattr(illust, "illust_tag", None)),
            meta_tags=serialize_meta_tags(
                normalize_meta_tags(getattr(illust, "meta_tags", None))
            ),
        )

    tags_by_name = _get_or_create_tags(db, list(getattr(payload, "tag_names", None) or []))
    for tag in tags_by_name.values():
        repo.add_episode_tag(db, episode_id=episode.id, tag_id=tag.id)

    has_translatable_content = bool(
        (episode.title or "").strip()
        or (episode.body or "").strip()
        or list(getattr(payload, "tag_names", None) or [])
    )
    needs_translation = has_translatable_content and not is_episode_draft(episode)
    db.commit()
    db.refresh(episode)
    is_indexable_episode = _is_episode_indexable_for_search(episode, novel)
    if needs_translation:
        if AUTO_TRANSLATION_REQUIRED:
            upsert_episode_translation(db, episode=episode, source_language=language)
            novel_for_translation = db.query(models.Novel).filter(models.Novel.id == episode.novel_id).first()
            if novel_for_translation:
                upsert_novel_translation(
                    db,
                    novel=novel_for_translation,
                    source_language=normalize_language(getattr(novel_for_translation, "language", None)),
                    tag_names=get_novel_tag_names(db, novel_for_translation.id),
                )
            db.commit()
        else:
            background_tasks.add_task(_background_upsert_episode_and_novel_translation, episode.id)
    if publish_mode == "public":
        background_tasks.add_task(_background_notify_episode_published, novel_id, episode.id, site_key)
    if is_indexable_episode:
        base_origin = _request_origin(request, fallback=FRONTEND_ORIGIN.rstrip("/"))
        _enqueue_indexnow_urls(
            background_tasks=background_tasks,
            request=request,
            event="urlUpdated",
            urls=[f"{base_origin.rstrip('/')}/episodes/{episode.id}"],
        )
    return episode
