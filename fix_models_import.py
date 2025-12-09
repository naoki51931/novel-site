import pathlib, re

path = pathlib.Path("backend/app/models.py")
src = path.read_text(encoding="utf-8")

# sqlalchemy import 行を安全に置換
new_import = "from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, func\n"

# Column の import がある行を探す
pattern = r"from sqlalchemy import[^\n]*\n"

if re.search(pattern, src):
    src2 = re.sub(pattern, new_import, src, count=1)
    print("[OK] replaced broken sqlalchemy import")
else:
    print("[WARN] no import line found to replace")
    src2 = src

path.write_text(src2, encoding="utf-8")
