from functools import partial

import jwt
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import author_dashboard_helpers, models
from ..cache_helpers import enqueue_novel_view
from ..content_helpers import deserialize_tag_names, get_novel_char_counts, normalize_language
from ..episode_publish_helpers import is_novel_draft, publish_scheduled_episodes
from ..payout_reading_helpers import get_episode_number, is_free_reading_time, is_jp_holiday, truncate_for_free
from ..read_time import estimated_read_minutes_for_char_count, estimated_read_minutes_for_text
from ..repositories import novels_read_repository as repo
from ..runtime_config import (
    AGE_RESTRICTION_DISABLED,
    ALGORITHM,
    FORCE_ALL_PREMIUM,
    FORCE_PREMIUM_USERNAMES,
    SECRET_KEY,
    SITE_HOST_MAP,
    SITE_KEY_ALLOWED,
    SITE_KEY_DEFAULT,
)
from ..site_helpers import (
    get_novel_in_site_or_404 as get_novel_in_site_or_404_impl,
    normalize_site_key as normalize_site_key_impl,
    resolve_site_key as resolve_site_key_impl,
)
from ..user_access_helpers import (
    calc_age,
    is_effective_premium_user as is_effective_premium_user_impl,
    is_force_premium_username as is_force_premium_username_impl,
    record_user_view_history as record_user_view_history_impl,
    require_current_user as require_current_user_impl,
)

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
get_novel_in_site_or_404 = partial(
    get_novel_in_site_or_404_impl,
    resolve_site_key=resolve_site_key,
    models=models,
    http_exception_cls=HTTPException,
)
require_current_user = partial(
    require_current_user_impl,
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
    jwt_module=jwt,
    models=models,
    http_exception_cls=HTTPException,
)
is_force_premium_username = partial(
    is_force_premium_username_impl,
    force_premium_usernames=FORCE_PREMIUM_USERNAMES,
)
is_effective_premium_user = partial(
    is_effective_premium_user_impl,
    force_all_premium=FORCE_ALL_PREMIUM,
    is_force_premium_username=is_force_premium_username,
)
record_user_view_history = partial(
    record_user_view_history_impl,
    normalize_site_key=normalize_site_key,
    models=models,
)
_is_free_reading_time = partial(
    is_free_reading_time,
    is_jp_holiday=is_jp_holiday,
)


def _optional_current_user(request: Request, db: Session):
    try:
        return require_current_user(request, db)
    except Exception:
        return None


def list_novels_service(
    *,
    request: Request,
    mine: bool = False,
    lang: str | None = None,
    background_tasks=None,
    db: Session,
):
    site_key = resolve_site_key(request)
    publish_scheduled_episodes(db, site_key=site_key)
    author_id = None
    if mine:
        user = require_current_user(request, db)
        author_id = int(user.id)

    novels = repo.list_novels_with_relations(db, site_key=site_key, author_id=author_id)
    novel_ids = [novel.id for novel in novels]
    char_counts = get_novel_char_counts(db, novel_ids)

    return [
        {
            "id": novel.id,
            "title": novel.title,
            "description": novel.description,
            "created_at": novel.created_at,
            "author_id": novel.author_id,
            "view_count": getattr(novel, "view_count", 0) or 0,
            "like_count": getattr(novel, "like_count", 0) or 0,
            "favorite_count": len(getattr(novel, "favorite_links", []) or []),
            "cover_image_url": getattr(novel, "cover_image_path", None),
            "total_char_count": char_counts.get(novel.id, 0),
            "estimated_read_minutes": estimated_read_minutes_for_char_count(char_counts.get(novel.id, 0)),
            "age_limit": getattr(novel, "age_limit", "all"),
            "is_ai_generated": bool(getattr(novel, "is_ai_generated", False)),
            "creative_type": getattr(novel, "creative_type", "original"),
            "fanfic_source_title": getattr(novel, "fanfic_source_title", None),
            "fanfic_characters": getattr(novel, "fanfic_characters", None),
            "fanfic_coupling": getattr(novel, "fanfic_coupling", None),
            "fanfic_notes": getattr(novel, "fanfic_notes", None),
            "series_name": getattr(novel, "series_name", None),
            "series_order": getattr(novel, "series_order", None),
            "is_public": bool(getattr(novel, "is_public", True)),
            "status": getattr(novel, "status", "public"),
            "tags": [
                {"id": nt.tag.id, "name": nt.tag.name}
                for nt in (getattr(novel, "novel_tags", []) or [])
                if getattr(nt, "tag", None) is not None
            ],
        }
        for novel in novels
    ]


def get_novel_detail_service(*, novel_id: int, request: Request, db: Session):
    user = _optional_current_user(request, db)
    site_key = resolve_site_key(request)
    novel = repo.find_novel_with_tags_and_author(db, novel_id=novel_id, site_key=site_key)
    if not novel:
        raise HTTPException(404, "小説が存在しません")

    if not novel.is_public:
        if not user or novel.author_id != user.id:
            raise HTTPException(404, "小説が存在しません")

    display_view_count = (novel.view_count or 0) + 1
    enqueue_novel_view(novel.id)
    if user:
        record_user_view_history(
            db,
            user_id=int(user.id),
            target_type="novel",
            target_id=int(novel.id),
            site_key=site_key,
        )
        db.commit()

    if not AGE_RESTRICTION_DISABLED and novel.age_limit in ("r15", "r18"):
        if not user:
            raise HTTPException(status_code=403, detail="年齢制限コンテンツです")
        age = calc_age(user.birth_date)
        if age is None:
            raise HTTPException(status_code=403, detail="生年月日が未登録のため閲覧できません")
        if novel.age_limit == "r15" and age < 15:
            raise HTTPException(status_code=403, detail="R15コンテンツを閲覧できません")
        if novel.age_limit == "r18" and age < 18:
            raise HTTPException(status_code=403, detail="R18コンテンツを閲覧できません")

    is_liked = bool(user and repo.user_liked_novel(db, novel_id=novel.id, user_id=int(user.id)))
    is_favorited = bool(user and repo.user_favorited_novel(db, novel_id=novel.id, user_id=int(user.id)))

    is_premium_user = is_effective_premium_user(user)
    is_free_time = _is_free_reading_time()
    can_read_full = is_premium_user or is_free_time or (user and novel.author_id == user.id)

    include_private = bool(user and novel.author_id == user.id)
    episodes = repo.list_novel_episodes_with_tags(
        db,
        novel_id=novel_id,
        site_key=site_key,
        include_private=include_private,
    )

    episode_ids = [int(ep.id) for ep in episodes if int(getattr(ep, "id", 0) or 0) > 0]
    episode_updated_map = {}
    if episode_ids and author_dashboard_helpers._table_has_column(db, "episodes", "updated_at"):
        episode_updated_map = repo.get_episode_updated_map(db, episode_ids=episode_ids)

    tags = [{"id": novel_tag.tag.id, "name": novel_tag.tag.name} for novel_tag in novel.novel_tags]
    public_only = not (user and novel.author_id == user.id)
    total_char_count = get_novel_char_counts(db, [novel.id], public_only=public_only).get(novel.id, 0)

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
        "age_confirmation_required": AGE_RESTRICTION_DISABLED and novel.age_limit == "r18",
        "total_char_count": total_char_count,
        "estimated_read_minutes": estimated_read_minutes_for_char_count(total_char_count),
        "tags": tags,
        "episodes": [
            {
                "id": ep.id,
                "title": ep.title,
                "cover_image_url": ep.cover_image_url,
                "view_count": getattr(ep, "view_count", 0) or 0,
                "number": get_episode_number(ep),
                "is_free_public": bool(getattr(ep, "is_free_public", False)),
                "body": ep.body if (bool(getattr(ep, "is_free_public", False)) or can_read_full) else truncate_for_free(ep.body or ""),
                "created_at": ep.created_at,
                "updated_at": episode_updated_map.get(int(ep.id)),
                "estimated_read_minutes": int(getattr(ep, "estimated_read_minutes", 0) or estimated_read_minutes_for_text(getattr(ep, "body", None))),
                "tags": [{"id": t.tag.id, "name": t.tag.name} for t in ep.episode_tags],
            }
            for ep in episodes
        ],
    }


def get_novel_translation_service(*, novel_id: int, lang: str, request: Request, db: Session):
    novel = get_novel_in_site_or_404(db, request, novel_id)
    if is_novel_draft(novel):
        user = _optional_current_user(request, db)
        if not user or novel.author_id != user.id:
            raise HTTPException(404, "小説が存在しません")
    language = normalize_language(lang)
    translation = repo.find_novel_translation(db, novel_id=novel_id, language=language)
    if not translation:
        raise HTTPException(404, "翻訳が存在しません")
    return {
        "novel_id": novel_id,
        "language": language,
        "title": translation.title,
        "description": translation.description,
        "tags": deserialize_tag_names(translation.tag_names),
        "created_at": translation.created_at,
        "updated_at": translation.updated_at,
    }


def list_episodes_service(*, novel_id: int, request: Request, db: Session):
    site_key = resolve_site_key(request)
    publish_scheduled_episodes(db, site_key=site_key)
    novel = repo.find_novel_with_tags_and_author(db, novel_id=novel_id, site_key=site_key)
    if not novel:
        raise HTTPException(404, "小説が存在しません")

    user = _optional_current_user(request, db)
    is_premium_user = is_effective_premium_user(user)
    is_free_time = _is_free_reading_time()
    can_read_full = is_premium_user or is_free_time or (user and novel.author_id == user.id)

    episodes = repo.list_novel_episodes_with_tags(
        db,
        novel_id=novel_id,
        site_key=site_key,
        include_private=bool(user and novel.author_id == user.id),
    )

    return [
        {
            "id": ep.id,
            "title": ep.title,
            "cover_image_url": ep.cover_image_url,
            "view_count": getattr(ep, "view_count", 0) or 0,
            "number": get_episode_number(ep),
            "is_free_public": bool(getattr(ep, "is_free_public", False)),
            "body": ep.body if (bool(getattr(ep, "is_free_public", False)) or can_read_full) else truncate_for_free(ep.body or ""),
            "created_at": ep.created_at,
            "estimated_read_minutes": int(getattr(ep, "estimated_read_minutes", 0) or estimated_read_minutes_for_text(getattr(ep, "body", None))),
        }
        for ep in episodes
    ]
