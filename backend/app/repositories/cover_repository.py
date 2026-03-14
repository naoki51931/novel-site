from typing import Optional

from sqlalchemy.orm import Session

from .. import models


def create_cover_generation(
    db: Session,
    *,
    user_id: int,
    novel_id: Optional[int],
    prompt: str,
    genre: Optional[str],
    mood: Optional[str],
    color_theme: Optional[str],
    character_count: Optional[int],
    provider: str,
    model: str,
    status: str,
) -> models.CoverGeneration:
    row = models.CoverGeneration(
        user_id=user_id,
        novel_id=novel_id,
        prompt=prompt,
        genre=genre,
        mood=mood,
        color_theme=color_theme,
        character_count=character_count,
        provider=provider,
        model=model,
        status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def mark_cover_generation_succeeded(
    db: Session,
    *,
    row_id: int,
    image_path: str,
) -> models.CoverGeneration | None:
    row = db.query(models.CoverGeneration).filter(models.CoverGeneration.id == row_id).first()
    if not row:
        return None
    row.status = "succeeded"
    row.image_path = image_path
    row.error_message = None
    db.commit()
    db.refresh(row)
    return row


def mark_cover_generation_failed(
    db: Session,
    *,
    row_id: int,
    error_message: str,
) -> models.CoverGeneration | None:
    row = db.query(models.CoverGeneration).filter(models.CoverGeneration.id == row_id).first()
    if not row:
        return None
    row.status = "failed"
    row.error_message = str(error_message or "")[:4000] or "cover generation failed"
    db.commit()
    db.refresh(row)
    return row


def list_cover_generations(
    db: Session,
    *,
    user_id: int,
    novel_id: int | None = None,
    limit: int = 50,
) -> list[models.CoverGeneration]:
    q = db.query(models.CoverGeneration).filter(models.CoverGeneration.user_id == user_id)
    if novel_id is not None:
        q = q.filter(models.CoverGeneration.novel_id == novel_id)
    return (
        q.order_by(models.CoverGeneration.created_at.desc(), models.CoverGeneration.id.desc())
        .limit(max(1, min(int(limit), 200)))
        .all()
    )


def find_user_cover_by_path(
    db: Session,
    *,
    user_id: int,
    image_path: str,
) -> models.CoverGeneration | None:
    return (
        db.query(models.CoverGeneration)
        .filter(
            models.CoverGeneration.user_id == user_id,
            models.CoverGeneration.status == "succeeded",
            models.CoverGeneration.image_path == image_path,
        )
        .order_by(models.CoverGeneration.id.desc())
        .first()
    )
