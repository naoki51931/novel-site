#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
OUT_DICT = SRC_DIR / "lib" / "i18nPretranslated.json"
CHECKPOINT = ROOT / "i18n" / "ui_dict_checkpoint.json"
API_BASE = os.getenv("UI_I18N_API_BASE", "http://127.0.0.1:8000").rstrip("/")
TARGET_LANGS = ["zh-cn", "zh-tw", "ko"]
BATCH_SIZE = max(1, int(os.getenv("UI_I18N_BATCH_SIZE", "8")))
HTTP_TIMEOUT = max(10, int(os.getenv("UI_I18N_TIMEOUT_SEC", "120")))
SLEEP_ON_ERROR = max(1, int(os.getenv("UI_I18N_SLEEP_ON_ERROR_SEC", "2")))
RETRY_PER_CHUNK = max(1, int(os.getenv("UI_I18N_RETRY_PER_CHUNK", "3")))


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _unquote(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    if s.startswith("`") and s.endswith("`"):
        body = s[1:-1]
        if "${" in body:
            return ""
        return body.replace("\\`", "`").replace("\\\\", "\\")
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        try:
            if s.startswith("'"):
                inner = s[1:-1].replace("\\", "\\\\").replace('"', '\\"')
                return json.loads(f'"{inner}"')
            return json.loads(s)
        except Exception:
            return ""
    return ""


def _extract_file_entries(text: str):
    out = []
    re_t = re.compile(r"t\s*\(\s*\{([\s\S]*?)\}\s*(?:,|\))")
    re_kv = re.compile(r"""(?:^|,)\s*(ja|en)\s*:\s*("(?:\\.|[^"])*"|'(?:\\.|[^'])*'|`(?:\\.|[^`])*`)""")
    for m in re_t.finditer(text):
        body = m.group(1) or ""
        row = {}
        for kv in re_kv.finditer(body):
            lang = kv.group(1)
            val = _unquote(kv.group(2))
            if val:
                row[lang] = val.strip()
        if row.get("ja") or row.get("en"):
            out.append(row)
    return out


def _scan_pages():
    pages = []
    for p in sorted(SRC_DIR.rglob("*")):
        if p.suffix not in {".jsx", ".js", ".tsx", ".ts"}:
            continue
        rel = str(p.relative_to(ROOT))
        try:
            rows = _extract_file_entries(p.read_text(encoding="utf-8"))
        except Exception:
            rows = []
        if not rows:
            continue
        dedup = []
        seen = set()
        for r in rows:
            key = r.get("ja") or r.get("en") or ""
            if not key or key in seen:
                continue
            seen.add(key)
            dedup.append(
                {
                    "source_lang": "ja" if r.get("ja") else "en",
                    "source_text": r.get("ja") or r.get("en") or "",
                }
            )
        if dedup:
            pages.append({"path": rel, "items": dedup})
    return pages


def _translate_chunk(source_lang: str, target_lang: str, texts):
    req = urllib.request.Request(
        API_BASE + "/api/i18n/translate",
        data=json.dumps(
            {
                "source_lang": source_lang,
                "target_lang": target_lang,
                "texts": texts,
                "force": True,
            }
        ).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    items = payload.get("items")
    return items if isinstance(items, dict) else {}


def _translate_resilient(source_lang: str, target_lang: str, texts):
    if not texts:
        return {}, []
    last_err = None
    for _ in range(RETRY_PER_CHUNK):
        try:
            return _translate_chunk(source_lang, target_lang, texts), []
        except Exception as e:
            last_err = e
            time.sleep(1)
    if len(texts) <= 1:
        return {}, texts[:]  # do not fallback to source text
    mid = len(texts) // 2
    left_ok, left_ng = _translate_resilient(source_lang, target_lang, texts[:mid])
    right_ok, right_ng = _translate_resilient(source_lang, target_lang, texts[mid:])
    left_ok.update(right_ok)
    return left_ok, left_ng + right_ng


def _checkpoint_default():
    return {
        "target_lang_index": 0,
        "page_index": 0,
        "item_index_by_page": {},
        "failed_by_lang": {"zh-cn": [], "zh-tw": [], "ko": []},
        "updated_at": int(time.time()),
    }


def main():
    pages = _scan_pages()
    if not pages:
        print("no translatable pages found")
        return 0

    dict_payload = _read_json(OUT_DICT, {"zh-cn": {}, "zh-tw": {}, "ko": {}})
    for lang in TARGET_LANGS:
        if not isinstance(dict_payload.get(lang), dict):
            dict_payload[lang] = {}

    checkpoint = _read_json(CHECKPOINT, _checkpoint_default())
    target_lang_index = int(checkpoint.get("target_lang_index", 0) or 0)
    page_index = int(checkpoint.get("page_index", 0) or 0)
    item_index_by_page = checkpoint.get("item_index_by_page", {}) or {}
    failed_by_lang = checkpoint.get("failed_by_lang", {}) or {}
    for lang in TARGET_LANGS:
        if not isinstance(failed_by_lang.get(lang), list):
            failed_by_lang[lang] = []

    total_pages = len(pages)
    for li in range(target_lang_index, len(TARGET_LANGS)):
        target_lang = TARGET_LANGS[li]
        if li != target_lang_index:
            page_index = 0
        for pi in range(page_index, total_pages):
            page = pages[pi]
            path = page["path"]
            items = page["items"]
            cursor_key = f"{target_lang}:{path}"
            cursor = int(item_index_by_page.get(cursor_key, 0) or 0)

            ja_items = [i["source_text"] for i in items if i["source_lang"] == "ja"]
            en_items = [i["source_text"] for i in items if i["source_lang"] == "en"]
            merged = [("ja", t) for t in ja_items] + [("en", t) for t in en_items]
            total_items = len(merged)
            if total_items == 0:
                continue

            while cursor < total_items:
                batch = merged[cursor : cursor + BATCH_SIZE]
                grouped = {"ja": [], "en": []}
                for src_lang, txt in batch:
                    grouped[src_lang].append(txt)

                try:
                    if grouped["ja"]:
                        got, failed = _translate_resilient("ja", target_lang, grouped["ja"])
                        dict_payload[target_lang].update(got)
                        if failed:
                            failed_by_lang[target_lang].extend(failed)
                    if grouped["en"]:
                        got, failed = _translate_resilient("en", target_lang, grouped["en"])
                        dict_payload[target_lang].update(got)
                        if failed:
                            failed_by_lang[target_lang].extend(failed)
                except Exception as e:
                    print(f"[warn] {target_lang} {path} cursor={cursor} err={e!r}")
                    time.sleep(SLEEP_ON_ERROR)
                    continue

                cursor += len(batch)
                item_index_by_page[cursor_key] = cursor
                checkpoint = {
                    "target_lang_index": li,
                    "page_index": pi,
                    "item_index_by_page": item_index_by_page,
                    "failed_by_lang": failed_by_lang,
                    "updated_at": int(time.time()),
                }
                _write_json(OUT_DICT, dict_payload)
                _write_json(CHECKPOINT, checkpoint)
                print(
                    f"[ok] {target_lang} page={pi+1}/{total_pages} file={path} items={cursor}/{total_items} translated={len(dict_payload[target_lang])} failed={len(failed_by_lang[target_lang])}",
                    flush=True,
                )

            item_index_by_page[cursor_key] = total_items
            _write_json(CHECKPOINT, checkpoint)

    _write_json(OUT_DICT, dict_payload)
    final_cp = _checkpoint_default()
    final_cp["target_lang_index"] = len(TARGET_LANGS)
    final_cp["page_index"] = total_pages
    final_cp["updated_at"] = int(time.time())
    _write_json(CHECKPOINT, final_cp)

    summary = {lang: len(dict_payload.get(lang, {})) for lang in TARGET_LANGS}
    failed_summary = {lang: len(failed_by_lang.get(lang, [])) for lang in TARGET_LANGS}
    print(json.dumps({"ok": True, "pages": total_pages, "counts": summary, "failed_counts": failed_summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
