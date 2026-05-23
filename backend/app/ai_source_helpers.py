import re

import httpx

from .external_service_helpers import GOOGLE_CSE_API_KEY, GOOGLE_CSE_CX, _is_preferred_cse_host


def _legacy():
    from . import main as legacy

    return legacy


async def _search_character_reference_sources(
    character_name: str,
    *,
    anime_title: str | None = None,
) -> list[dict]:
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_CX:
        return []
    name = (character_name or "").strip()
    if not name:
        return []
    title = (anime_title or "").strip()
    if title:
        queries = [
            f"\"{title}\" \"{name}\" キャラクター",
            f"\"{title}\" \"{name}\" 作品",
        ]
    else:
        queries = [
            f"\"{name}\" キャラクター 性格 アニメ",
            f"\"{name}\" 作品 キャラ",
        ]
    aggregated_items: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for q in queries:
                params = {
                    "key": GOOGLE_CSE_API_KEY,
                    "cx": GOOGLE_CSE_CX,
                    "q": q,
                    "num": 5,
                    "gl": "jp",
                    "hl": "ja",
                    "lr": "lang_ja",
                }
                res = await client.get("https://www.googleapis.com/customsearch/v1", params=params)
                if res.status_code != 200:
                    continue
                data = res.json() if res.content else {}
                items = data.get("items") or []
                if isinstance(items, list):
                    aggregated_items.extend(items)
    except Exception:
        return []

    dedup: list[dict] = []
    seen: set[str] = set()
    for item in aggregated_items:
        link = str(item.get("link") or "").strip()
        if not link or link in seen:
            continue
        seen.add(link)
        dedup.append(item)

    preferred = [i for i in dedup if _is_preferred_cse_host(i.get("link"))]
    picked = preferred[:8] if preferred else dedup[:8]
    return [
        {
            "title": (i.get("title") or "").strip(),
            "link": i.get("link"),
            "snippet": (i.get("snippet") or "").strip(),
        }
        for i in picked
    ]


async def _build_fanfic_personality_from_sources(
    *,
    character_name: str,
    base_personality: str,
    model: str | None,
    provider: str | None,
    sources: list[dict],
) -> str:
    snippets: list[str] = []
    for s in sources[:8]:
        title = str(s.get("title") or "").strip()
        snippet = str(s.get("snippet") or "").strip()
        if title and snippet:
            snippets.append(f"- {title}: {snippet}")
        elif title:
            snippets.append(f"- {title}")
        elif snippet:
            snippets.append(f"- {snippet}")
    sources_text = "\n".join(snippets)[:2200]
    prompt = (
        "あなたはロールプレイ設定を作る編集者です。\n"
        "次の同名キャラ候補の検索要約を参考に、二次創作チャット用の性格設定を作ってください。\n"
        "不確かな情報は断定しないでください。\n"
        "元の性格設定があれば必ず統合してください。\n\n"
        f"キャラクター名: {character_name}\n"
        f"ユーザー指定の追加性格設定: {(base_personality or 'なし')[:1200]}\n\n"
        f"検索要約:\n{sources_text or '(なし)'}\n\n"
        "出力は必ずJSON 1個のみ。キーは personality のみ。\n"
        "personality は箇条書きで6〜10行、口調・行動方針・NG表現・関係性の扱いを含めること。\n"
        '例: {"personality":"- ..."}'
    )
    data, _, _ = await _legacy()._call_ai_chat_json_with_fallback(
        prompt,
        model=model,
        provider=provider,
        system_instructions=(
            "あなたはキャラクター設定編集AIです。"
            "必ずJSON 1個のみを返してください。"
            "キーは personality のみ。"
            "曖昧な情報は断定せず、推測表現を使ってください。"
        ),
    )
    personality = str(data.get("personality") or "").strip()
    if personality:
        return personality[:1800]

    if base_personality:
        return base_personality[:1800]
    return (
        f"- {character_name}らしい口調を維持する。\n"
        "- 感情の起伏を一貫させる。\n"
        "- 相手への反応は丁寧に段階を踏む。\n"
        "- 不明な原作情報は断定しない。"
    )


def _merge_fanfic_with_base_personality(
    *,
    fanfic_personality: str,
    base_personality: str,
) -> str:
    marker = "【二次創作モード補完】"
    base_marker = "【元の性格設定】"
    base = (base_personality or "").strip()
    fanfic = (fanfic_personality or "").strip()

    raw_base = base
    if marker in base and base_marker in base:
        try:
            raw_base = base.split(base_marker, 1)[1].strip()
        except Exception:
            raw_base = base

    if not raw_base:
        return fanfic
    if not fanfic:
        return raw_base
    if fanfic in raw_base:
        return raw_base
    return f"{marker}\n{fanfic}\n\n{base_marker}\n{raw_base}"


def _extract_title_candidates_from_source_titles(
    *,
    character_name: str,
    sources: list[dict],
    limit: int,
) -> list[str]:
    name = (character_name or "").strip()
    candidates: list[str] = []
    for s in sources[:12]:
        raw_title = str(s.get("title") or "").strip()
        if not raw_title:
            continue
        parts = re.split(r"[|\-｜:：]", raw_title)
        for part in parts:
            text = re.sub(r"\s+", " ", part).strip()
            if len(text) < 2:
                continue
            if name and text == name:
                continue
            if name and name in text and len(text) <= len(name) + 2:
                continue
            if text in candidates:
                continue
            candidates.append(text[:80])
            if len(candidates) >= limit:
                return candidates
    return candidates


async def _build_anime_title_candidates_from_sources(
    *,
    character_name: str,
    sources: list[dict],
    model: str | None,
    provider: str | None,
    limit: int,
) -> list[str]:
    snippets: list[str] = []
    for s in sources[:10]:
        title = str(s.get("title") or "").strip()
        snippet = str(s.get("snippet") or "").strip()
        if title and snippet:
            snippets.append(f"- {title}: {snippet}")
        elif title:
            snippets.append(f"- {title}")
        elif snippet:
            snippets.append(f"- {snippet}")
    sources_text = "\n".join(snippets)[:2600]
    prompt = (
        "あなたはアニメ作品名の候補抽出AIです。\n"
        "検索要約から、指定キャラクターが登場する可能性が高い作品名候補を抽出してください。\n"
        "不確かな場合は推測候補として扱ってください。\n\n"
        f"キャラクター名: {character_name}\n"
        f"検索要約:\n{sources_text or '(なし)'}\n\n"
        f"出力は必ずJSON 1個のみ。キーは candidates のみ。件数は最大 {limit} 件。\n"
        "作品名だけを短く返し、説明文は含めないこと。"
    )
    data, _, _ = await _legacy()._call_ai_chat_json_with_fallback(
        prompt,
        model=model,
        provider=provider,
        system_instructions=(
            "あなたは作品名抽出AIです。"
            "必ずJSON 1個のみを返してください。"
            "キーは candidates のみ。"
        ),
    )
    out: list[str] = []
    raw = data.get("candidates")
    if isinstance(raw, list):
        for item in raw:
            text = re.sub(r"\s+", " ", str(item or "").strip())
            if not text:
                continue
            if text in out:
                continue
            out.append(text[:80])
            if len(out) >= limit:
                break
    elif isinstance(raw, str):
        for item in re.split(r"[\r\n,、]+", raw):
            text = re.sub(r"\s+", " ", str(item or "").strip())
            if not text:
                continue
            if text in out:
                continue
            out.append(text[:80])
            if len(out) >= limit:
                break
    return out[:limit]
