from pathlib import Path

path = Path("backend/app/main.py")
src = path.read_text(encoding="utf-8")

old_block = """    # --- タグフィルタ ---
    if tag:
        query = (
            query.join(models.NovelTag, models.Novel.id == models.NovelTag.novel_id)
            .join(models.Tag, models.Tag.id == models.NovelTag.tag_id)
            .filter(models.Tag.name == tag)
        )

"""

new_block = """    # --- タグフィルタ ---
    if tag:
        # Novel タグ または Episode タグのどちらかに tag が付いている作品を取得
        ep_subq = (
            db.query(models.Episode.novel_id)
            .join(
                models.EpisodeTag,
                models.EpisodeTag.episode_id == models.Episode.id,
            )
            .join(models.Tag, models.Tag.id == models.EpisodeTag.tag_id)
            .filter(models.Tag.name == tag)
            .subquery()
        )

        query = (
            query.outerjoin(
                models.NovelTag, models.Novel.id == models.NovelTag.novel_id
            )
            .outerjoin(models.Tag, models.Tag.id == models.NovelTag.tag_id)
            .filter(
                or_(
                    models.Tag.name == tag,          # 小説自体のタグ
                    models.Novel.id.in_(ep_subq),    # エピソードのタグ経由
                )
            )
        )

"""

if old_block not in src:
    print("タグフィルタの既存ブロックが見つかりませんでした（既に修正済みか、インデントが違う可能性）")
else:
    src = src.replace(old_block, new_block, 1)
    path.write_text(src, encoding="utf-8")
    print("✅ list_public_novels のタグ検索を NovelTag + EpisodeTag 両対応に修正しました")
