from fastapi import HTTPException, Request
from sqlalchemy.orm import Session


def _payload_value(payload, key, default=None):
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)


async def generate_tag_candidates_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(400, "本文が空です。")
    source_text = text[:1000]
    candidates, tokens, model = await legacy.call_openai_tag_candidates(
        source_text,
        model=getattr(user, "ai_tag_model", None),
    )
    return legacy.TagCandidatesOut(candidates=candidates, model=model, used_tokens=tokens)


async def generate_summary_candidates_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(400, "本文が空です。")
    source_text = text[:3000]
    candidates, tokens, model = await legacy.call_openai_summary_candidates(
        source_text,
        model=getattr(user, "ai_summary_model", None),
    )
    limit = max(1, min(8, int(getattr(payload, "suggestions_count", 4) or 4)))
    return legacy.NovelSummaryCandidatesOut(
        candidates=[str(c or "").strip() for c in (candidates or []) if str(c or "").strip()][:limit],
        model=model,
        used_tokens=tokens,
    )


async def generate_title_candidate_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(400, "本文が空です。")
    source_text = text[:2000]
    title, tokens, model = await legacy.call_openai_title_candidate(
        source_text,
        model=getattr(user, "ai_title_model", None),
    )
    return legacy.TitleCandidateOut(title=title, model=model, used_tokens=tokens)


async def generate_title_candidates_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(400, "本文が空です。")
    source_text = text[:2200]
    count = max(2, min(8, int(payload.suggestions_count or 5)))
    candidates, tokens, model = await legacy.call_openai_title_candidates(
        source_text,
        model=getattr(user, "ai_title_model", None),
        suggestions_count=count,
    )
    return legacy.TitleCandidatesOut(candidates=candidates, model=model, used_tokens=tokens)


async def extract_ai_character_terms_service(*, payload):
    from .. import main as legacy

    source = "\n".join(
        [
            str(payload.title or "").strip(),
            str(payload.description or "").strip(),
            str(payload.tags or "").strip(),
        ]
    ).strip()
    if not source:
        return {"terms": []}

    limit = max(1, min(20, int(payload.limit or 8)))
    terms: list[str] = []
    seen: set[str] = set()

    for item in legacy._split_character_fullname_terms(source) + legacy._split_character_terms(source):
        term = str(item or "").strip()
        if len(term) < 2 or term in seen:
            continue
        seen.add(term)
        terms.append(term)
        if len(terms) >= limit:
            break

    return {"terms": terms}


def get_ai_novel_remaining_service(*, request: Request, response, db: Session):
    from .. import main as legacy

    guest_id = legacy.get_or_set_ai_guest_id(request, response)
    usage = legacy.get_guest_ai_usage(db, guest_id)
    guest_remaining = max(0, legacy.AI_GUEST_FREE_MAX - int(getattr(usage, "generate_count", 0) or 0))

    try:
        user = legacy.get_optional_current_user(request, db)
    except legacy.HTTPException:
        user = None

    user_remaining = None
    user_base_remaining = None
    user_paid_remaining = None
    if legacy.is_effective_premium_user(user):
        user_remaining, user_base_remaining, user_paid_remaining = legacy._ai_novel_remaining_for_user(db, user)

    return {
        "guest_remaining": guest_remaining,
        "user_remaining": user_remaining,
        "user_base_remaining": user_base_remaining,
        "user_paid_remaining": user_paid_remaining,
        "addon_unit_generations": max(1, legacy.AI_NOVEL_ADDON_UNIT_GENERATIONS),
        "addon_unit_price_yen": max(1, legacy.AI_NOVEL_ADDON_PRICE_YEN),
    }


async def _auto_fill_ai_novel_inputs_service_impl(*, query: str | None = None, characters: str | None = None):
    from .. import main as legacy

    q = (query or "").strip()
    c = (characters or "").strip()
    if not q and not c:
        raise HTTPException(400, "検索キーワードが空です。")
    if not legacy.GOOGLE_CSE_API_KEY or not legacy.GOOGLE_CSE_CX:
        raise HTTPException(500, "Google Custom Search の API 設定がありません。")

    terms = []
    if q:
        terms.extend(legacy._split_search_terms(q))
    if c:
        fullname_terms = legacy._split_character_fullname_terms(c)
        if fullname_terms:
            for name in fullname_terms[:6]:
                safe_name = name.replace('"', "").strip()
                if safe_name:
                    terms.append(f'"{safe_name}"')
            if len(fullname_terms) >= 2:
                safe_names = [n.replace('"', "").strip() for n in fullname_terms[:3] if n.strip()]
                joined = " ".join(f'"{name}"' for name in safe_names if name)
                if joined:
                    terms.append(joined)
        terms.extend(legacy._split_character_terms(c))
    if not terms:
        raise HTTPException(400, "検索キーワードが空です。")

    seen = set()
    merged_terms = []
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        merged_terms.append(term)
    terms = merged_terms[:10]

    aggregated_items: list[dict] = []
    pick_count = 15
    try:
        async with legacy.httpx.AsyncClient(timeout=10.0) as client:
            for term in terms:
                params = {
                    "key": legacy.GOOGLE_CSE_API_KEY,
                    "cx": legacy.GOOGLE_CSE_CX,
                    "q": term,
                    "num": 5,
                    "gl": "jp",
                    "hl": "ja",
                    "lr": "lang_ja",
                }
                res = await client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params=params,
                )
                if res.status_code != 200:
                    detail = res.text[:300]
                    raise HTTPException(
                        status_code=502,
                        detail=f"検索 API が失敗しました (status={res.status_code}): {detail}",
                    )
                data = res.json() if res.content else {}
                items = data.get("items") or []
                if isinstance(items, list):
                    aggregated_items.extend(items)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"検索 API の呼び出しに失敗しました: {e!r}")

    preferred = [i for i in aggregated_items if legacy._is_preferred_cse_host(i.get("link"))]
    picked = preferred[:pick_count] if preferred else aggregated_items[:pick_count]
    genre_append, characters_append = legacy._build_auto_fill_snippets(picked)
    primary_character = ""
    if c:
        full_terms_for_title = legacy._split_character_fullname_terms(c)
        if full_terms_for_title:
            primary_character = full_terms_for_title[0]
        else:
            char_terms_for_title = legacy._split_character_terms(c)
            if char_terms_for_title:
                primary_character = char_terms_for_title[0]
    if not primary_character:
        primary_character = q
    from .. import ai_source_helpers

    source_title_candidates = ai_source_helpers._extract_title_candidates_from_source_titles(
        character_name=primary_character,
        sources=picked,
        limit=8,
    )
    inferred_source_title = source_title_candidates[0] if source_title_candidates else ""

    return {
        "query": q,
        "characters_query": c,
        "terms": terms,
        "genre_append": genre_append,
        "characters_append": characters_append,
        "inferred_source_title": inferred_source_title,
        "source_title_candidates": source_title_candidates,
        "sources": [
            {
                "title": (i.get("title") or "").strip(),
                "link": i.get("link"),
                "snippet": (i.get("snippet") or "").strip(),
            }
            for i in picked
        ],
    }


async def auto_fill_ai_novel_inputs_service(*, query: str | None = None, characters: str | None = None):
    return await _auto_fill_ai_novel_inputs_service_impl(query=query, characters=characters)


async def auto_fill_ai_novel_inputs_post_service(*, payload):
    return await _auto_fill_ai_novel_inputs_service_impl(
        query=_payload_value(payload, "query"),
        characters=_payload_value(payload, "characters"),
    )
