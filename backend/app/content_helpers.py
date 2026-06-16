import json
import re
from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from . import models

ILLUST_TAG_RE = re.compile(r"^illust:\d{8}$")
ILLUST_TAG_BRACKET_RE = re.compile(r"^\[\[illust:(\d{8})\]\]$")
ALLOWED_META_TAGS = {
    "type": {"scene", "portrait", "object", "map", "symbol"},
    "pos": {"intro", "middle", "climax", "outro"},
    "mood": {"bright", "dark", "soft", "tense", "melancholy"},
    "light": {"day", "night", "backlight"},
    "spoiler": {"none", "hint", "full"},
}


def get_novel_char_counts(db: Session, novel_ids: list[int], public_only: bool = False) -> dict[int, int]:
    if not novel_ids:
        return {}
    description_rows = (
        db.query(
            models.Novel.id,
            func.coalesce(func.char_length(models.Novel.description), 0),
        )
        .filter(models.Novel.id.in_(novel_ids))
        .all()
    )
    counts: dict[int, int] = {row[0]: int(row[1] or 0) for row in description_rows}

    query = (
        db.query(
            models.Episode.novel_id,
            func.coalesce(
                func.sum(func.coalesce(func.char_length(models.Episode.body), 0)),
                0,
            ),
        )
        .filter(models.Episode.novel_id.in_(novel_ids))
    )
    if public_only:
        query = query.filter(models.Episode.status == "public").filter(models.Episode.is_public == True)
    rows = query.group_by(models.Episode.novel_id).all()
    for row in rows:
        novel_id = int(row[0])
        counts[novel_id] = counts.get(novel_id, 0) + int(row[1] or 0)
    return counts


def apply_novel_daily_metric(
    db: Session,
    novel_id: int,
    view_delta: int = 0,
    like_delta: int = 0,
    favorite_delta: int = 0,
    target_date: Optional[date] = None,
) -> None:
    if view_delta == 0 and like_delta == 0 and favorite_delta == 0:
        return
    metric_date = target_date or date.today()
    db.execute(
        text(
            """
            INSERT INTO novel_daily_metrics (novel_id, `date`, view_count, like_count, favorite_count)
            VALUES (:novel_id, :metric_date, :view_delta, :like_delta, :favorite_delta)
            ON DUPLICATE KEY UPDATE
                view_count = GREATEST(0, view_count + :view_delta),
                like_count = GREATEST(0, like_count + :like_delta),
                favorite_count = GREATEST(0, favorite_count + :favorite_delta),
                updated_at = NOW()
            """
        ),
        {
            "novel_id": novel_id,
            "metric_date": metric_date,
            "view_delta": view_delta,
            "like_delta": like_delta,
            "favorite_delta": favorite_delta,
        },
    )


def normalize_illust_tag(value: str | None) -> str | None:
    tag = (value or "").strip()
    if not tag:
        return None
    bracket_match = ILLUST_TAG_BRACKET_RE.match(tag)
    if bracket_match:
        tag = f"illust:{bracket_match.group(1)}"
    if not ILLUST_TAG_RE.match(tag):
        raise HTTPException(400, "illustタグは [[illust:12345678]] の形式で指定してください")
    if any(ord(ch) > 127 for ch in tag):
        raise HTTPException(400, "illustタグは英数字のみで指定してください")
    return tag


def normalize_meta_tags(value: str | list[str] | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        raw_tags = [tag for tag in re.split(r"[,\\s]+", value.strip()) if tag]
    else:
        raw_tags = [tag for tag in value if tag]

    normalized: list[str] = []
    for raw in raw_tags:
        tag = (raw or "").strip().lower()
        if not tag:
            continue
        if any(ord(ch) > 127 for ch in tag):
            raise HTTPException(400, "押絵の補助タグは英語のみで指定してください")
        if ":" not in tag:
            raise HTTPException(400, f"押絵の補助タグ形式が不正です: {tag}")
        key, val = tag.split(":", 1)
        allowed_vals = ALLOWED_META_TAGS.get(key)
        if not allowed_vals or val not in allowed_vals:
            raise HTTPException(400, f"押絵の補助タグが不正です: {tag}")
        if tag not in normalized:
            normalized.append(tag)
    return normalized


def serialize_meta_tags(tags: list[str]) -> str | None:
    if not tags:
        return None
    return ",".join(tags)


def deserialize_meta_tags(value: str | None) -> list[str]:
    if not value:
        return []
    return [tag for tag in value.split(",") if tag]


def normalize_language(value: str | None) -> str:
    normalized = (value or "ja").strip().lower()
    if normalized in ("ja", "jp", "jpn", "japanese"):
        return "ja"
    if normalized in ("en", "eng", "english"):
        return "en"
    if normalized in ("zh-cn", "zh_cn", "zh-hans", "zh_hans", "cn", "chs", "chinese-simplified"):
        return "zh-cn"
    if normalized in ("zh-tw", "zh_tw", "zh-hant", "zh_hant", "tw", "cht", "chinese-traditional"):
        return "zh-tw"
    if normalized in ("ko", "kr", "kor", "korean"):
        return "ko"
    raise HTTPException(400, "language は ja/en/zh-cn/zh-tw/ko のみ指定できます")


def translation_target_languages(
    source_language: str,
    *,
    novel_translation_original_only: bool,
    novel_translation_ja_en_only: bool,
    novel_translation_all_languages: bool,
) -> list[str]:
    src = normalize_language(source_language)
    if novel_translation_original_only:
        return []
    if novel_translation_ja_en_only:
        return [lang for lang in ("ja", "en") if lang != src]
    if novel_translation_all_languages:
        return [lang for lang in ("ja", "en", "zh-cn", "zh-tw", "ko") if lang != src]
    if src == "ja":
        return ["en", "zh-cn", "zh-tw", "ko"]
    if src in ("en", "zh-cn", "zh-tw", "ko"):
        return ["ja"]
    return ["en"]


def serialize_tag_names(tag_names: list[str]) -> str | None:
    if not tag_names:
        return None
    return json.dumps(tag_names, ensure_ascii=True)


def deserialize_tag_names(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(v) for v in parsed if str(v).strip()]
    except Exception:
        pass
    return [value for value in value.split(",") if value]


def normalize_translated_tags(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,\n]", value) if part.strip()]
    return []
