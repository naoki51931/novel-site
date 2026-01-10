import argparse

from .database import SessionLocal
from . import models
from .main import (
    normalize_language,
    other_language,
    get_novel_tag_names,
    upsert_novel_translation,
    upsert_episode_translation,
)


def backfill(limit: int | None = None) -> tuple[int, int]:
    db = SessionLocal()
    novels_done = 0
    episodes_done = 0
    try:
        novel_query = db.query(models.Novel).order_by(models.Novel.id.asc())
        if limit:
            novel_query = novel_query.limit(limit)
        for novel in novel_query.all():
            source_language = normalize_language(getattr(novel, "language", None))
            target_language = other_language(source_language)
            exists = (
                db.query(models.NovelTranslation)
                .filter(
                    models.NovelTranslation.novel_id == novel.id,
                    models.NovelTranslation.language == target_language,
                )
                .first()
            )
            if exists:
                continue
            tag_names = get_novel_tag_names(db, novel.id)
            upsert_novel_translation(
                db,
                novel=novel,
                source_language=source_language,
                tag_names=tag_names,
            )
            db.commit()
            novels_done += 1

        episode_query = db.query(models.Episode).order_by(models.Episode.id.asc())
        if limit:
            episode_query = episode_query.limit(limit)
        for episode in episode_query.all():
            source_language = normalize_language(getattr(episode, "language", None))
            target_language = other_language(source_language)
            exists = (
                db.query(models.EpisodeTranslation)
                .filter(
                    models.EpisodeTranslation.episode_id == episode.id,
                    models.EpisodeTranslation.language == target_language,
                )
                .first()
            )
            if exists:
                continue
            upsert_episode_translation(
                db,
                episode=episode,
                source_language=source_language,
            )
            db.commit()
            episodes_done += 1
    finally:
        db.close()
    return novels_done, episodes_done


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill JP/EN translations.")
    parser.add_argument("--limit", type=int, default=None, help="Max items to process")
    args = parser.parse_args()

    novels_done, episodes_done = backfill(args.limit)
    print(f"novels_translated={novels_done} episodes_translated={episodes_done}")


if __name__ == "__main__":
    main()
