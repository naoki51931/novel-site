from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy.orm import Session

from ..repositories import novels_write_repository as repo


def update_novel_service(
    *,
    novel_id: int,
    payload,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session,
):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    novel = repo.find_novel_in_site(db, novel_id=novel_id, site_key=legacy.resolve_site_key(request))
    if not novel:
        raise HTTPException(404, "小説が存在しません")

    was_public = bool(getattr(novel, "is_public", True))
    was_indexable = legacy._is_novel_indexable_for_search(novel)
    has_non_tag_change = False
    if payload.language is not None and legacy.normalize_language(payload.language) != legacy.normalize_language(
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
        legacy.logger.warning(
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
        novel.language = legacy.normalize_language(payload.language)
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
        repo.delete_novel_tags(db, novel_id=novel_id)
        updated_tag_names = []
        for tag_name in payload.tag_names:
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            updated_tag_names.append(tag_name)
            tag = repo.find_tag_by_name(db, tag_name=tag_name)
            if not tag:
                tag = repo.create_tag(db, tag_name=tag_name)
            repo.add_novel_tag(db, novel_id=novel.id, tag_id=tag.id)
        needs_translation = True

    if needs_translation:
        if legacy.AUTO_TRANSLATION_REQUIRED:
            tag_names_for_translation = (
                updated_tag_names if updated_tag_names is not None else legacy.get_novel_tag_names(db, novel.id)
            )
            legacy.upsert_novel_translation(
                db,
                novel=novel,
                source_language=legacy.normalize_language(getattr(novel, "language", None)),
                tag_names=tag_names_for_translation,
            )
        else:
            background_tasks.add_task(legacy._background_upsert_novel_translation, novel.id)

    db.commit()
    db.refresh(novel)
    is_indexable = legacy._is_novel_indexable_for_search(novel)
    base_origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    novel_url = f"{base_origin.rstrip('/')}/novels/{novel.id}"
    should_notify_indexnow_update = bool(has_non_tag_change or payload.tag_names is not None)
    if not was_indexable and is_indexable:
        legacy._enqueue_indexnow_urls(background_tasks=background_tasks, request=request, event="urlUpdated", urls=[novel_url])
    elif was_indexable and not is_indexable:
        legacy._enqueue_indexnow_urls(background_tasks=background_tasks, request=request, event="urlDeleted", urls=[novel_url])
    elif was_indexable and is_indexable and should_notify_indexnow_update:
        legacy._enqueue_indexnow_urls(background_tasks=background_tasks, request=request, event="urlUpdated", urls=[novel_url])
    if (not was_public) and bool(getattr(novel, "is_public", True)):
        legacy.notify_recommended_users_new_novel(db, novel=novel)
        legacy.notify_followers_author_new_novel(db, novel=novel)
        legacy.notify_tag_followers_new_novel(db, novel=novel)
    legacy.invalidate_public_list_caches()
    return novel


def delete_novel_service(
    *,
    novel_id: int,
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
            "削除権限がありません",
            getattr(request.url, "path", None),
            getattr(user, "id", None),
            novel_id,
            None,
        )
        raise HTTPException(403, "削除権限がありません")

    should_indexnow_delete = legacy._is_novel_indexable_for_search(novel)
    base_origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    novel_url = f"{base_origin.rstrip('/')}/novels/{novel_id}"
    repo.delete_novel_with_children(db, novel_id=novel_id, site_key=site_key)
    db.commit()
    if should_indexnow_delete:
        legacy._enqueue_indexnow_urls(
            background_tasks=background_tasks,
            request=request,
            event="urlDeleted",
            urls=[novel_url],
        )
    legacy.invalidate_public_list_caches()
    return {"ok": True}
