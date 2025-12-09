from pathlib import Path

path = Path("backend/app/main.py")
src = path.read_text(encoding="utf-8")

old = (
    '        "is_ai_generated": novel.is_ai_generated,\n'
)

new = (
    '        "is_ai_generated": novel.is_ai_generated,\n'
    '        "is_public": bool(getattr(novel, "is_public", True)),\n'
    '        "status": getattr(novel, "status", "public"),\n'
)

if new in src:
    print("already patched")
elif old in src:
    src = src.replace(old, new, 1)
    path.write_text(src, encoding="utf-8")
    print("patched get_novel_detail")
else:
    print("target block not found; no changes")
