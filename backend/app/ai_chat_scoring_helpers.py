import hashlib
from typing import Any, Literal


def _score_ai_chat_followup_latency(latency_seconds: float | None) -> tuple[float, str]:
    sec = min(300.0, max(0.0, float(latency_seconds or 0.0)))
    if sec <= 20.0:
        return 1.0, "instant"
    if sec <= 45.0:
        return 0.8, "very_fast"
    if sec <= 90.0:
        return 0.5, "fast"
    if sec <= 180.0:
        return 0.25, "normal"
    return 0.0, "slow"


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _build_ai_chat_profile_key(
    *,
    character_name: str,
    personality: str,
    speech_gender: str | None = None,
    normalize_speech_gender: Any,
) -> str:
    normalized_name = " ".join(str(character_name or "").strip().lower().split())
    normalized_gender = normalize_speech_gender(speech_gender)
    payload = f"{normalized_name}||{normalized_gender}"
    if not payload.strip("|"):
        payload = "default_profile"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _calc_user_personalization_weight(user_samples: int) -> float:
    n = max(0, int(user_samples or 0))
    if n < 8:
        return 0.0
    if n < 24:
        return 0.2 + ((n - 8) / 16.0) * 0.45
    return 0.85


def _update_profile_learning_stats(
    db: Any,
    *,
    profile_key: str,
    detail_scores: dict[str, float],
    models: Any,
) -> None:
    key = str(profile_key or "").strip()
    if not key:
        return
    row = (
        db.query(models.AIChatProfileLearningStat)
        .filter(models.AIChatProfileLearningStat.profile_key == key)
        .first()
    )
    if row is None:
        row = models.AIChatProfileLearningStat(
            profile_key=key,
            sample_count=0,
        )
        db.add(row)
        db.flush()

    prev_count = int(getattr(row, "sample_count", 0) or 0)
    next_count = prev_count + 1

    def rolling(prev_avg: float, new_value: float) -> float:
        if prev_count <= 0:
            return float(new_value)
        return ((float(prev_avg) * prev_count) + float(new_value)) / next_count

    row.sample_count = next_count
    row.average_engagement_score = rolling(getattr(row, "average_engagement_score", 0.0), detail_scores.get("engagement_score", 0.0))
    row.average_latency_score = rolling(getattr(row, "average_latency_score", 0.0), detail_scores.get("latency_score", 0.0))
    row.average_intimacy_score = rolling(getattr(row, "average_intimacy_score", 0.0), detail_scores.get("intimacy_score", 0.0))
    row.average_proactiveness_score = rolling(getattr(row, "average_proactiveness_score", 0.0), detail_scores.get("proactiveness_score", 0.0))
    row.average_empathy_score = rolling(getattr(row, "average_empathy_score", 0.0), detail_scores.get("empathy_score", 0.0))
    row.average_cuteness_score = rolling(getattr(row, "average_cuteness_score", 0.0), detail_scores.get("cuteness_score", 0.0))
    row.average_consistency_score = rolling(getattr(row, "average_consistency_score", 0.0), detail_scores.get("consistency_score", 0.0))
    row.average_novelty_score = rolling(getattr(row, "average_novelty_score", 0.0), detail_scores.get("novelty_score", 0.0))
    row.average_clarity_score = rolling(getattr(row, "average_clarity_score", 0.0), detail_scores.get("clarity_score", 0.0))
    row.average_coolness_score = rolling(getattr(row, "average_coolness_score", 0.0), detail_scores.get("coolness_score", 0.0))
    row.average_seriousness_score = rolling(getattr(row, "average_seriousness_score", 0.0), detail_scores.get("seriousness_score", 0.0))
    db.add(row)


def _normalized_keyword_score(text: str, keywords: list[str], *, cap_hits: int, clip01: Any) -> float:
    normalized = str(text or "").lower()
    if not normalized:
        return 0.0
    hits = 0
    for kw in keywords:
        if not kw:
            continue
        hits += normalized.count(str(kw).lower())
    return clip01(hits / max(1, cap_hits))


def _extract_personality_keywords(personality_hint: str, max_items: int = 8, *, re_module: Any = None) -> list[str]:
    words = re_module.findall(r"[ぁ-んァ-ヴー一-龥A-Za-z]{2,}", str(personality_hint or ""))
    uniq: list[str] = []
    for w in words:
        token = str(w).strip().lower()
        if len(token) < 2:
            continue
        if token in uniq:
            continue
        uniq.append(token)
        if len(uniq) >= max_items:
            break
    return uniq


def _estimate_ai_reply_scores(
    *,
    assistant_content: str,
    personality_hint: str = "",
    assistant_mode: str = "say",
    character_gender: Literal["auto", "female", "male"] = "auto",
    latency_score: float = 0.0,
    clip01: Any,
    normalized_keyword_score: Any,
    extract_personality_keywords: Any,
    re_module: Any,
) -> dict[str, float]:
    text = str(assistant_content or "").strip()
    if not text:
        return {
            "latency_score": clip01(latency_score),
            "intimacy_score": 0.0,
            "cuteness_score": 0.0,
            "proactiveness_score": 0.0,
            "consistency_score": 0.0,
            "empathy_score": 0.0,
            "novelty_score": 0.0,
            "clarity_score": 0.0,
            "coolness_score": 0.0,
            "seriousness_score": 0.0,
            "engagement_score": clip01(latency_score),
        }

    intimacy_keywords = ["好き", "愛", "大切", "そば", "一緒", "抱き", "ぎゅ", "キス", "恋人", "会いた", "darling", "love", "dear"]
    cuteness_keywords = ["かわいい", "えへ", "ふふ", "にゃ", "なの", "だよ", "♡", "♪", "きゅん", "ふわ"]
    proactive_keywords = ["しよう", "やろう", "行こう", "任せて", "まず", "次に", "今から", "私が", "提案", "試そう", "let's", "i will", "first"]
    empathy_keywords = ["わかる", "気持ち", "大丈夫", "無理しない", "つら", "しんど", "安心", "寄り添", "嬉しい", "悲しい", "i understand", "it's okay"]
    clarity_keywords = ["まず", "次に", "最後に", "つまり", "要するに", "具体的", "結論", "理由", "だから", "そのうえで"]
    coolness_keywords = ["冷静", "鋭い", "余裕", "堂々", "頼れる", "守る", "強い", "キメ", "決める", "信念", "cool", "calm", "confident"]
    seriousness_keywords = ["真面目", "誠実", "責任", "約束", "計画", "丁寧", "慎重", "優先", "必要", "重要", "sincere", "responsible", "careful"]

    intimacy_score = normalized_keyword_score(text, intimacy_keywords, cap_hits=4)
    cuteness_score = normalized_keyword_score(text, cuteness_keywords, cap_hits=4)
    proactiveness_score = normalized_keyword_score(text, proactive_keywords, cap_hits=4)
    empathy_score = normalized_keyword_score(text, empathy_keywords, cap_hits=4)
    coolness_score = normalized_keyword_score(text, coolness_keywords, cap_hits=4)
    seriousness_score = normalized_keyword_score(text, seriousness_keywords, cap_hits=4)

    if assistant_mode == "do":
        proactiveness_score = clip01(proactiveness_score + 0.15)

    personality_keywords = extract_personality_keywords(personality_hint, max_items=8)
    consistency_score = normalized_keyword_score(text, personality_keywords, cap_hits=max(2, len(personality_keywords)))

    tokens = re_module.findall(r"[ぁ-んァ-ヴー一-龥A-Za-z0-9]+", text)
    uniq_ratio = (len(set(tokens)) / len(tokens)) if tokens else 0.0
    length_bonus = clip01(len(text) / 220.0)
    repetition_penalty = 0.25 if re_module.search(r"(.{4,12})\1{1,}", text) else 0.0
    novelty_score = clip01((uniq_ratio * 0.45) + (length_bonus * 0.55) - repetition_penalty)

    punctuation_count = len(re_module.findall(r"[。！？!?]", text))
    clarity_base = 0.35
    if punctuation_count >= 1:
        clarity_base += 0.2
    if len(text) >= 45:
        clarity_base += 0.15
    clarity_base += normalized_keyword_score(text, clarity_keywords, cap_hits=3) * 0.3
    clarity_score = clip01(clarity_base)

    latency = clip01(latency_score)
    engagement_score = clip01(
        (latency * (0.26 if character_gender == "male" else 0.30))
        + (intimacy_score * 0.12)
        + (cuteness_score * (0.03 if character_gender == "male" else 0.09))
        + (proactiveness_score * 0.14)
        + (consistency_score * 0.10)
        + (empathy_score * 0.10)
        + (novelty_score * 0.07)
        + (clarity_score * 0.06)
        + (coolness_score * (0.07 if character_gender == "male" else 0.01))
        + (seriousness_score * (0.05 if character_gender == "male" else 0.01))
    )
    return {
        "latency_score": latency,
        "intimacy_score": intimacy_score,
        "cuteness_score": cuteness_score,
        "proactiveness_score": proactiveness_score,
        "consistency_score": consistency_score,
        "empathy_score": empathy_score,
        "novelty_score": novelty_score,
        "clarity_score": clarity_score,
        "coolness_score": coolness_score,
        "seriousness_score": seriousness_score,
        "engagement_score": engagement_score,
    }


def _estimate_user_followup_signal_scores(
    *,
    user_content: str,
    latency_score: float = 0.0,
    normalized_keyword_score: Any,
    clip01: Any,
) -> dict[str, float]:
    text = str(user_content or "").strip()
    if not text:
        return {
            "latency_score": clip01(latency_score),
            "intimacy_score": 0.0,
            "proactiveness_score": 0.0,
            "empathy_score": 0.0,
        }
    intimacy_keywords = ["好き", "会いたい", "一緒", "そば", "大事", "嬉しい", "ありがとう", "もっと話したい", "love", "dear", "miss you"]
    proactive_keywords = ["しよう", "やろう", "行こう", "今から", "次は", "こうして", "提案", "決めた", "let's", "i will", "next"]
    empathy_keywords = ["わかる", "共感", "気持ち", "つらい", "しんどい", "大丈夫", "無理しない", "安心して", "i understand", "i feel you", "it's okay"]

    intimacy_score = normalized_keyword_score(text, intimacy_keywords, cap_hits=4)
    proactiveness_score = normalized_keyword_score(text, proactive_keywords, cap_hits=4)
    empathy_score = normalized_keyword_score(text, empathy_keywords, cap_hits=4)

    text_len = len(text)
    if text_len >= 50:
        intimacy_score = clip01(intimacy_score + 0.08)
        empathy_score = clip01(empathy_score + 0.05)
    if "?" in text or "？" in text:
        proactiveness_score = clip01(proactiveness_score + 0.08)

    return {
        "latency_score": clip01(latency_score),
        "intimacy_score": intimacy_score,
        "proactiveness_score": proactiveness_score,
        "empathy_score": empathy_score,
    }


def _record_ai_chat_followup_feedback(
    db: Any,
    *,
    user_id: int,
    character_id: int,
    assistant_message_id: int,
    followup_user_message_id: int | None,
    latency_seconds: float,
    assistant_content: str = "",
    personality_hint: str = "",
    assistant_mode: str = "say",
    character_gender: Literal["auto", "female", "male"] = "auto",
    followup_user_content: str = "",
    character_profile_key: str = "",
    models: Any,
    score_ai_chat_followup_latency: Any,
    estimate_ai_reply_scores: Any,
    estimate_user_followup_signal_scores: Any,
    clip01: Any,
    update_profile_learning_stats: Any,
) -> None:
    existing = (
        db.query(models.AIChatTurnFeedback.id)
        .filter(models.AIChatTurnFeedback.assistant_message_id == int(assistant_message_id))
        .first()
    )
    if existing:
        return
    normalized_latency_seconds = min(300.0, max(0.0, float(latency_seconds or 0.0)))
    latency_score, bucket = score_ai_chat_followup_latency(normalized_latency_seconds)
    detail_scores = estimate_ai_reply_scores(
        assistant_content=assistant_content,
        personality_hint=personality_hint,
        assistant_mode=assistant_mode,
        character_gender=character_gender,
        latency_score=latency_score,
    )
    user_signal_scores = estimate_user_followup_signal_scores(
        user_content=followup_user_content,
        latency_score=latency_score,
    )
    detail_scores["latency_score"] = float(user_signal_scores.get("latency_score", latency_score))
    detail_scores["intimacy_score"] = float(user_signal_scores.get("intimacy_score", 0.0))
    detail_scores["proactiveness_score"] = float(user_signal_scores.get("proactiveness_score", 0.0))
    detail_scores["empathy_score"] = float(user_signal_scores.get("empathy_score", 0.0))
    detail_scores["engagement_score"] = clip01(
        (detail_scores["latency_score"] * 0.34)
        + (detail_scores["intimacy_score"] * 0.20)
        + (detail_scores["proactiveness_score"] * 0.20)
        + (detail_scores["empathy_score"] * 0.16)
        + (float(detail_scores.get("consistency_score", 0.0)) * 0.04)
        + (float(detail_scores.get("clarity_score", 0.0)) * 0.03)
        + (float(detail_scores.get("novelty_score", 0.0)) * 0.03)
    )
    db.add(
        models.AIChatTurnFeedback(
            user_id=int(user_id),
            character_id=int(character_id),
            assistant_message_id=int(assistant_message_id),
            followup_user_message_id=int(followup_user_message_id) if followup_user_message_id else None,
            character_profile_key=str(character_profile_key or "").strip(),
            followup_latency_seconds=normalized_latency_seconds,
            latency_score=float(detail_scores.get("latency_score", latency_score)),
            intimacy_score=float(detail_scores.get("intimacy_score", 0.0)),
            cuteness_score=float(detail_scores.get("cuteness_score", 0.0)),
            proactiveness_score=float(detail_scores.get("proactiveness_score", 0.0)),
            consistency_score=float(detail_scores.get("consistency_score", 0.0)),
            empathy_score=float(detail_scores.get("empathy_score", 0.0)),
            novelty_score=float(detail_scores.get("novelty_score", 0.0)),
            clarity_score=float(detail_scores.get("clarity_score", 0.0)),
            coolness_score=float(detail_scores.get("coolness_score", 0.0)),
            seriousness_score=float(detail_scores.get("seriousness_score", 0.0)),
            engagement_score=float(detail_scores.get("engagement_score", latency_score)),
            latency_bucket=bucket,
            score_version="v3_10d",
        )
    )
    update_profile_learning_stats(
        db,
        profile_key=str(character_profile_key or "").strip(),
        detail_scores=detail_scores,
    )


def _build_ai_chat_engagement_learning_instruction(
    db: Any,
    *,
    viewer: Any | None,
    character: Any | None,
    query_text: str | None = None,
    vector_context_text: str | None = None,
    models: Any,
    build_ai_chat_profile_key: Any,
    calc_user_personalization_weight: Any,
    clip01: Any,
    normalize_speech_gender: Any,
    retrieve_memories: Any,
    resolve_memory_scope: Any,
    format_long_term_memories: Any,
    ai_chat_memory_topk: int,
    re_module: Any,
) -> str:
    if viewer is None or character is None:
        return ""
    profile_key = build_ai_chat_profile_key(
        character_name=str(getattr(character, "name", "") or ""),
        personality=str(getattr(character, "personality", "") or ""),
        speech_gender=str(getattr(character, "speech_gender", "auto") or "auto"),
    )
    profile_stat = (
        db.query(models.AIChatProfileLearningStat)
        .filter(models.AIChatProfileLearningStat.profile_key == profile_key)
        .first()
    )
    rows = (
        db.query(models.AIChatTurnFeedback)
        .filter(models.AIChatTurnFeedback.character_profile_key == profile_key)
        .order_by(models.AIChatTurnFeedback.id.desc())
        .limit(40)
        .all()
    )
    if not rows:
        rows = (
            db.query(models.AIChatTurnFeedback)
            .filter(models.AIChatTurnFeedback.character_id == int(character.id))
            .order_by(models.AIChatTurnFeedback.id.desc())
            .limit(40)
            .all()
        )
    user_rows = (
        db.query(models.AIChatTurnFeedback)
        .filter(
            models.AIChatTurnFeedback.user_id == int(viewer.id),
            models.AIChatTurnFeedback.character_profile_key == profile_key,
        )
        .order_by(models.AIChatTurnFeedback.id.desc())
        .limit(40)
        .all()
    )
    if not user_rows:
        user_rows = (
            db.query(models.AIChatTurnFeedback)
            .filter(
                models.AIChatTurnFeedback.user_id == int(viewer.id),
                models.AIChatTurnFeedback.character_id == int(character.id),
            )
            .order_by(models.AIChatTurnFeedback.id.desc())
            .limit(40)
            .all()
        )
    if not rows and profile_stat is None:
        return ""

    def _avg_from_rows(items: list[Any], attr: str) -> float:
        if not items:
            return 0.0
        vals = [float(getattr(r, attr, 0.0) or 0.0) for r in items]
        return float(sum(vals) / len(vals)) if vals else 0.0

    if profile_stat is not None:
        global_avg_score = float(getattr(profile_stat, "average_engagement_score", 0.0) or 0.0)
        global_avg_latency = float(getattr(profile_stat, "average_latency_score", 0.0) or 0.0)
        global_avg_intimacy = float(getattr(profile_stat, "average_intimacy_score", 0.0) or 0.0)
        global_avg_cuteness = float(getattr(profile_stat, "average_cuteness_score", 0.0) or 0.0)
        global_avg_proactive = float(getattr(profile_stat, "average_proactiveness_score", 0.0) or 0.0)
        global_avg_consistency = float(getattr(profile_stat, "average_consistency_score", 0.0) or 0.0)
        global_avg_empathy = float(getattr(profile_stat, "average_empathy_score", 0.0) or 0.0)
        global_avg_novelty = float(getattr(profile_stat, "average_novelty_score", 0.0) or 0.0)
        global_avg_clarity = float(getattr(profile_stat, "average_clarity_score", 0.0) or 0.0)
        global_avg_coolness = float(getattr(profile_stat, "average_coolness_score", 0.0) or 0.0)
        global_avg_seriousness = float(getattr(profile_stat, "average_seriousness_score", 0.0) or 0.0)
    else:
        global_avg_score = _avg_from_rows(rows, "engagement_score")
        global_avg_latency = _avg_from_rows(rows, "latency_score")
        global_avg_intimacy = _avg_from_rows(rows, "intimacy_score")
        global_avg_cuteness = _avg_from_rows(rows, "cuteness_score")
        global_avg_proactive = _avg_from_rows(rows, "proactiveness_score")
        global_avg_consistency = _avg_from_rows(rows, "consistency_score")
        global_avg_empathy = _avg_from_rows(rows, "empathy_score")
        global_avg_novelty = _avg_from_rows(rows, "novelty_score")
        global_avg_clarity = _avg_from_rows(rows, "clarity_score")
        global_avg_coolness = _avg_from_rows(rows, "coolness_score")
        global_avg_seriousness = _avg_from_rows(rows, "seriousness_score")

    user_avg_score = _avg_from_rows(user_rows, "engagement_score")
    user_avg_latency = _avg_from_rows(user_rows, "latency_score")
    user_avg_intimacy = _avg_from_rows(user_rows, "intimacy_score")
    user_avg_cuteness = _avg_from_rows(user_rows, "cuteness_score")
    user_avg_proactive = _avg_from_rows(user_rows, "proactiveness_score")
    user_avg_consistency = _avg_from_rows(user_rows, "consistency_score")
    user_avg_empathy = _avg_from_rows(user_rows, "empathy_score")
    user_avg_novelty = _avg_from_rows(user_rows, "novelty_score")
    user_avg_clarity = _avg_from_rows(user_rows, "clarity_score")
    user_avg_coolness = _avg_from_rows(user_rows, "coolness_score")
    user_avg_seriousness = _avg_from_rows(user_rows, "seriousness_score")

    user_weight = calc_user_personalization_weight(len(user_rows))
    global_weight = 1.0 - user_weight

    avg_score = (user_avg_score * user_weight) + (global_avg_score * global_weight)
    avg_latency = (user_avg_latency * user_weight) + (global_avg_latency * global_weight)
    avg_intimacy = (user_avg_intimacy * user_weight) + (global_avg_intimacy * global_weight)
    avg_cuteness = (user_avg_cuteness * user_weight) + (global_avg_cuteness * global_weight)
    avg_proactive = (user_avg_proactive * user_weight) + (global_avg_proactive * global_weight)
    avg_consistency = (user_avg_consistency * user_weight) + (global_avg_consistency * global_weight)
    avg_empathy = (user_avg_empathy * user_weight) + (global_avg_empathy * global_weight)
    avg_novelty = (user_avg_novelty * user_weight) + (global_avg_novelty * global_weight)
    avg_clarity = (user_avg_clarity * user_weight) + (global_avg_clarity * global_weight)
    avg_coolness = (user_avg_coolness * user_weight) + (global_avg_coolness * global_weight)
    avg_seriousness = (user_avg_seriousness * user_weight) + (global_avg_seriousness * global_weight)
    instant_rate = clip01(avg_latency)

    top_rows = sorted(rows, key=lambda x: float(getattr(x, "engagement_score", 0.0) or 0.0), reverse=True)[:3]
    top_msg_ids = [int(r.assistant_message_id) for r in top_rows if getattr(r, "assistant_message_id", None)]
    top_lines: list[str] = []
    if top_msg_ids:
        top_msgs = (
            db.query(models.AIChatMessage.id, models.AIChatMessage.content)
            .filter(models.AIChatMessage.id.in_(top_msg_ids))
            .all()
        )
        by_id = {int(mid): str(content or "") for mid, content in top_msgs}
        for rid in top_msg_ids:
            text_snippet = re_module.sub(r"\s+", " ", by_id.get(int(rid), "")).strip()[:120]
            if text_snippet:
                top_lines.append(f"- {text_snippet}")

    gender = normalize_speech_gender(getattr(character, "speech_gender", None))
    if user_weight >= 0.80:
        phase_note = "後半フェーズ（ユーザー最適化強）"
    elif user_weight >= 0.20:
        phase_note = "中盤フェーズ（ユーザー最適化へ移行）"
    else:
        phase_note = "序盤フェーズ（グローバル学習優先）"
    weak_pool = [
        ("親密度", avg_intimacy),
        ("積極度", avg_proactive),
        ("整合度", avg_consistency),
        ("共感度", avg_empathy),
        ("新規性", avg_novelty),
        ("明瞭さ", avg_clarity),
    ]
    if gender == "male":
        weak_pool.extend([
            ("かっこよさ", avg_coolness),
            ("まじめさ", avg_seriousness),
        ])
    else:
        weak_pool.append(("かわいさ", avg_cuteness))
    weak_dimensions = sorted(weak_pool, key=lambda x: x[1])[:2]
    weak_names = "・".join([name for name, _ in weak_dimensions]) if weak_dimensions else "なし"
    if avg_score >= 0.70:
        tuning = "全体良好。テンポと関係性を維持し、毎回1つだけ新しい展開を追加。"
    elif avg_score >= 0.45:
        tuning = f"中間。弱い軸（{weak_names}）を優先補強し、短い問いかけで継続率を上げる。"
    else:
        tuning = f"改善余地大。弱い軸（{weak_names}）を最優先し、結論先出し+次アクション提示。"

    example_block = "\n".join(top_lines) if top_lines else "- （高評価履歴なし）"
    vector_lines: list[str] = []
    raw_vector_text = str(vector_context_text or "").strip()
    if not raw_vector_text and query_text and viewer is not None and character is not None:
        try:
            mem_scope, mem_scope_id = resolve_memory_scope(int(character.id))
            vec_memories = retrieve_memories(
                db,
                user_id=int(viewer.id),
                scope=mem_scope,
                scope_id=mem_scope_id,
                query_text=str(query_text),
                topk=min(6, ai_chat_memory_topk),
            )
            raw_vector_text = format_long_term_memories(vec_memories, max_items=4) or ""
        except Exception:
            raw_vector_text = ""
    if raw_vector_text:
        for line in str(raw_vector_text).splitlines():
            text = str(line or "").strip()
            if not text:
                continue
            vector_lines.append(text[:140])
            if len(vector_lines) >= 3:
                break
    vector_block = "\n".join([f"- {v}" for v in vector_lines]) if vector_lines else "- （類似メモなし）"
    return (
        "【継続入力学習フィードバック】\n"
        f"- 即レス率(<=45秒): {instant_rate:.0%}\n"
        f"- 総合: {avg_score:.2f}\n"
        f"- 速度: {avg_latency:.2f}\n"
        f"- 親密度: {avg_intimacy:.2f}\n"
        f"- かわいさ: {avg_cuteness:.2f}\n"
        f"- 積極度: {avg_proactive:.2f}\n"
        f"- 設定整合度: {avg_consistency:.2f}\n"
        f"- 共感度: {avg_empathy:.2f}\n"
        f"- 新規性: {avg_novelty:.2f}\n"
        f"- 明瞭さ: {avg_clarity:.2f}\n"
        f"- かっこよさ: {avg_coolness:.2f}\n"
        f"- まじめさ: {avg_seriousness:.2f}\n"
        f"- 個人最適化重み: {user_weight:.0%}\n"
        f"- 学習フェーズ: {phase_note}\n"
        "- ベクトル類似メモ（解析参照）:\n"
        f"{vector_block}\n"
        f"- 調整方針: {tuning}\n"
        "- 直近高評価返信の要素を参考にする（内容のコピペは禁止）:\n"
        f"{example_block}\n"
    )


def _build_ai_chat_recommendation_map(
    db: Any,
    *,
    user_id: int,
    character_ids: list[int],
    models: Any,
    func: Any,
    build_ai_chat_profile_key: Any,
    calc_user_personalization_weight: Any,
    clip01: Any,
) -> dict[int, dict]:
    if not character_ids:
        return {}
    character_rows = (
        db.query(
            models.AIChatCharacter.id,
            models.AIChatCharacter.name,
            models.AIChatCharacter.personality,
            models.AIChatCharacter.speech_gender,
        )
        .filter(models.AIChatCharacter.id.in_(character_ids))
        .all()
    )
    if not character_rows:
        return {}

    char_to_key: dict[int, str] = {}
    profile_keys: list[str] = []
    for cid, name, personality, speech_gender in character_rows:
        key = build_ai_chat_profile_key(
            character_name=str(name or ""),
            personality=str(personality or ""),
            speech_gender=str(speech_gender or "auto"),
        )
        char_to_key[int(cid)] = key
        profile_keys.append(key)

    global_rows = (
        db.query(models.AIChatProfileLearningStat)
        .filter(models.AIChatProfileLearningStat.profile_key.in_(profile_keys))
        .all()
    )
    global_map = {
        str(getattr(r, "profile_key", "") or ""): r
        for r in global_rows
        if str(getattr(r, "profile_key", "") or "")
    }
    agg_rows = (
        db.query(
            models.AIChatTurnFeedback.character_profile_key,
            func.count(models.AIChatTurnFeedback.id),
            func.avg(models.AIChatTurnFeedback.latency_score),
            func.avg(models.AIChatTurnFeedback.intimacy_score),
            func.avg(models.AIChatTurnFeedback.proactiveness_score),
            func.avg(models.AIChatTurnFeedback.empathy_score),
        )
        .filter(
            models.AIChatTurnFeedback.user_id == int(user_id),
            models.AIChatTurnFeedback.character_profile_key.in_(profile_keys),
        )
        .group_by(models.AIChatTurnFeedback.character_profile_key)
        .all()
    )
    user_map = {
        str(k): {
            "samples": int(c or 0),
            "latency": float(lat or 0.0),
            "intimacy": float(inti or 0.0),
            "proactive": float(pro or 0.0),
            "empathy": float(emp or 0.0),
        }
        for k, c, lat, inti, pro, emp in agg_rows
        if str(k or "").strip()
    }

    def _score(latency: float, intimacy: float, proactive: float, empathy: float) -> float:
        return clip01(
            (float(latency) * 0.30)
            + (float(intimacy) * 0.24)
            + (float(proactive) * 0.24)
            + (float(empathy) * 0.22)
        )

    result: dict[int, dict] = {}
    for cid in character_ids:
        key = char_to_key.get(int(cid), "")
        global_stat = global_map.get(key)
        user_stat = user_map.get(key)
        global_score = _score(
            float(getattr(global_stat, "average_latency_score", 0.0) or 0.0),
            float(getattr(global_stat, "average_intimacy_score", 0.0) or 0.0),
            float(getattr(global_stat, "average_proactiveness_score", 0.0) or 0.0),
            float(getattr(global_stat, "average_empathy_score", 0.0) or 0.0),
        ) if global_stat is not None else 0.0
        global_samples = int(getattr(global_stat, "sample_count", 0) or 0) if global_stat is not None else 0

        user_score = _score(
            float(user_stat.get("latency", 0.0)),
            float(user_stat.get("intimacy", 0.0)),
            float(user_stat.get("proactive", 0.0)),
            float(user_stat.get("empathy", 0.0)),
        ) if user_stat else 0.0
        user_samples = int(user_stat.get("samples", 0)) if user_stat else 0

        user_weight = calc_user_personalization_weight(user_samples)
        blended = (user_score * user_weight) + (global_score * (1.0 - user_weight))
        combined_samples = max(global_samples, user_samples)
        result[int(cid)] = {
            "score": blended,
            "samples": combined_samples,
            "is_recommended": bool(combined_samples >= 3 and blended >= 0.45),
        }
    return result


def _build_public_profile_recommendation_map(
    db: Any,
    *,
    profile_keys: list[str],
    models: Any,
    clip01: Any,
) -> dict[str, dict]:
    keys = [str(k or "").strip() for k in profile_keys if str(k or "").strip()]
    if not keys:
        return {}
    rows = (
        db.query(models.AIChatProfileLearningStat)
        .filter(models.AIChatProfileLearningStat.profile_key.in_(keys))
        .all()
    )
    result: dict[str, dict] = {}
    for row in rows:
        key = str(getattr(row, "profile_key", "") or "").strip()
        if not key:
            continue
        score = clip01(
            (float(getattr(row, "average_latency_score", 0.0) or 0.0) * 0.30)
            + (float(getattr(row, "average_intimacy_score", 0.0) or 0.0) * 0.24)
            + (float(getattr(row, "average_proactiveness_score", 0.0) or 0.0) * 0.24)
            + (float(getattr(row, "average_empathy_score", 0.0) or 0.0) * 0.22)
        )
        samples = int(getattr(row, "sample_count", 0) or 0)
        result[key] = {
            "score": score,
            "samples": samples,
            "is_recommended": bool(samples >= 3 and score >= 0.45),
        }
    return result
