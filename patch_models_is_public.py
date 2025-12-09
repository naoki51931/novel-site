import pathlib

path = pathlib.Path("backend/app/models.py")
src = path.read_text(encoding="utf-8")

changed = False

# 1) Boolean を import に追加
lines = src.splitlines()
for i, line in enumerate(lines):
    if line.startswith("from sqlalchemy import ") and "Boolean" not in line:
        lines[i] = line.rstrip() + ", Boolean"
        print("[OK] added Boolean to sqlalchemy import")
        changed = True
        break
src = "\n".join(lines)

# 2) Novel に is_public 追加
if "class Novel(Base):" in src and "is_public = Column(Boolean" not in src:
    before = "    description = Column(Text, nullable=True)"
    after = before + "\n    is_public = Column(Boolean, nullable=False, default=True)"
    if before in src:
        src = src.replace(before, after, 1)
        print("[OK] added Novel.is_public")
        changed = True
    else:
        print("[WARN] could not find 'description' line under Novel to insert is_public")

# 3) Episode に is_public 追加
if "class Episode(Base):" in src and "is_public = Column(Boolean" not in src:
    before = "    episode_number = Column(Integer, nullable=False)"
    after = before + "\n    is_public = Column(Boolean, nullable=False, default=True)"
    if before in src:
        src = src.replace(before, after, 1)
        print("[OK] added Episode.is_public")
        changed = True
    else:
        print("[WARN] could not find 'episode_number' line under Episode to insert is_public")

if changed:
    path.write_text(src, encoding="utf-8")
    print("[DONE] models.py patched")
else:
    print("[INFO] no changes applied (maybe already patched)")
