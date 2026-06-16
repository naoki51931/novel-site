from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import models


def find_novel_in_site(db: Session, *, novel_id: int, site_key: str) -> models.Novel | None:
    return (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id, models.Novel.site_key == site_key)
        .first()
    )


def create_novel(db: Session, **kwargs) -> models.Novel:
    novel = models.Novel(**kwargs)
    db.add(novel)
    db.flush()
    return novel


def delete_novel_tags(db: Session, *, novel_id: int) -> None:
    db.query(models.NovelTag).filter(models.NovelTag.novel_id == novel_id).delete()


def find_tag_by_name(db: Session, *, tag_name: str) -> models.Tag | None:
    return db.query(models.Tag).filter(models.Tag.name == tag_name).first()


def create_tag(db: Session, *, tag_name: str) -> models.Tag:
    tag = models.Tag(name=tag_name)
    db.add(tag)
    db.flush()
    return tag


def add_novel_tag(db: Session, *, novel_id: int, tag_id: int) -> models.NovelTag:
    row = models.NovelTag(novel_id=novel_id, tag_id=tag_id)
    db.add(row)
    return row


def replace_novel_tags(db: Session, *, novel_id: int, tag_names: list[str]) -> list[str]:
    delete_novel_tags(db, novel_id=novel_id)
    normalized_tag_names: list[str] = []
    for raw_name in tag_names:
        tag_name = (raw_name or "").strip()
        if not tag_name:
            continue
        normalized_tag_names.append(tag_name)
        tag = find_tag_by_name(db, tag_name=tag_name)
        if not tag:
            tag = create_tag(db, tag_name=tag_name)
        add_novel_tag(db, novel_id=novel_id, tag_id=tag.id)
    return normalized_tag_names


def delete_novel_with_children(db: Session, *, novel_id: int, site_key: str) -> None:
    db.execute(
        text(
            "DELETE FROM episode_illusts "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id = :nid)"
        ),
        {"nid": novel_id},
    )
    db.execute(
        text(
            "DELETE FROM episode_tags "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id = :nid)"
        ),
        {"nid": novel_id},
    )
    db.execute(
        text(
            "DELETE FROM episode_likes "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id = :nid)"
        ),
        {"nid": novel_id},
    )
    db.execute(
        text(
            "DELETE FROM episode_translations "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id = :nid)"
        ),
        {"nid": novel_id},
    )
    db.execute(
        text(
            "DELETE FROM episode_comments "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id = :nid)"
        ),
        {"nid": novel_id},
    )
    db.execute(
        text(
            "DELETE FROM supports "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id = :nid)"
        ),
        {"nid": novel_id},
    )
    db.execute(text("DELETE FROM novel_comments WHERE novel_id = :nid"), {"nid": novel_id})
    db.execute(text("DELETE FROM novel_favorites WHERE novel_id = :nid"), {"nid": novel_id})
    db.execute(text("DELETE FROM novel_tags WHERE novel_id = :nid"), {"nid": novel_id})
    db.execute(text("DELETE FROM novel_likes WHERE novel_id = :nid"), {"nid": novel_id})
    db.execute(text("DELETE FROM novel_translations WHERE novel_id = :nid"), {"nid": novel_id})
    db.execute(text("DELETE FROM supports WHERE novel_id = :nid"), {"nid": novel_id})
    db.execute(text("DELETE FROM episodes WHERE novel_id = :nid"), {"nid": novel_id})
    db.execute(
        text("DELETE FROM novels WHERE id = :nid AND site_key = :site_key"),
        {"nid": novel_id, "site_key": site_key},
    )
