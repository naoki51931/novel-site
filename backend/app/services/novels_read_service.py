from datetime import datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import author_dashboard_helpers
from ..repositories import novels_read_repository as repo


def _optional_current_user(request: Request, db: Session):
    from .. import main as legacy

    try:
        return legacy.require_current_user(request, db)
    except Exception:
        return None


def get_novel_detail_service(*, novel_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = _optional_current_user(request, db)
    site_key = legacy.resolve_site_key(request)
    novel = repo.find_novel_with_tags_and_author(db, novel_id=novel_id, site_key=site_key)
    if not novel:
        raise HTTPException(404, "小説が存在しません")

    if not novel.is_public:
        if not user or novel.author_id != user.id:
            raise HTTPException(404, "小説が存在しません")

    display_view_count = (novel.view_count or 0) + 1
    legacy.enqueue_novel_view(novel.id)
    if user:
        legacy.record_user_view_history(
            db,
            user_id=int(user.id),
            target_type="novel",
            target_id=int(novel.id),
            site_key=site_key,
        )
        db.commit()

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

    is_liked = bool(user and repo.user_liked_novel(db, novel_id=novel.id, user_id=int(user.id)))
    is_favorited = bool(user and repo.user_favorited_novel(db, novel_id=novel.id, user_id=int(user.id)))

    is_premium_user = legacy.is_effective_premium_user(user)
    is_free_time = legacy.is_free_reading_time()
    can_read_full = is_premium_user or is_free_time or (user and novel.author_id == user.id)

    episode_q = repo.list_novel_episodes_with_tags(db, novel_id=novel_id, site_key=site_key)
    if user and novel.author_id == user.id:
        episodes = episode_q.order_by(legacy.models.Episode.episode_number).all()
    else:
        episodes = (
            episode_q.filter(legacy.models.Episode.status == "public")
            .filter(legacy.models.Episode.is_public == True)
            .order_by(legacy.models.Episode.episode_number)
            .all()
        )

    episode_updated_map: dict[int, datetime] = {}
    episode_ids = [int(ep.id) for ep in episodes if int(getattr(ep, "id", 0) or 0) > 0]
    if episode_ids and author_dashboard_helpers._table_has_column(db, "episodes", "updated_at"):
        updated_rows = db.execute(
            legacy.text(
                """
                SELECT id, updated_at
                FROM episodes
                WHERE id IN :episode_ids
                """
            ).bindparams(legacy.bindparam("episode_ids", expanding=True)),
            {"episode_ids": episode_ids},
        ).fetchall()
        for row in updated_rows:
            mapping = getattr(row, "_mapping", {})
            eid = int(mapping.get("id") or 0)
            updated_at = mapping.get("updated_at")
            if eid > 0 and isinstance(updated_at, datetime):
                episode_updated_map[eid] = updated_at

    tags = [{"id": novel_tag.tag.id, "name": novel_tag.tag.name} for novel_tag in novel.novel_tags]
    public_only = not (user and novel.author_id == user.id)
    total_char_count = legacy.get_novel_char_counts(db, [novel.id], public_only=public_only).get(novel.id, 0)

    return {
        "id": novel.id,
        "title": novel.title,
        "description": novel.description,
        "language": getattr(novel, "language", "ja"),
        "created_at": novel.created_at,
        "author_id": novel.author_id,
        "author_username": novel.author.username if novel.author else None,
        "view_count": display_view_count,
        "like_count": novel.like_count or 0,
        "is_liked": is_liked,
        "is_favorited": is_favorited,
        "is_premium_user": is_premium_user,
        "is_free_reading_time": is_free_time,
        "age_limit": novel.age_limit,
        "is_ai_generated": novel.is_ai_generated,
        "creative_type": getattr(novel, "creative_type", "original"),
        "fanfic_source_title": getattr(novel, "fanfic_source_title", None),
        "fanfic_characters": getattr(novel, "fanfic_characters", None),
        "fanfic_coupling": getattr(novel, "fanfic_coupling", None),
        "fanfic_notes": getattr(novel, "fanfic_notes", None),
        "series_name": getattr(novel, "series_name", None),
        "series_order": getattr(novel, "series_order", None),
        "is_public": bool(getattr(novel, "is_public", True)),
        "status": getattr(novel, "status", "public"),
        "cover_image_url": getattr(novel, "cover_image_path", None)
        or (episodes[0].cover_image_url if episodes and getattr(episodes[0], "cover_image_url", None) else None),
        "can_edit_full": bool(user and novel.author_id == user.id),
        "age_confirmation_required": legacy.AGE_RESTRICTION_DISABLED and novel.age_limit == "r18",
        "total_char_count": total_char_count,
        "tags": tags,
        "episodes": [
            {
                "id": ep.id,
                "title": ep.title,
                "cover_image_url": ep.cover_image_url,
                "number": legacy.get_episode_number(ep),
                "is_free_public": bool(getattr(ep, "is_free_public", False)),
                "body": ep.body if (bool(getattr(ep, "is_free_public", False)) or can_read_full) else legacy.truncate_for_free(ep.body or ""),
                "created_at": ep.created_at,
                "updated_at": episode_updated_map.get(int(ep.id)),
                "tags": [{"id": t.tag.id, "name": t.tag.name} for t in ep.episode_tags],
            }
            for ep in episodes
        ],
    }


def get_novel_translation_service(*, novel_id: int, lang: str, request: Request, db: Session):
    from .. import main as legacy

    novel = legacy.get_novel_in_site_or_404(db, request, novel_id)
    if legacy.is_novel_draft(novel):
        user = _optional_current_user(request, db)
        if not user or novel.author_id != user.id:
            raise HTTPException(404, "小説が存在しません")
    language = legacy.normalize_language(lang)
    translation = repo.find_novel_translation(db, novel_id=novel_id, language=language)
    if not translation:
        raise HTTPException(404, "翻訳が存在しません")
    return {
        "novel_id": novel_id,
        "language": language,
        "title": translation.title,
        "description": translation.description,
        "tags": legacy.deserialize_tag_names(translation.tag_names),
        "created_at": translation.created_at,
        "updated_at": translation.updated_at,
    }


def list_episodes_service(*, novel_id: int, request: Request, db: Session):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    legacy.publish_scheduled_episodes(db, site_key=site_key)
    novel = repo.find_novel_with_tags_and_author(db, novel_id=novel_id, site_key=site_key)
    if not novel:
        raise HTTPException(404, "小説が存在しません")

    user = _optional_current_user(request, db)
    is_premium_user = legacy.is_effective_premium_user(user)
    is_free_time = legacy.is_free_reading_time()
    can_read_full = is_premium_user or is_free_time or (user and novel.author_id == user.id)

    base_q = repo.list_novel_episodes_with_tags(db, novel_id=novel_id, site_key=site_key)
    if user and novel.author_id == user.id:
        episodes = base_q.order_by(legacy.models.Episode.episode_number).all()
    else:
        episodes = (
            base_q.filter(legacy.models.Episode.status == "public")
            .filter(legacy.models.Episode.is_public == True)
            .order_by(legacy.models.Episode.episode_number)
            .all()
        )

    return [
        {
            "id": ep.id,
            "title": ep.title,
            "cover_image_url": ep.cover_image_url,
            "number": legacy.get_episode_number(ep),
            "is_free_public": bool(getattr(ep, "is_free_public", False)),
            "body": ep.body if (bool(getattr(ep, "is_free_public", False)) or can_read_full) else legacy.truncate_for_free(ep.body or ""),
            "created_at": ep.created_at,
        }
        for ep in episodes
    ]
