from pathlib import Path

path = Path("backend/app/main.py")
src = path.read_text(encoding="utf-8")

old_line = '        tag_names = [t.name for t in novel.tags]\n'
new_line = '        tag_names = [nt.tag.name for nt in novel.novel_tags]\n'

if old_line not in src:
    print("⚠ tag_names line not found; maybe already patched?")
else:
    src = src.replace(old_line, new_line, 1)
    path.write_text(src, encoding="utf-8")
    print("✅ tag_names line patched")
