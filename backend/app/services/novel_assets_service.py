from fastapi import HTTPException, Request
from sqlalchemy.orm import Session


async def generate_novel_summary_candidates_service(*, novel_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    novel = legacy.get_novel_in_site_or_404(db, request, novel_id)
    if novel.author_id != user.id:
        raise HTTPException(403, "説明文の生成権限がありません")

    first_episode = (
        db.query(legacy.models.Episode)
        .filter(
            legacy.models.Episode.novel_id == novel_id,
            legacy.models.Episode.site_key == legacy.resolve_site_key(request),
        )
        .order_by(
            legacy.models.Episode.episode_number.is_(None),
            legacy.models.Episode.episode_number,
            legacy.models.Episode.id,
        )
        .first()
    )
    if not first_episode or not (first_episode.body or "").strip():
        raise HTTPException(404, "本文が存在しません")

    source_text = (first_episode.body or "").strip()[:1000]
    candidates, tokens, model = await legacy.call_openai_summary_candidates(
        source_text,
        model=getattr(user, "ai_summary_model", None),
    )
    return legacy.NovelSummaryCandidatesOut(
        candidates=candidates,
        model=model,
        used_tokens=tokens,
    )


async def generate_novel_tag_candidates_service(*, novel_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    novel = legacy.get_novel_in_site_or_404(db, request, novel_id)
    if novel.author_id != user.id:
        raise HTTPException(403, "タグ生成権限がありません")

    first_episode = (
        db.query(legacy.models.Episode)
        .filter(
            legacy.models.Episode.novel_id == novel_id,
            legacy.models.Episode.site_key == legacy.resolve_site_key(request),
        )
        .order_by(
            legacy.models.Episode.episode_number.is_(None),
            legacy.models.Episode.episode_number,
            legacy.models.Episode.id,
        )
        .first()
    )
    if not first_episode or not (first_episode.body or "").strip():
        raise HTTPException(404, "本文が存在しません")

    source_text = (first_episode.body or "").strip()[:1000]
    candidates, tokens, model = await legacy.call_openai_tag_candidates(
        source_text,
        model=getattr(user, "ai_tag_model", None),
    )
    return legacy.TagCandidatesOut(
        candidates=candidates,
        model=model,
        used_tokens=tokens,
    )


async def generate_novel_title_candidates_service(*, novel_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    novel = legacy.get_novel_in_site_or_404(db, request, novel_id)
    if novel.author_id != user.id:
        raise HTTPException(403, "タイトル生成権限がありません")

    first_episode = (
        db.query(legacy.models.Episode)
        .filter(
            legacy.models.Episode.novel_id == novel_id,
            legacy.models.Episode.site_key == legacy.resolve_site_key(request),
        )
        .order_by(
            legacy.models.Episode.episode_number.is_(None),
            legacy.models.Episode.episode_number,
            legacy.models.Episode.id,
        )
        .first()
    )
    if not first_episode or not (first_episode.body or "").strip():
        raise HTTPException(404, "本文が存在しません")

    source_text = (first_episode.body or "").strip()[:2200]
    candidates, tokens, model = await legacy.call_openai_title_candidates(
        source_text,
        model=getattr(user, "ai_title_model", None),
        suggestions_count=5,
    )
    return legacy.TitleCandidatesOut(
        candidates=candidates,
        model=model,
        used_tokens=tokens,
    )
