from pathlib import Path

path = Path("frontend/src/pages/EditNovel.jsx")
src = path.read_text(encoding="utf-8")

old = (
'        // status があればそれを、なければ is_public から推測\n'
'        setStatus(data.status || (data.is_public === false ? "draft" : "public"));\n'
)

new = (
'        // status が "draft" なら下書き。\n'
'        // それ以外でも is_public === false なら下書き扱いにする（データ不整合の保険）\n'
'        if (data.status === "draft" || data.is_public === false) {\n'
'          setStatus("draft");\n'
'        } else {\n'
'          setStatus("public");\n'
'        }\n'
)

if new in src:
    print("already patched")
elif old in src:
    src = src.replace(old, new, 1)
    path.write_text(src, encoding="utf-8")
    print("patched EditNovel status init")
else:
    print("target block not found; no changes")
