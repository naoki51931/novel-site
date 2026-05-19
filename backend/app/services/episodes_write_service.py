from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy.orm import Session

from ..repositories import episodes_write_repository as repo


def create_episode_service(
    *,
    novel_id: int,
    payload,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session,
):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    site_key = legacy.resolve_site_key(request)
    novel = repo.find_novel_in_site(db, novel_id=novel_id, site_key=site_key)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    if novel.author_id != user.id:
        legacy.logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "追加権限がありません",
            getattr(request.url, "path", None),
            getattr(user, "id", None),
            novel_id,
            None,
        )
        raise HTTPException(403, "追加権限がありません")

    publish_mode = legacy.resolve_episode_publish_mode(
        getattr(payload, "publish_mode", None),
        getattr(payload, "status", None),
        None,
        default_mode="public",
    )
    if publish_mode is None:
        publish_mode = "public"
    if publish_mode == "scheduled":
        legacy.assert_premium_user(user, "投稿予約はプレミアム会員限定です")
    scheduled_publish_at = legacy.normalize_optional_datetime(
        getattr(payload, "scheduled_publish_at", None)
    )
    language = legacy.normalize_language(
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
    legacy.apply_episode_publish_mode(
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
            illust_tag=legacy.normalize_illust_tag(getattr(illust, "illust_tag", None)),
            meta_tags=legacy.serialize_meta_tags(
                legacy.normalize_meta_tags(getattr(illust, "meta_tags", None))
            ),
        )

    tags_by_name = legacy._get_or_create_tags(db, list(getattr(payload, "tag_names", None) or []))
    for tag in tags_by_name.values():
        repo.add_episode_tag(db, episode_id=episode.id, tag_id=tag.id)

    has_translatable_content = bool(
        (episode.title or "").strip()
        or (episode.body or "").strip()
        or list(getattr(payload, "tag_names", None) or [])
    )
    needs_translation = has_translatable_content and not legacy.is_episode_draft(episode)
    db.commit()
    db.refresh(episode)
    is_indexable_episode = legacy._is_episode_indexable_for_search(episode, novel)
    if needs_translation:
        if legacy.AUTO_TRANSLATION_REQUIRED:
            legacy.upsert_episode_translation(db, episode=episode, source_language=language)
            novel_for_translation = db.query(legacy.models.Novel).filter(legacy.models.Novel.id == episode.novel_id).first()
            if novel_for_translation:
                legacy.upsert_novel_translation(
                    db,
                    novel=novel_for_translation,
                    source_language=legacy.normalize_language(getattr(novel_for_translation, "language", None)),
                    tag_names=legacy.get_novel_tag_names(db, novel_for_translation.id),
                )
            db.commit()
        else:
            background_tasks.add_task(legacy._background_upsert_episode_and_novel_translation, episode.id)
    if publish_mode == "public":
        background_tasks.add_task(legacy._background_notify_episode_published, novel_id, episode.id, site_key)
    if is_indexable_episode:
        base_origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
        legacy._enqueue_indexnow_urls(
            background_tasks=background_tasks,
            request=request,
            event="urlUpdated",
            urls=[f"{base_origin.rstrip('/')}/episodes/{episode.id}"],
        )
    return episode
