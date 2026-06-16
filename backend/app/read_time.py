import math
import re

from sqlalchemy import func
from sqlalchemy.orm import Session

READING_CHARS_PER_MINUTE = 600
_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


def normalized_char_count(text: str | None) -> int:
    if not text:
        return 0
    compact = _WHITESPACE_RE.sub("", str(text))
    return len(compact)


def estimated_read_minutes_for_char_count(char_count: int | None) -> int:
    count = max(0, int(char_count or 0))
    if count <= 0:
        return 0
    return max(1, int(math.ceil(count / READING_CHARS_PER_MINUTE)))


def estimated_read_minutes_for_text(text: str | None) -> int:
    return estimated_read_minutes_for_char_count(normalized_char_count(text))


def sync_episode_estimated_read_minutes(episode) -> int:
    minutes = estimated_read_minutes_for_text(getattr(episode, "body", None))
    episode.estimated_read_minutes = minutes
    return minutes


def sync_novel_estimated_read_minutes(db: Session, *, novel_id: int, models) -> int:
    total = (
        db.query(func.coalesce(func.sum(models.Episode.estimated_read_minutes), 0))
        .filter(models.Episode.novel_id == int(novel_id))
        .scalar()
    )
    minutes = int(total or 0)
    db.query(models.Novel).filter(models.Novel.id == int(novel_id)).update(
        {models.Novel.estimated_read_minutes: minutes},
        synchronize_session=False,
    )
    return minutes
