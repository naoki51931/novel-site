from pathlib import Path

# パスは今の構成どおりならこれでOK（違えばここだけ変えて）
path = Path("backend/app/main.py")

src = path.read_text(encoding="utf-8")

# --- ① タグフィルタ部の置換 ---
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
        tag_str = tag.strip()
        if tag_str:
            query = (
                query.join(models.NovelTag, models.Novel.id == models.NovelTag.novel_id)
                .join(models.Tag, models.Tag.id == models.NovelTag.tag_id)
                .filter(models.Tag.name == tag_str)
            )
"""

if old_block not in src:
    print("⚠ tag filter block not found; maybe already patched?")
else:
    src = src.replace(old_block, new_block, 1)
    print("✅ tag filter block patched")

# --- ② tag_names 行の置換（1行だけ） ---
old_line = "        tag_names = [t.name for t in novel.tags]\n"
new_line = "        tag_names = [nt.tag.name for nt in novel.novel_tags]\n"

if old_line not in src:
    print("⚠ tag_names line not found; maybe already patched?")
else:
    src = src.replace(old_line, new_line, 1)
    print("✅ tag_names line patched")

path.write_text(src, encoding="utf-8")
