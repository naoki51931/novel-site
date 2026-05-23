import unicodedata

from . import models


_PUBLIC_CHAT_R18_HINT_KEYWORDS = (
    "18禁",
    "成人向け",
    "エロ",
    "性的",
    "sex",
    "sexual",
    "nsfw",
    "hentai",
    "淫",
    "喘ぎ",
    "快感",
    "キス",
    "裸",
    "乳首",
    "陰茎",
    "膣",
    "挿入",
    "中出し",
    "絶頂",
    "フェラ",
    "自慰",
)


def _contains_public_chat_r18_hint(text: str | None) -> bool:
    normalized = unicodedata.normalize("NFKC", str(text or "")).lower().strip()
    if not normalized:
        return False
    if "r18" in normalized:
        return True
    for keyword in _PUBLIC_CHAT_R18_HINT_KEYWORDS:
        if keyword in normalized:
            return True
    return False


def _is_public_chat_r18(
    character: models.AIChatCharacter,
    messages: list[models.AIChatMessage] | None = None,
) -> bool:
    if bool(getattr(character, "is_r18", False)):
        return True
    if _contains_public_chat_r18_hint(getattr(character, "name", None)):
        return True
    if _contains_public_chat_r18_hint(getattr(character, "personality", None)):
        return True
    for msg in messages or []:
        if _contains_public_chat_r18_hint(getattr(msg, "content", None)):
            return True
    return False


def _trim_public_character_intro(text: str | None, max_chars: int = 450) -> str | None:
    raw = str(text or "")
    if len(raw) <= max_chars:
        return raw or None
    if max_chars <= 1:
        return raw[:max_chars]
    return f"{raw[: max_chars - 1]}…"
