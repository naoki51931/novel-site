import pathlib

path = pathlib.Path("backend/app/schemas.py")
src = path.read_text(encoding="utf-8")
changed = False

# 1) NovelBase / NovelCreate 側（is_ai_generated の下に追加）
if "is_public: bool" not in src:
    old = "    is_ai_generated: bool = False\n"
    new = old + "    is_public: bool = True\n"
    if old in src:
        src = src.replace(old, new, 1)
        print("[OK] added is_public: bool = True after is_ai_generated")
        changed = True
    else:
        print("[WARN] is_ai_generated: bool = False not found for NovelBase")

# 2) NovelUpdate 側
if "is_public: Optional[bool]" not in src:
    old = "    is_ai_generated: Optional[bool] = None\n"
    new = old + "    is_public: Optional[bool] = None\n"
    if old in src:
        src = src.replace(old, new, 1)
        print("[OK] added is_public: Optional[bool] = None after is_ai_generated in NovelUpdate")
        changed = True
    else:
        print("[WARN] is_ai_generated: Optional[bool] = None not found for NovelUpdate")

# 3) EpisodeBase に is_public 追加（body の下）
if "is_public: bool" not in src:
    old = "    body: str\n"
    new = old + "    is_public: bool = True\n"
    if old in src:
        src = src.replace(old, new, 1)
        print("[OK] added is_public: bool = True in EpisodeBase")
        changed = True
    else:
        print("[WARN] body: str not found for EpisodeBase")

# 4) EpisodeUpdate に is_public 追加
if "is_public: Optional[bool]" not in src:
    old = "    body: Optional[str] = None\n"
    new = old + "    is_public: Optional[bool] = None\n"
    if old in src:
        src = src.replace(old, new, 1)
        print("[OK] added is_public: Optional[bool] = None in EpisodeUpdate")
        changed = True
    else:
        print("[WARN] body: Optional[str] = None not found for EpisodeUpdate")

if changed:
    path.write_text(src, encoding="utf-8")
    print("[DONE] schemas.py patched")
else:
    print("[INFO] no changes applied (maybe already patched)")
