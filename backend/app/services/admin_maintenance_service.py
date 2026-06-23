from fastapi import HTTPException, Request
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, aliased


def admin_backfill_translations_service(*, request: Request, payload: dict, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    only_public = bool(payload.get("only_public") or False)
    site_key = (payload.get("site_key") or "").strip().lower() or None
    max_novels = payload.get("max_novels", payload.get("limit"))
    max_episodes = payload.get("max_episodes", payload.get("limit"))
    try:
        max_novels_value = int(max_novels) if max_novels is not None else 200
        max_episodes_value = int(max_episodes) if max_episodes is not None else 400
    except Exception:
        raise HTTPException(400, "max_novels/max_episodes/limit は数値で指定してください")
    max_novels_value = max(0, min(5000, max_novels_value))
    max_episodes_value = max(0, min(10000, max_episodes_value))

    novels_done = 0
    episodes_done = 0
    novels_failed = 0
    episodes_failed = 0

    def _apply_public_filters(q, model):
        if not only_public:
            return q
        return q.filter(getattr(model, "status") == "public").filter(getattr(model, "is_public") == True)

    def _apply_site_key_filter(q, model):
        if not site_key:
            return q
        if hasattr(model, "site_key"):
            return q.filter(getattr(model, "site_key") == site_key)
        return q

    if max_novels_value:
        ja_targets = legacy.translation_target_languages("ja")
        novel_tr = aliased(legacy.models.NovelTranslation)
        ja_missing = (
            db.query(legacy.models.Novel)
            .outerjoin(
                novel_tr,
                and_(
                    novel_tr.novel_id == legacy.models.Novel.id,
                    novel_tr.language.in_(ja_targets),
                ),
            )
            .filter(or_(legacy.models.Novel.language.is_(None), legacy.models.Novel.language == "ja"))
            .group_by(legacy.models.Novel.id)
            .having(func.count(func.distinct(novel_tr.language)) < len(ja_targets))
        )
        ja_missing = _apply_public_filters(ja_missing, legacy.models.Novel)
        ja_missing = _apply_site_key_filter(ja_missing, legacy.models.Novel)
        ja_missing = ja_missing.order_by(legacy.models.Novel.id.asc()).limit(max_novels_value).all()
        for novel in ja_missing:
            tag_names = legacy.get_novel_tag_names(db, novel.id)
            legacy.upsert_novel_translation(db, novel=novel, source_language="ja", tag_names=tag_names)
            db.commit()
            translated_count = (
                db.query(func.count(func.distinct(legacy.models.NovelTranslation.language)))
                .filter(
                    legacy.models.NovelTranslation.novel_id == novel.id,
                    legacy.models.NovelTranslation.language.in_(ja_targets),
                )
                .scalar()
                or 0
            )
            if int(translated_count) >= len(ja_targets):
                novels_done += 1
            else:
                novels_failed += 1

        remaining = max_novels_value - novels_done
        if remaining > 0:
            novel_tr2 = aliased(legacy.models.NovelTranslation)
            en_missing = (
                db.query(legacy.models.Novel)
                .outerjoin(
                    novel_tr2,
                    and_(
                        novel_tr2.novel_id == legacy.models.Novel.id,
                        novel_tr2.language == "ja",
                    ),
                )
                .filter(legacy.models.Novel.language.in_(["en", "zh-cn", "zh-tw", "ko"]))
                .filter(novel_tr2.novel_id.is_(None))
            )
            en_missing = _apply_public_filters(en_missing, legacy.models.Novel)
            en_missing = _apply_site_key_filter(en_missing, legacy.models.Novel)
            en_missing = en_missing.order_by(legacy.models.Novel.id.asc()).limit(remaining).all()
            for novel in en_missing:
                tag_names = legacy.get_novel_tag_names(db, novel.id)
                legacy.upsert_novel_translation(db, novel=novel, source_language="en", tag_names=tag_names)
                db.commit()
                created = (
                    db.query(legacy.models.NovelTranslation)
                    .filter(
                        legacy.models.NovelTranslation.novel_id == novel.id,
                        legacy.models.NovelTranslation.language == "ja",
                    )
                    .first()
                )
                if created:
                    novels_done += 1
                else:
                    novels_failed += 1

    if max_episodes_value:
        episodes_q = db.query(legacy.models.Episode).order_by(legacy.models.Episode.id.asc())
        episodes_q = _apply_public_filters(episodes_q, legacy.models.Episode)
        episodes_q = _apply_site_key_filter(episodes_q, legacy.models.Episode)
        candidates = episodes_q.limit(max_episodes_value).all()
        for episode in candidates:
            source_language = legacy.normalize_language(getattr(episode, "language", None))
            if legacy._is_episode_translation_complete(db, episode=episode, source_language=source_language):
                continue
            legacy.upsert_episode_translation(db, episode=episode, source_language=source_language)
            db.commit()
            if legacy._is_episode_translation_complete(db, episode=episode, source_language=source_language):
                episodes_done += 1
            else:
                episodes_failed += 1

    return {
        "novels_translated": novels_done,
        "episodes_translated": episodes_done,
        "novels_failed": novels_failed,
        "episodes_failed": episodes_failed,
    }


def admin_delete_board_post_service(*, post_id: int, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    site_key = legacy.resolve_site_key(request)
    post = (
        db.query(legacy.models.BoardPost)
        .filter(legacy.models.BoardPost.id == post_id, legacy.models.BoardPost.site_key == site_key)
        .first()
    )
    if not post:
        raise HTTPException(404, "投稿が見つかりません")
    child_ids = [
        int(row[0])
        for row in db.query(legacy.models.BoardPost.id)
        .filter(
            legacy.models.BoardPost.parent_post_id == post.id,
            legacy.models.BoardPost.site_key == site_key,
        )
        .all()
    ]
    delete_post_ids = [int(post.id), *child_ids]
    if delete_post_ids:
        db.query(legacy.models.BoardPostLike).filter(
            legacy.models.BoardPostLike.post_id.in_(delete_post_ids)
        ).delete(synchronize_session=False)
    db.query(legacy.models.BoardPost).filter(
        legacy.models.BoardPost.parent_post_id == post.id,
        legacy.models.BoardPost.site_key == site_key,
    ).delete(synchronize_session=False)
    db.delete(post)
    db.commit()
    return {"ok": True}
