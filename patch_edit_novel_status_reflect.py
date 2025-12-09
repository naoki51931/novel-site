from pathlib import Path

path = Path("frontend/src/pages/EditNovel.jsx")
src = path.read_text(encoding="utf-8")

changed = False

# 1) サーバ取得時に status を反映
if 'setStatus(data.status' not in src:
    old = (
        '        setTitle(data.title || "");\n'
        '        setDescription(data.description || "");\n'
        '        setAgeLimit(data.age_limit || "all");\n'
        '        setIsAIGenerated(!!data.is_ai_generated);\n'
    )
    new = (
        '        setTitle(data.title || "");\n'
        '        setDescription(data.description || "");\n'
        '        setAgeLimit(data.age_limit || "all");\n'
        '        setIsAIGenerated(!!data.is_ai_generated);\n'
        '        setStatus(data.status ?? (data.is_public ? "public" : "draft"));\n'
    )
    if old in src:
        src = src.replace(old, new)
        changed = True

# 2) ローカルストレージ読み込み時にも status を反映
if 'draft.status' not in src:
    old = (
        '      if (draft.title) setTitle(draft.title);\n'
        '      if (draft.description) setDescription(draft.description);\n'
        '      if (draft.ageLimit) setAgeLimit(draft.ageLimit);\n'
        '      if (typeof draft.isAIGenerated === "boolean") {\n'
        '        setIsAIGenerated(draft.isAIGenerated);\n'
        '      }\n'
    )
    new = (
        '      if (draft.title) setTitle(draft.title);\n'
        '      if (draft.description) setDescription(draft.description);\n'
        '      if (draft.ageLimit) setAgeLimit(draft.ageLimit);\n'
        '      if (draft.status) setStatus(draft.status);\n'
        '      if (typeof draft.isAIGenerated === "boolean") {\n'
        '        setIsAIGenerated(draft.isAIGenerated);\n'
        '      }\n'
    )
    if old in src:
        src = src.replace(old, new)
        changed = True

# 3) 自動保存 payload にも status を含める
if "status,\n        saved_at" not in src:
    old = (
        "        title,\n"
        "        description,\n"
        "        ageLimit,\n"
        "        isAIGenerated,\n"
        "        saved_at: new Date().toISOString(),\n"
        "      };\n"
    )
    new = (
        "        title,\n"
        "        description,\n"
        "        ageLimit,\n"
        "        isAIGenerated,\n"
        "        status,\n"
        "        saved_at: new Date().toISOString(),\n"
        "      };\n"
    )
    if old in src:
        src = src.replace(old, new)
        changed = True

if changed:
    path.write_text(src, encoding="utf-8")
    print("patched EditNovel.jsx")
else:
    print("no changes applied")
