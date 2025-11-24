
# タグ存在チェック & 作成関数
def get_or_create_tags(db: Session, tag_names: list[str]):
    normalized = [s.strip() for s in tag_names if s.strip()]
    if not normalized:
        return []

    existing = db.query(models.Tag).filter(models.Tag.name.in_(normalized)).all()
    exist_map = {t.name: t for t in existing}

    result = []
    for name in normalized:
        if name in exist_map:
            result.append(exist_map[name])
        else:
            t = models.Tag(name=name)
            db.add(t)
            db.flush()
            result.append(t)
    return result
