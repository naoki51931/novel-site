from fastapi import BackgroundTasks, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..repositories import episodes_core_repository as repo


def _optional_current_user(request: Request, db: Session):
    from .. import main as legacy

    try:
        return legacy.require_current_user(request, db)
    except Exception:
        return None


def update_episode_service(
    *,
    episode_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    payload: dict,
    db: Session,
):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    ep = legacy.get_episode_in_site_or_404(db, request, episode_id)
    was_public = not legacy.is_episode_draft(ep)
    payload_publish_mode = payload.get("publish_mode")
    payload_status = payload.get("status")
    payload_is_public = payload.get("is_public")
    payload_scheduled_publish_at_raw = payload["scheduled_publish_at"] if "scheduled_publish_at" in payload else None
    payload_scheduled_publish_at = legacy.normalize_optional_datetime(payload_scheduled_publish_at_raw)
    next_publish_mode = legacy.resolve_episode_publish_mode(
        payload_publish_mode,
        payload_status,
        payload_is_public,
        default_mode=None,
    )

    has_non_tag_change = False
    if payload.get("language") is not None and legacy.normalize_language(payload.get("language")) != legacy.normalize_language(getattr(ep, "language", None)):
        has_non_tag_change = True
    if payload.get("episode_number") is not None and int(payload.get("episode_number")) != getattr(ep, "episode_number", None):
        has_non_tag_change = True
    if payload.get("title") is not None and payload.get("title") != ep.title:
        has_non_tag_change = True
    if payload.get("body") is not None and payload.get("body") != ep.body:
        has_non_tag_change = True
    if payload.get("is_free_public") is not None and bool(payload.get("is_free_public")) != bool(getattr(ep, "is_free_public", False)):
        has_non_tag_change = True
    if (
        payload_publish_mode is not None
        or payload_status is not None
        or payload_is_public is not None
        or "scheduled_publish_at" in payload
    ):
        has_non_tag_change = True
    tag_only_update = payload.get("tag_names") is not None and not has_non_tag_change

    novel = legacy.get_novel_in_site_or_404(db, request, ep.novel_id)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    was_indexable = legacy._is_episode_indexable_for_search(ep, novel)
    is_author = novel.author_id == user.id
    if not is_author and not tag_only_update:
        legacy.logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "編集権限がありません",
            getattr(request.url, "path", None),
            getattr(user, "id", None),
            getattr(novel, "id", None),
            episode_id,
        )
        raise HTTPException(403, "編集権限がありません")

    needs_translation = False
    if is_author and "language" in payload and payload["language"] is not None:
        ep.language = legacy.normalize_language(payload["language"])
        needs_translation = True
    if is_author and "episode_number" in payload and payload["episode_number"] is not None:
        ep.episode_number = int(payload["episode_number"])
    if is_author and "title" in payload and payload["title"] is not None:
        ep.title = payload["title"]
        needs_translation = True
    if is_author and "body" in payload and payload["body"] is not None:
        ep.body = payload["body"]
        needs_translation = True
    if is_author and "is_free_public" in payload and payload["is_free_public"] is not None:
        ep.is_free_public = bool(payload["is_free_public"])

    if is_author and (next_publish_mode is not None or "scheduled_publish_at" in payload):
        if next_publish_mode is None and payload_scheduled_publish_at is not None:
            next_publish_mode = "scheduled"
        if next_publish_mode == "scheduled":
            legacy.assert_premium_user(user, "投稿予約はプレミアム会員限定です")
        if next_publish_mode is not None:
            legacy.apply_episode_publish_mode(
                ep,
                publish_mode=next_publish_mode,
                scheduled_publish_at=payload_scheduled_publish_at,
            )

    tag_names = payload.get("tag_names")
    if tag_names is not None and (is_author or tag_only_update):
        db.query(legacy.models.EpisodeTag).filter(
            legacy.models.EpisodeTag.episode_id == episode_id
        ).delete()
        tags_by_name = legacy._get_or_create_tags(db, list(tag_names or []))
        for tag in tags_by_name.values():
            db.add(legacy.models.EpisodeTag(episode_id=ep.id, tag_id=tag.id))
        needs_translation = True

    publishing_now = was_public is False and not legacy.is_episode_draft(ep)
    if publishing_now:
        needs_translation = True

    db.commit()
    db.refresh(ep)
    is_indexable = legacy._is_episode_indexable_for_search(ep, novel)
    base_origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    episode_url = f"{base_origin.rstrip('/')}/episodes/{ep.id}"
    should_notify_indexnow_update = bool(
        "language" in payload
        or "episode_number" in payload
        or "title" in payload
        or "body" in payload
        or payload_publish_mode is not None
        or payload_status is not None
        or payload_is_public is not None
        or payload.get("is_free_public") is not None
        or "scheduled_publish_at" in payload
        or payload.get("tag_names") is not None
    )
    if not was_indexable and is_indexable:
        legacy._enqueue_indexnow_urls(background_tasks=background_tasks, request=request, event="urlUpdated", urls=[episode_url])
    elif was_indexable and not is_indexable:
        legacy._enqueue_indexnow_urls(background_tasks=background_tasks, request=request, event="urlDeleted", urls=[episode_url])
    elif was_indexable and is_indexable and should_notify_indexnow_update:
        legacy._enqueue_indexnow_urls(background_tasks=background_tasks, request=request, event="urlUpdated", urls=[episode_url])

    has_translatable_content = bool(
        (ep.title or "").strip()
        or (ep.body or "").strip()
        or legacy.get_episode_tag_names(db, ep.id)
    )
    if needs_translation and not legacy.is_episode_draft(ep) and has_translatable_content:
        if legacy.AUTO_TRANSLATION_REQUIRED:
            legacy.upsert_episode_translation(
                db,
                episode=ep,
                source_language=legacy.normalize_language(getattr(ep, "language", None)),
            )
            novel_for_translation = db.query(legacy.models.Novel).filter(legacy.models.Novel.id == ep.novel_id).first()
            if novel_for_translation:
                legacy.upsert_novel_translation(
                    db,
                    novel=novel_for_translation,
                    source_language=legacy.normalize_language(getattr(novel_for_translation, "language", None)),
                    tag_names=legacy.get_novel_tag_names(db, novel_for_translation.id),
                )
            db.commit()
        else:
            background_tasks.add_task(legacy._background_upsert_episode_and_novel_translation, ep.id)
    if publishing_now:
        background_tasks.add_task(legacy._background_notify_episode_published, novel.id, ep.id, ep.site_key)
    return ep


def unschedule_episode_service(*, episode_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    legacy.assert_premium_user(user, "予約投稿の操作はプレミアム会員限定です")
    ep = legacy.get_episode_in_site_or_404(db, request, episode_id)
    novel = legacy.get_novel_in_site_or_404(db, request, ep.novel_id)
    if not novel or novel.author_id != user.id:
        raise HTTPException(403, "このエピソードを変更する権限がありません")
    ep.status = "draft"
    ep.is_public = False
    ep.scheduled_publish_at = None
    db.commit()
    db.refresh(ep)
    return {
        "episode_id": int(ep.id),
        "status": str(ep.status or "draft"),
        "is_public": bool(ep.is_public),
        "scheduled_publish_at": None,
    }


def delete_episode_service(
    *,
    episode_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session,
):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    site_key = legacy.resolve_site_key(request)
    ep = repo.find_episode_with_tags_and_illusts(db, episode_id=episode_id, site_key=site_key)
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    novel = repo.find_novel_in_site(db, novel_id=ep.novel_id, site_key=site_key)
    if not novel or novel.author_id != user.id:
        legacy.logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "削除権限がありません",
            getattr(request.url, "path", None),
            getattr(user, "id", None),
            getattr(novel, "id", None) if novel else None,
            episode_id,
        )
        raise HTTPException(403, "削除権限がありません")
    should_indexnow_delete = legacy._is_episode_indexable_for_search(ep, novel)
    base_origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    episode_url = f"{base_origin.rstrip('/')}/episodes/{episode_id}"
    file_paths: list[str] = []
    if ep.cover_image_url:
        file_paths.append(ep.cover_image_url)
    for ill in ep.illusts:
        if ill.image_url:
            file_paths.append(ill.image_url)
    db.execute(legacy.text("DELETE FROM episode_comments WHERE episode_id = :eid"), {"eid": episode_id})
    db.execute(legacy.text("DELETE FROM supports WHERE episode_id = :eid"), {"eid": episode_id})
    db.delete(ep)
    db.commit()
    if should_indexnow_delete:
        legacy._enqueue_indexnow_urls(background_tasks=background_tasks, request=request, event="urlDeleted", urls=[episode_url])
    for url in file_paths:
        rel_path = (url or "").lstrip("/")
        if not rel_path:
            continue
        file_path = legacy.os.path.join("/app", rel_path)
        try:
            if legacy.os.path.exists(file_path):
                legacy.os.remove(file_path)
        except Exception as exc:
            print("delete episode file error:", repr(exc))
    return {"ok": True, "message": "エピソードを削除しました"}


def get_episode_for_edit_service(*, episode_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    site_key = legacy.resolve_site_key(request)
    ep = repo.find_episode_with_tags_and_illusts(db, episode_id=episode_id, site_key=site_key)
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    novel = repo.find_novel_in_site(db, novel_id=ep.novel_id, site_key=site_key)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    is_author = novel.author_id == user.id
    if not is_author:
        return {
            "id": ep.id,
            "novel_id": ep.novel_id,
            "title": ep.title,
            "tags": [{"id": t.tag.id, "name": t.tag.name} for t in ep.episode_tags],
            "is_free_public": bool(getattr(ep, "is_free_public", False)),
            "can_edit_full": False,
        }
    like_count = repo.count_episode_likes(db, episode_id=episode_id)
    is_liked = repo.user_liked_episode(db, episode_id=episode_id, user_id=int(user.id))
    is_premium = legacy.is_effective_premium_user(user)
    return {
        "id": ep.id,
        "novel_id": ep.novel_id,
        "title": ep.title,
        "cover_image_url": ep.cover_image_url,
        "body": ep.body,
        "language": getattr(ep, "language", "ja"),
        "episode_number": ep.episode_number,
        "created_at": ep.created_at,
        "view_count": ep.view_count,
        "like_count": like_count,
        "is_liked": is_liked,
        "status": getattr(ep, "status", "public"),
        "is_public": bool(getattr(ep, "is_public", True)),
        "is_free_public": bool(getattr(ep, "is_free_public", False)),
        "scheduled_publish_at": ep.scheduled_publish_at,
        "published_at": ep.published_at,
        "tags": [{"id": t.tag.id, "name": t.tag.name} for t in ep.episode_tags],
        "illusts": [
            {
                "id": il.id,
                "image_url": il.image_url,
                "position": il.position,
                "caption": il.caption,
                "illust_tag": il.illust_tag,
                "meta_tags": legacy.deserialize_meta_tags(il.meta_tags),
            }
            for il in ep.illusts
        ],
        "is_premium_user": is_premium,
        "can_edit_full": True,
    }


def get_episode_service(*, episode_id: int, request: Request, db: Session):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    legacy.publish_scheduled_episodes(db, site_key=site_key)
    ep = repo.find_episode_with_tags_and_illusts(db, episode_id=episode_id, site_key=site_key)
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    user = _optional_current_user(request, db)
    novel = repo.find_novel_with_author_and_tags(db, novel_id=ep.novel_id, site_key=site_key)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    if legacy.is_episode_draft(ep):
        if not user or novel.author_id != user.id:
            raise HTTPException(404, "エピソードが存在しません")
    ep.view_count = (ep.view_count or 0) + 1
    legacy.enqueue_episode_view(ep.id)
    if not legacy.AGE_RESTRICTION_DISABLED and novel.age_limit in ("r15", "r18"):
        if not user:
            raise HTTPException(status_code=403, detail="年齢制限コンテンツです")
        age = legacy.calc_age(user.birth_date)
        if age is None:
            raise HTTPException(status_code=403, detail="生年月日が未登録のため閲覧できません")
        if novel.age_limit == "r15" and age < 15:
            raise HTTPException(status_code=403, detail="R15コンテンツを閲覧できません")
        if novel.age_limit == "r18" and age < 18:
            raise HTTPException(status_code=403, detail="R18コンテンツを閲覧できません")
    is_premium_user = legacy.is_effective_premium_user(user)
    is_free_time = legacy.is_free_reading_time()
    can_read_full = bool(getattr(ep, "is_free_public", False)) or is_premium_user or is_free_time or (user and novel.author_id == user.id)
    body_converted = ep.body if can_read_full else legacy.truncate_for_free(ep.body or "")
    next_episode = None
    prev_episode = None
    current_number = legacy.get_episode_number(ep)
    public_only = not (user and novel and novel.author_id == user.id)
    if current_number is not None:
        next_ep = repo.next_episode(db, novel_id=ep.novel_id, site_key=site_key, current_number=current_number, public_only=public_only)
        prev_ep = repo.prev_episode(db, novel_id=ep.novel_id, site_key=site_key, current_number=current_number, public_only=public_only)
        if next_ep:
            next_episode = {"id": next_ep.id, "title": next_ep.title, "episode_number": next_ep.episode_number}
        if prev_ep:
            prev_episode = {"id": prev_ep.id, "title": prev_ep.title, "episode_number": prev_ep.episode_number}
    like_count = repo.count_episode_likes(db, episode_id=episode_id)
    is_liked = bool(user and repo.user_liked_episode(db, episode_id=episode_id, user_id=int(user.id)))
    return {
        "id": ep.id,
        "novel_id": ep.novel_id,
        "author_id": novel.author_id if novel else None,
        "author_username": (novel.author.username if (novel and novel.author) else None),
        "novel_title": getattr(novel, "title", None),
        "novel_description": getattr(novel, "description", None),
        "novel_tags": [{"id": t.id, "name": t.name} for t in (novel.tags if novel else [])],
        "novel_age_limit": novel.age_limit if novel else None,
        "title": ep.title,
        "cover_image_url": ep.cover_image_url,
        "body": body_converted,
        "language": getattr(ep, "language", "ja"),
        "episode_number": ep.episode_number,
        "created_at": ep.created_at,
        "view_count": ep.view_count,
        "like_count": like_count,
        "is_liked": is_liked,
        "status": getattr(ep, "status", "public"),
        "is_public": bool(getattr(ep, "is_public", True)),
        "is_free_public": bool(getattr(ep, "is_free_public", False)),
        "tags": [{"id": t.tag.id, "name": t.tag.name} for t in ep.episode_tags],
        "illusts": [
            {
                "id": il.id,
                "image_url": il.image_url,
                "position": il.position,
                "caption": il.caption,
                "illust_tag": il.illust_tag,
                "meta_tags": legacy.deserialize_meta_tags(il.meta_tags),
            }
            for il in ep.illusts
        ],
        "is_premium_user": is_premium_user,
        "is_free_reading_time": is_free_time,
        "next_episode": next_episode,
        "prev_episode": prev_episode,
        "age_confirmation_required": legacy.AGE_RESTRICTION_DISABLED and bool(novel) and novel.age_limit == "r18",
    }


def get_episode_translation_service(*, episode_id: int, lang: str, request: Request, db: Session):
    from .. import main as legacy

    ep = legacy.get_episode_in_site_or_404(db, request, episode_id)
    if legacy.is_episode_draft(ep):
        novel = legacy.get_novel_in_site_or_404(db, request, ep.novel_id)
        user = _optional_current_user(request, db)
        if not user or novel.author_id != user.id:
            raise HTTPException(404, "エピソードが存在しません")
    language = legacy.normalize_language(lang)
    translation = repo.find_episode_translation(db, episode_id=episode_id, language=language)
    if not translation:
        raise HTTPException(404, "翻訳が存在しません")
    return {
        "episode_id": episode_id,
        "language": language,
        "title": translation.title,
        "body": translation.body,
        "tags": legacy.deserialize_tag_names(getattr(translation, "tag_names", None)),
        "created_at": translation.created_at,
        "updated_at": translation.updated_at,
    }
