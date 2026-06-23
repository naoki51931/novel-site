from fastapi import Request
from sqlalchemy.orm import Session

from .. import public_chat_helpers
from ..repositories import favorites_repository as repo


def list_my_favorites_service(*, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    site_key = legacy.resolve_site_key(request)
    favorites = repo.list_user_favorite_novels(db, user_id=int(user.id), site_key=site_key)
    novel_ids = [int(n.id) for n in favorites]
    char_counts = legacy.get_novel_char_counts(db, novel_ids, public_only=True)
    cover_map = legacy._build_public_cover_map(db, novel_ids, site_key)

    return [
        {
            "id": novel.id,
            "title": novel.title,
            "description": novel.description,
            "age_limit": novel.age_limit,
            "is_ai_generated": novel.is_ai_generated,
            "creative_type": getattr(novel, "creative_type", "original"),
            "author_id": novel.author_id,
            "author_username": novel.author.username if novel.author else None,
            "created_at": novel.created_at,
            "view_count": getattr(novel, "view_count", 0) or 0,
            "like_count": getattr(novel, "like_count", 0) or 0,
            "favorite_count": len(getattr(novel, "favorite_links", []) or []),
            "total_char_count": char_counts.get(novel.id, 0),
            "is_public": bool(getattr(novel, "is_public", True)),
            "status": getattr(novel, "status", "public"),
            "cover_image_url": cover_map.get(novel.id),
            "tags": [
                {"id": novel_tag.tag.id, "name": novel_tag.tag.name}
                for novel_tag in (getattr(novel, "novel_tags", []) or [])
                if getattr(novel_tag, "tag", None) is not None
            ],
        }
        for novel in favorites
    ]


def list_my_ai_chat_favorites_service(*, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    can_view_r18 = legacy.can_user_access_novel_age_limit(user, "r18")
    rows = repo.list_user_ai_chat_favorites(db, user_id=int(user.id))
    if not rows:
        return []

    character_ids = [int(character.id) for _, character, _ in rows]
    like_counts = repo.ai_chat_like_counts(db, character_ids=character_ids)
    favorite_counts = repo.ai_chat_favorite_counts(db, character_ids=character_ids)

    output = []
    for favorite_link, character, author_username in rows:
        if bool(getattr(character, "is_r18", False)) and not can_view_r18:
            continue
        output.append(
            {
                "id": int(character.id),
                "name": str(character.name or ""),
                "personality": public_chat_helpers._trim_public_character_intro(
                    getattr(character, "personality", None)
                ),
                "author_username": author_username,
                "published_at": legacy.to_utc_isoformat(getattr(character, "published_at", None)),
                "image_url": getattr(character, "image_url", None),
                "is_r18": bool(getattr(character, "is_r18", False)),
                "like_count": like_counts.get(int(character.id), 0),
                "favorite_count": favorite_counts.get(int(character.id), 0),
                "created_at": legacy.to_utc_isoformat(getattr(favorite_link, "created_at", None)),
            }
        )
    return output
