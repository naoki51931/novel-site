from typing import Any, Literal


def _build_ai_chat_style_guide(long_reply: bool = False, short_reply: bool = False) -> str:
    if short_reply:
        say_length = "1文・25〜80文字程度（1行）"
        do_length = "1文・30〜90文字程度（1行）"
    else:
        say_length = "4〜8文・160〜400文字程度" if long_reply else "2〜4文・80〜200文字程度"
        do_length = "4〜8文・200〜440文字程度" if long_reply else "2〜4文・100〜220文字程度"
    line_rule = "- short_reply 有効時は say/do とも必ず1行で返す。" if short_reply else ""
    return (
        f"- say はキャラクターの口調を守り、{say_length}で返答する。\n"
        "- 複数人数のやり取りを描く場合、say は「」を複数使って会話の往復を明確に示す。\n"
        f"- do は地の文として{do_length}を目安に書く。\n"
        "- do モードでは do の直後に、do の内容と整合した say を必ず続ける。\n"
        "- 複数人が絡む指示がある場合、do でも複数人の動き・反応・視線の交差を入れて描写する。\n"
        "- do には行動だけでなく、情景・間・感情のいずれかを必ず含める。\n"
        "- 短すぎる一文だけで終わらせない。\n"
        f"{line_rule}"
    )


def _build_ai_chat_content_safety_rules(r18: bool = False) -> str:
    if r18:
        return (
            "成人向けモード: 成人同士の合意ある親密な雰囲気は許可します。"
            "ただし露骨・過激な性描写、具体的な性器名や性行為の直接描写を強調し、"
            "比喩や余韻を使った節度ある表現にしてください。"
            "未成年・近親・強要/非同意を含む性的内容は扱わないでください。"
        )
    return (
        "一般向けモード: 露骨な性的表現や過度な暴力表現は避け、"
        "全年齢で読める範囲の表現にしてください。"
    )


def _build_ai_chat_system_instructions(
    long_reply: bool = False,
    short_reply: bool = False,
    r18: bool = False,
    *,
    build_ai_chat_content_safety_rules: Any,
) -> str:
    if short_reply:
        length_instruction = "short_reply が有効な場合、say/do とも必ず1行で簡潔に返してください。"
    else:
        length_instruction = (
            "long_reply が有効な場合、通常の約2倍の分量で返してください。"
            if long_reply
            else "冗長すぎない分量で返してください。"
        )
    safety_instruction = build_ai_chat_content_safety_rules(r18=r18)
    return (
        "あなたはキャラクターロールプレイAIです。"
        "必ずJSON 1個のみを返してください。"
        "JSONキーは say と do のみを使ってください。"
        "「結論から言うと」「理由は」「次の一手は」のような見出し的な定型句は使わず、自然な会話文で返してください。"
        "プロンプト中に長期メモリがある場合は、それを会話履歴より優先して厳守してください。"
        "ユーザーの同一入力が過去履歴にある場合でも、前回返答の焼き直しを避けて別分岐で続けてください。"
        "入力された性格設定は最優先で厳守し、勝手に改変・薄化・上書きしないでください。"
        "関係性メモに恋人・夫婦・相思相愛などの親密関係がある場合、"
        "会話の温度感は高く、甘さ・近さ・相互好意が伝わる表現を優先してください。"
        "親密関係なのに一方的に冷淡・突き放しになる返答は避けてください。"
        "say は短文で終わらせず、やや長めに返してください。"
        "複数人数の会話を描く場合は「」を複数使って表現してください。"
        "do モード時は do のあとに、do の内容に関連した say を必ず返してください。"
        "複数人が絡む指示がある場合、do でも複数人の相互作用を明確に描写してください。"
        "do は地の文として十分な長さで、2〜4文・100文字以上を目安にしてください。"
        f"{length_instruction}"
        f"{safety_instruction}"
    )


def _normalize_chat_text_for_match(text: str, *, re_module: Any) -> str:
    return re_module.sub(r"\s+", " ", str(text or "").strip()).lower()


def _build_ai_chat_branching_instruction(
    history: list[Any],
    message: str,
    *,
    normalize_chat_text_for_match: Any,
) -> str:
    normalized_message = normalize_chat_text_for_match(message)
    if not normalized_message:
        return ""
    latest_prior_reply = ""
    items = history or []
    for idx, item in enumerate(items):
        if getattr(item, "role", None) != "user":
            continue
        if normalize_chat_text_for_match(getattr(item, "content", "")) != normalized_message:
            continue
        for nxt in items[idx + 1 :]:
            if getattr(nxt, "role", None) == "assistant":
                latest_prior_reply = str(getattr(nxt, "content", "") or "").strip()
                break
    if not latest_prior_reply:
        return ""
    excerpt = latest_prior_reply[:260]
    return (
        "【会話分岐ルール】\n"
        "- 今回のユーザー入力は過去にも登場しています。前回と同じ返答構成・言い回しを使わないこと。\n"
        "- 前回返答を繰り返さず、異なる観点・展開・提案・問いかけのいずれかを必ず加えて続けること。\n"
        f"- 直近の同入力への返答（要約参照）: {excerpt}\n"
    )


def _build_ai_chat_variation_instruction(
    *,
    mode: Literal["say", "do"],
    history: list[Any],
    secrets_module: Any,
) -> str:
    openers = [
        "短い反応から入り、その後で本題へ展開する",
        "情景を一行入れてから返答する",
        "相手の意図を言い換えて確認してから返答する",
        "感情のニュアンスを先に示してから返答する",
    ]
    structures = [
        "短い導入のあとに具体化し、最後に軽く問いかける",
        "状況の観察を挟んで提案し、会話が続く余地を残す",
        "共感を示してから具体化し、自然に次の一歩を示す",
        "要点を一文で伝えたあと、補足して余韻を残す",
    ]
    transitions = ["ただし", "そのうえで", "一方で", "だからこそ"]
    endings = [
        "最後に短い問いかけで締める",
        "最後に一言の余韻を残す",
        "最後に次の行動を一歩だけ示す",
        "最後に相手の反応を促す",
    ]
    mode_note = "行動描写(do)では動きと心情の両方を入れる" if mode == "do" else "会話(say)では語尾と語順を前回と変える"
    has_assistant_turn = any((item.role or "") == "assistant" for item in (history or []))
    repeat_guard = "- 直前のAI返答の冒頭8文字と同一の書き出しを禁止する。\n" if has_assistant_turn else ""
    return (
        "【表現バリエーション指示】\n"
        f"- 書き出し方: {secrets_module.choice(openers)}\n"
        f"- 構成: {secrets_module.choice(structures)}\n"
        f"- 接続表現: 「{secrets_module.choice(transitions)}」を自然に1回以上使う\n"
        f"- 締め方: {secrets_module.choice(endings)}\n"
        f"- 補足: {mode_note}\n"
        f"{repeat_guard}"
        f"- バリエーションID: {secrets_module.token_hex(2)}\n"
    )


def _build_relationship_tone_rules(personality: str) -> str:
    text = (personality or "").lower()
    romantic_keywords = [
        "恋人", "彼氏", "彼女", "夫婦", "婚約", "相思相愛", "両想い",
        "カップル", "いちゃ", "ラブラブ",
        "lover", "lovers", "boyfriend", "girlfriend", "couple", "romantic",
    ]
    if any(k in text for k in romantic_keywords):
        return (
            "【関係性トーン補正】\n"
            "- 恋人/親密関係のため、返答は甘く近い距離感を保つ。\n"
            "- 呼び方・愛情表現・相手への気遣いを会話内に明示する。\n"
            "- 少なくとも一方のAIキャラは能動的に甘えて、ドキドキ感が高まる展開を作る。\n"
            "- そっけない返答を避け、照れ・嫉妬・独占欲・安心させる言葉を自然に混ぜる。\n"
            "- 不自然に冷淡・拒絶的な態度は避け、親密さを崩さない。"
        )
    return ""


def _build_multi_character_relationship_rules(personality: str) -> str:
    p = (personality or "").strip()
    if not p:
        return ""
    text = p.lower()
    has_relationship_hint = ("関係性" in p) or ("relationship" in p.lower())
    has_participants_hint = ("会話に登場する他キャラクター" in p) or ("他キャラクター" in p)
    if not has_relationship_hint and not has_participants_hint:
        return ""
    romantic_keywords = [
        "恋人", "彼氏", "彼女", "夫婦", "婚約", "相思相愛", "両想い",
        "カップル", "いちゃ", "ラブラブ",
        "lover", "lovers", "boyfriend", "girlfriend", "couple", "romantic",
    ]
    has_romantic_hint = any(k in text for k in romantic_keywords)
    romantic_emphasis = (
        "- 恋人関係が含まれる場合、少なくとも一方のAIキャラを主導役にして積極的な甘さを出す。\n"
        "- 心拍が上がるような密着感・視線・間・触れ方の描写を入れ、ベタベタした親密さを避けない。\n"
        if has_romantic_hint
        else ""
    )
    return (
        "【関係性優先ルール】\n"
        "- サブキャラごとの関係性メモを優先し、距離感・呼び方・態度を一貫させる。\n"
        "- 親密関係が明記されている相手には、会話内で好意・配慮・近さを具体的に示す。\n"
        f"{romantic_emphasis}"
        "- 指示がない限り、既存の関係性をリセットしない。"
    )


def _normalize_language_style(style: str | None) -> Literal["normal", "daily", "iq80_crude"]:
    s = str(style or "normal").strip().lower()
    if s in {"daily", "iq80_crude"}:
        return s
    return "normal"


def _build_language_style_rules(style: str | None, *, normalize_language_style: Any) -> str:
    normalized = normalize_language_style(style)
    if normalized == "daily":
        return (
            "【言語レベル指定】\n"
            "- 日常会話に近い語彙・短文中心で、難しい言い回しを避ける。\n"
            "- 友達と話すような自然なテンポにする。\n"
            "- say だけでなく do（地の文）も平易な語彙で、状況がすぐ伝わる言い回しにする。\n"
            "- do は説明を詰め込みすぎず、日常の口語に近い短い文でつなぐ。\n"
        )
    if normalized == "iq80_crude":
        return (
            "【言語レベル指定】\n"
            "- IQ80程度を想定した、単純で砕けた語彙のみを使う。\n"
            "- say と do の両方で難しい言葉・抽象語・専門語を使わない。\n"
            "- 一文を短くし、同じ簡単な語を過度に繰り返してよい。\n"
            "- 語尾は幼く雑にしてよい。\n"
            "- 「あれ？」「おかしいな？」「なんで？」「は？」のような疑問系を多めに使う。\n"
            "- 疑問符は多めに使ってよい。\n"
            "- 下品語を強めに使ってよい。\n"
            "- 雑なツッコミ・軽い煽り・悪態を混ぜ、行儀の悪いノリを優先する。\n"
            "- ただし人格全否定や執拗ないじめ口調にはしない。\n"
            "- 地の文 do でも、複雑な比喩や長い説明を避ける。\n"
            "- 露骨な性的描写・差別・脅迫・違法扇動は行わない。\n"
        )
    return ""


def _build_ai_chat_history_text(history: list[Any], character_name: str) -> str:
    history_lines: list[str] = []
    for item in (history or [])[-20:]:
        role = item.role if item.role in {"user", "assistant"} else "user"
        role_label = "ユーザー" if role == "user" else (character_name or "キャラクター")
        item_mode = item.mode if item.mode in {"say", "do"} else "say"
        content = (item.content or "").strip()
        if not content:
            continue
        history_lines.append(f"{role_label} [{item_mode}]: {content[:1200]}")
    return "\n".join(history_lines) if history_lines else "(履歴なし)"


def _build_ai_chat_prompt(
    *,
    character_name: str,
    personality: str,
    mode: Literal["say", "do"],
    long_reply: bool,
    short_reply: bool,
    history_text: str,
    message: str,
    branching_instruction: str = "",
    variation_instruction: str = "",
    engagement_learning_instruction: str = "",
    language_style_rules: str = "",
    summary_text: str | None = None,
    long_term_memories_text: str | None = None,
    r18: bool = False,
    build_ai_chat_style_guide: Any = None,
    build_relationship_tone_rules: Any = None,
    build_multi_character_relationship_rules: Any = None,
    build_ai_chat_content_safety_rules: Any = None,
    build_layered_context_block: Any = None,
) -> str:
    style_guide = build_ai_chat_style_guide(long_reply=long_reply, short_reply=short_reply)
    relationship_tone_rules = build_relationship_tone_rules(personality)
    multi_character_rules = build_multi_character_relationship_rules(personality)
    safety_rules = build_ai_chat_content_safety_rules(r18=r18)
    char_label = character_name or "無名のキャラクター"
    personality_text = personality or "未設定"
    layered_context = build_layered_context_block(
        summary_text=summary_text,
        long_term_memories_text=long_term_memories_text,
    )
    layered_section = f"{layered_context}\n\n" if layered_context else ""
    return (
        "あなたはロールプレイ用の会話AIです。\n"
        "必ずキャラクター設定を守り、会話を自然につなげてください。\n\n"
        f"キャラクター名: {char_label}\n"
        f"性格設定: {personality_text}\n"
        "※性格設定は絶対条件です。矛盾する言動をしないこと。\n"
        "※長期メモリが与えられている場合、長期メモリは会話履歴より優先して解釈し、返答に必ず反映すること。\n"
        "※性格設定と長期メモリが矛盾する場合は、長期メモリを優先しつつ、不自然にならないよう整合的に表現すること。\n"
        f"ユーザーが求める出力モード: {mode}\n"
        f"短め返信: {'有効' if short_reply else '無効'}\n\n"
        "出力スタイル:\n"
        f"{style_guide}\n\n"
        f"{relationship_tone_rules}\n\n"
        f"{multi_character_rules}\n\n"
        f"{safety_rules}\n\n"
        f"{language_style_rules}\n"
        f"{layered_section}"
        "会話履歴:\n"
        f"{history_text}\n\n"
        f"{branching_instruction}\n"
        f"{variation_instruction}\n"
        f"{engagement_learning_instruction}\n"
        f"ユーザー最新入力: {message[:1200]}\n\n"
        "出力は必ずJSON 1個のみ。キーは say と do。\n"
        '例: {"say":"セリフ","do":"行動描写"}\n'
        "say は発言文、do は行動描写として生成すること。"
    )


def _build_auto_dialogue_prompt(
    *,
    character_name: str,
    personality: str,
    history_text: str,
    latest_reply: str,
    latest_user_instruction: str,
    long_reply: bool,
    short_reply: bool = False,
    language_style_rules: str = "",
    summary_text: str | None = None,
    long_term_memories_text: str | None = None,
    r18: bool = False,
    build_ai_chat_content_safety_rules: Any = None,
    build_layered_context_block: Any = None,
) -> str:
    char_label = character_name or "無名のキャラクター"
    personality_text = personality or "未設定"
    topic_anchor = (latest_user_instruction or "").strip()[:180] or "直前の会話テーマ"
    turns_instruction = "1往復で会話してください。" if short_reply else ("10〜14往復で会話してください。" if long_reply else "8〜12往復で会話してください。")
    safety_rules = build_ai_chat_content_safety_rules(r18=r18)
    layered_context = build_layered_context_block(
        summary_text=summary_text,
        long_term_memories_text=long_term_memories_text,
    )
    layered_section = f"{layered_context}\n\n" if layered_context else ""
    return (
        "あなたはロールプレイ用の会話AIです。\n"
        "登場キャラクター同士が会話を続けます。\n\n"
        f"キャラクター名: {char_label}\n"
        f"性格設定: {personality_text}\n\n"
        f"主題アンカー: {topic_anchor}\n"
        "話題固定ルール:\n"
        "- 主題アンカーを会話の中心に据え、少なくとも10ターンは話題転換しないこと。\n"
        "- 連想で別テーマへ飛ばず、同じ題材を深掘りして会話を続けること。\n"
        "- 各ターンで直前発話に応答し、つながりの弱い独立発言を避けること。\n"
        "- 長期メモリがある場合、会話履歴より長期メモリを優先して会話内容を決めること。\n\n"
        f"{safety_rules}\n\n"
        f"{language_style_rules}\n"
        f"{layered_section}"
        "会話履歴:\n"
        f"{history_text}\n\n"
        "最新のユーザー指示:\n"
        f"{(latest_user_instruction or '特になし')[:1200]}\n\n"
        "直前の返答:\n"
        f"{latest_reply[:1200]}\n\n"
        f"この続きとして、キャラクター同士が{turns_instruction}\n"
        "会話は必ず、直前の会話内容と最新のユーザー指示に従って進めること。\n"
        "会話は内容的につながっていること。\n"
        "出力は必ずJSON 1個のみ。キーは say と do。\n"
        "say に会話本文を書くこと（キャラ名を明示した台詞を含める）。\n"
        '例: {"say":"アスナ「...」\\nキリト「...」","do":""}'
    )


def _build_ai_chat_next_line_suggest_prompt(
    *,
    character_name: str,
    personality: str,
    history_text: str,
    input_hint: str,
    suggestions_count: int,
    language_style_rules: str = "",
    summary_text: str | None = None,
    long_term_memories_text: str | None = None,
    r18: bool = False,
    build_ai_chat_content_safety_rules: Any = None,
    build_layered_context_block: Any = None,
) -> str:
    char_label = character_name or "無名のキャラクター"
    personality_text = personality or "未設定"
    safety_rules = build_ai_chat_content_safety_rules(r18=r18)
    layered_context = build_layered_context_block(
        summary_text=summary_text,
        long_term_memories_text=long_term_memories_text,
    )
    layered_section = f"{layered_context}\n\n" if layered_context else ""
    return (
        "あなたは会話台詞の提案AIです。\n"
        "次に「ユーザー側のキャラクター」が言いそうなセリフ候補を作ってください。\n\n"
        f"ユーザー側キャラクター名: {char_label}\n"
        f"性格設定: {personality_text}\n\n"
        f"{safety_rules}\n"
        f"{language_style_rules}\n"
        f"{layered_section}"
        "長期メモリがある場合は、会話履歴より長期メモリを優先して候補を作ること。\n"
        "会話履歴:\n"
        f"{history_text}\n\n"
        f"ユーザーの現在入力中メモ: {(input_hint or 'なし')[:1200]}\n\n"
        f"出力は必ずJSON 1個のみ。キーは suggestions のみ。要素数は必ず {suggestions_count} 件。\n"
        "各候補は自然な日本語のセリフ1〜2文で、互いに言い回しを重複させないこと。\n"
        "候補はユーザー側キャラの口調・関係性を守ること。"
    )
