# backend/app/ai_novel.py

import os
import json
import asyncio
from textwrap import dedent
from typing import Tuple

from fastapi import HTTPException
from openai import OpenAI
from dotenv import load_dotenv

from pydantic import BaseModel

# .env 読み込み（他でやっていても二重読み込みは特に害なし）
load_dotenv()

# ===== OpenAI クライアント初期化 =====
try:
    client = OpenAI()
except Exception as e:
    # 起動時に OpenAI クライアント初期化でコケてもアプリ自体は起動できるようにしておく
    print("[WARN] OpenAI client init failed:", repr(e))
    client = None

# デフォルトモデル（env に無ければ gpt-4.1-mini を使う）
OPENAI_MODEL_TEXT = os.getenv("OPENAI_MODEL_TEXT", "gpt-4.1-mini")


def _read_secret_from_env_or_file(env_name: str, file_env_name: str) -> str | None:
    v = os.getenv(env_name)
    if v:
        v = v.strip()
        return v if v else None
    file_path = os.getenv(file_env_name)
    if not file_path:
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None


OPENROUTER_API_KEY = _read_secret_from_env_or_file(
    "OPENROUTER_API_KEY",
    "OPENROUTER_API_KEY_FILE",
)

try:
    openrouter_client = (
        OpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
        if OPENROUTER_API_KEY
        else None
    )
except Exception as e:
    print("[WARN] OpenRouter client init failed:", repr(e))
    openrouter_client = None


DEEPSEEK_API_KEY = _read_secret_from_env_or_file(
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_API_KEY_FILE",
)

try:
    deepseek_client = (
        OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        if DEEPSEEK_API_KEY
        else None
    )
except Exception as e:
    print("[WARN] DeepSeek client init failed:", repr(e))
    deepseek_client = None




def provider_from_model(model: str | None) -> str:
    if not model:
        return "openai"
    if model.startswith("deepseek:"):
        return "deepseek"
    return "openrouter" if "/" in model else "openai"


def provider_from_request(req: "AINovelRequest | None") -> str:
    if req is None:
        return "openai"
    provider = (getattr(req, "provider", None) or "").strip().lower()
    if provider:
        return provider
    return provider_from_model(getattr(req, "model", None))


# ===== Pydantic モデル =====

class AINovelRequest(BaseModel):
    """
    /api/ai/novels/generate 用の共通リクエスト。
    通常の「お題から生成」用では title_hint / genre / characters / tone / length を使う。
    「続き生成」のようなケースでは prompt を直接渡して使うこともできる。
    """
    title_hint: str | None = None
    genre: str | None = None
    characters: str | None = None
    tone: str | None = None
    length: str | None = "medium"  # "short" | "medium" | "long" | "xlong" | "xxlong"
    prompt: str | None = None
    model: str | None = None
    provider: str | None = None
    r18: bool = False
    retry_mode: bool = False
    retry_max: int | None = None


class AINovelResponse(BaseModel):
    generated_title: str
    body: str
    used_tokens: int | None = None  # OpenAIの使用トークン数
    model: str | None = None        # 実際に使ったモデル名
    prompt_used: str | None = None
    guest_remaining: int | None = None
    user_remaining: int | None = None


# ===== プロンプト組み立て =====

def build_ai_prompt(req: AINovelRequest) -> str:
    """
    ユーザー入力から、モデルに渡す日本語プロンプト文字列を組み立てる。
    """
    length_map = {
        "short": "およそ 800〜1200 文字の短編",
        "medium": "およそ 2000〜3000 文字の中編",
        "long": "およそ 4000〜6000 文字のやや長めの中編",
        "xlong": "およそ 6000〜8000 文字の長編",
        "xxlong": "およそ 8000〜10000 文字の長編",
    }
    length_text = length_map.get(req.length or "medium", length_map["medium"])

    genre = req.genre or "ジャンルは特に指定なし"
    tone = req.tone or "雰囲気は特に指定なし"
    characters = req.characters or "登場人物や設定の指定は特にない"

    title_hint = req.title_hint or "タイトルは内容に合うものをあなたが考えてほしい"

    constraint_text = (
        "- 成人向けの内容を含めて構いません。性的描写も許可します。\n"
        "- 読みやすい段落構成にしてください。\n"
        "- 一人称 / 三人称は、物語に合うほうをあなたが選んでください。"
        if req.r18
        else
        "- 一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。\n"
        "- 読みやすい段落構成にしてください。\n"
        "- 一人称 / 三人称は、物語に合うほうをあなたが選んでください。"
    )

    prompt = dedent(
        f"""
        あなたは日本語のライトノベル風の小説家です。
        以下の条件に合う短編小説を書いてください。

        # 出力フォーマット
        - 1行目に小説のタイトルだけを書く
        - 2行目は空行
        - 3行目以降に本文を書く

        # 制約
        {constraint_text}

        # 要望
        - 作品の長さ: {length_text}
        - ジャンル: {genre}
        - 雰囲気: {tone}
        - 登場人物・設定: {characters}
        - タイトルに関する要望: {title_hint}
        """
    ).strip()

    return prompt


# ===== テキストからタイトルと本文を切り分ける（今は使っていないが残しておく） =====

def split_title_and_body(text: str) -> Tuple[str, str]:
    """
    1行目 = タイトル, 2行目 = 空行想定で、本文と分離する。
    モデルの出力が多少ズレてもそこそこ頑丈に動くようにしている。
    """
    if not text:
        return "タイトル未設定", ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    # 先頭の空行を削る
    while lines and not lines[0].strip():
        lines.pop(0)

    if not lines:
        return "タイトル未設定", ""

    title = lines[0].strip()
    body_lines = lines[1:] if len(lines) > 1 else []
    body = "\n".join(body_lines).lstrip("\n")

    if not title:
        title = "タイトル未設定"

    return title, body


def _strip_code_fence(s: str) -> str:
    s = (s or "").strip()
    if not s.startswith("```"):
        return s
    lines = s.splitlines()
    if lines and lines[0].lstrip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_title_and_body(raw: str) -> Tuple[str, str]:
    import json
    import re

    if not raw:
        return "タイトル未設定", ""

    text = raw.strip()

    text = _strip_code_fence(text)

    def _from_dict(data: dict) -> Tuple[str, str]:
        title = (
            data.get("title")
            or data.get("generated_title")
            or data.get("generatedTitle")
            or ""
        )
        body = (
            data.get("body")
            or data.get("text")
            or data.get("content")
            or data.get("story")
            or ""
        )
        title = str(title or "").strip()
        body = str(body or "")
        if not title:
            title = "タイトル未設定"
        return title, body

    def _extract_dict(data) -> dict | None:
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        return None

    def _try_parse_dict(s: str) -> dict | None:
        s = _strip_code_fence((s or "").strip())
        if not s:
            return None

        try:
            parsed = json.loads(s)
            d = _extract_dict(parsed)
            if d is not None:
                return d
            # JSON の中身がさらに JSON 文字列として二重エンコードされているケース
            if isinstance(parsed, str):
                inner = _strip_code_fence(parsed.strip())
                try:
                    parsed2 = json.loads(inner)
                    d2 = _extract_dict(parsed2)
                    if d2 is not None:
                        return d2
                except Exception:
                    pass
        except Exception:
            pass

        return None

    # まずは素直に JSON として解釈
    d0 = _try_parse_dict(text)
    if d0 is not None:
        return _from_dict(d0)

    # よくある「\"title\"」のようなバックスラッシュ付き JSON を救済（モデルが JSON を文字列化して返す等）
    if '\\"' in text:
        text_unescaped_quotes = text.replace('\\"', '"')
        d1 = _try_parse_dict(text_unescaped_quotes)
        if d1 is not None:
            return _from_dict(d1)

        # 余計な前後テキスト付きの場合に備えて、 unescape 後の文字列を使って JSON 断片抽出を試す
        text = text_unescaped_quotes

    # 前後に余計な説明が付くケースに備えて JSON オブジェクト部分だけを抽出
    try:
        decoder = json.JSONDecoder()
        start = 0
        while True:
            brace_index = text.find("{", start)
            if brace_index < 0:
                break
            try:
                parsed, _end = decoder.raw_decode(text[brace_index:])
                if isinstance(parsed, dict):
                    return _from_dict(parsed)
            except Exception:
                pass
            start = brace_index + 1
    except Exception:
        pass

    # 最後の手段: { ... } っぽい範囲を雑に切り出して試す（本文中の { } で壊れる可能性があるので最終手段）
    try:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            d2 = _try_parse_dict(m.group(0))
            if d2 is not None:
                return _from_dict(d2)
    except Exception:
        pass

    return split_title_and_body(raw)


def _parse_json_payload(raw: str) -> dict:
    import json
    import re

    if not raw:
        raise ValueError("empty response")

    text = _strip_code_fence(raw.strip())

    def _extract_dict(value) -> dict | None:
        if isinstance(value, dict):
            return value
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value[0]
        return None

    def _try_parse_dict(s: str) -> dict | None:
        s = _strip_code_fence((s or "").strip())
        if not s:
            return None
        try:
            parsed = json.loads(s)
            d = _extract_dict(parsed)
            if d is not None:
                return d
            if isinstance(parsed, str):
                inner = _strip_code_fence(parsed.strip())
                try:
                    parsed2 = json.loads(inner)
                    d2 = _extract_dict(parsed2)
                    if d2 is not None:
                        return d2
                except Exception:
                    pass
        except Exception:
            pass
        return None

    d0 = _try_parse_dict(text)
    if d0 is not None:
        return d0

    if '\\"' in text:
        text_unescaped = text.replace('\\"', '"')
        d1 = _try_parse_dict(text_unescaped)
        if d1 is not None:
            return d1
        text = text_unescaped

    try:
        decoder = json.JSONDecoder()
        start = 0
        while True:
            brace_index = text.find("{", start)
            if brace_index < 0:
                break
            try:
                parsed, _end = decoder.raw_decode(text[brace_index:])
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
            start = brace_index + 1
    except Exception:
        pass

    try:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            d2 = _try_parse_dict(m.group(0))
            if d2 is not None:
                return d2
    except Exception:
        pass

    raise ValueError("failed to parse json")

def _log_ai_raw_response(raw: str, label: str) -> None:
    if os.getenv("AI_LOG_RAW_RESPONSE", "").strip() not in {"1", "true", "yes"}:
        return
    try:
        max_len = int(os.getenv("AI_LOG_RAW_RESPONSE_MAX", "4000"))
    except Exception:
        max_len = 4000
    text = raw or ""
    clipped = text if len(text) <= max_len else text[:max_len] + " ...[truncated]"
    print(f"[DEBUG] {label} raw response (len={len(text)}):\n{clipped}")


async def call_ai_json(
    prompt: str,
    *,
    model: str | None = None,
    provider: str | None = None,
    system_instructions: str | None = None,
) -> tuple[dict, int | None, str | None]:
    if not prompt:
        raise HTTPException(status_code=400, detail="プロンプトが空です。")

    provider = (provider or "").strip().lower() or provider_from_model(model)
    system_instructions = system_instructions or "JSON 1個のみを返してください。"

    if provider == "deepseek":
        if deepseek_client is None:
            raise HTTPException(status_code=500, detail="DeepSeek の API キーが設定されていません。")
        effective_model = (model or os.getenv("DEEPSEEK_MODEL_TEXT") or "").strip()
        if effective_model.startswith("deepseek:"):
            effective_model = effective_model.split(":", 1)[1].strip()
        if not effective_model:
            raise HTTPException(status_code=400, detail="モデルが指定されていません。")
        try:
            resp = await asyncio.to_thread(
                deepseek_client.chat.completions.create,
                model=effective_model,
                messages=[
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2048,
            )
        except Exception as e:
            print("[ERROR] DeepSeek API 呼び出し失敗:", repr(e))
            raise HTTPException(status_code=502, detail=f"AI 翻訳 API 呼び出しに失敗しました: {e!r}")

        raw = ""
        try:
            raw = resp.choices[0].message.content or ""
        except Exception:
            raw = ""
    elif provider == "openrouter":
        if openrouter_client is None:
            raise HTTPException(status_code=500, detail="OpenRouter の API キーが設定されていません。")
        effective_model = (model or os.getenv("OPENROUTER_MODEL_TEXT") or "").strip()
        if not effective_model:
            raise HTTPException(status_code=400, detail="モデルが指定されていません。")
        try:
            resp = await asyncio.to_thread(
                openrouter_client.chat.completions.create,
                model=effective_model,
                messages=[
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2048,
            )
        except Exception as e:
            print("[ERROR] OpenRouter API 呼び出し失敗:", repr(e))
            raise HTTPException(status_code=502, detail=f"AI 翻訳 API 呼び出しに失敗しました: {e!r}")

        raw = ""
        try:
            raw = resp.choices[0].message.content or ""
        except Exception:
            raw = ""
    else:
        if client is None:
            raise HTTPException(status_code=500, detail="OpenAI クライアントの初期化に失敗しています。")
        effective_model = (model or os.getenv("OPENAI_MODEL_TEXT") or OPENAI_MODEL_TEXT).strip()
        try:
            resp = await asyncio.to_thread(
                client.responses.create,
                model=effective_model,
                instructions=system_instructions,
                input=prompt,
                max_output_tokens=2048,
            )
        except Exception as e:
            print("[ERROR] OpenAI Responses API 呼び出し失敗:", repr(e))
            raise HTTPException(status_code=502, detail=f"AI 翻訳 API 呼び出しに失敗しました: {e!r}")

        raw = ""
        try:
            raw = resp.output[0].content[0].text
        except Exception:
            raw = getattr(resp, "output_text", "") or ""

    if not raw:
        raise HTTPException(status_code=500, detail="AI からの応答が空でした。")

    try:
        data = _parse_json_payload(raw)
    except Exception as e:
        _log_ai_raw_response(raw, "call_ai_json")
        print("[ERROR] AI JSON parse failed:", repr(e))
        raise HTTPException(status_code=500, detail="AI 応答の JSON 解析に失敗しました。")

    tokens: int | None = None
    usage = getattr(resp, "usage", None)
    if usage is not None:
        tokens = getattr(usage, "total_tokens", None)

    return data, tokens, effective_model

# ===== 実際に OpenAI API を叩く関数 =====

async def call_openai_novel_api(
    req: AINovelRequest | str,
    model: str | None = None,
    strict_json: bool = False,
) -> AINovelResponse:
    """
    OpenAI Responses API を用いて小説を生成する。

    - 通常の小説生成:
        req: AINovelRequest
        -> req.prompt があればそれをそのまま使い、無ければ build_ai_prompt(req) で組み立てる。

    - 「エピソードの続き生成」など:
        req: str  （すでに組み立て済みのプロンプト文字列）
        -> そのまま input に渡す。
    """
    if client is None:
        raise HTTPException(status_code=500, detail="OpenAI クライアントの初期化に失敗しています。")

    # ---- モデル決定 ----
    if isinstance(req, AINovelRequest):
        effective_model = (
            model
            or (req.model or os.getenv("OPENAI_MODEL_TEXT") or OPENAI_MODEL_TEXT)
        )
        effective_model = effective_model.strip()
        # プロンプト決定: 直接指定があればそれを優先
        if req.prompt:
            prompt = req.prompt
        else:
            prompt = build_ai_prompt(req)
    else:
        # 文字列としてプロンプトを直接渡されたパターン
        effective_model = (model or os.getenv("OPENAI_MODEL_TEXT") or OPENAI_MODEL_TEXT).strip()
        prompt = str(req)

    # ---- OpenAI 呼び出し ----
    try:
        resp = await asyncio.to_thread(
            client.responses.create,
            model=effective_model,
            instructions=(
                "あなたは日本語ライトノベル作家です。"
                "与えられた条件に基づいて短編小説を生成してください。"
                "出力は必ず JSON 1個のみ（前後に説明文を付けない / ``` で囲まない）。"
                '例: {\\"title\\": \\"タイトル\\", \\"body\\": \\"本文\\"}'
            ),
            input=prompt,
            max_output_tokens=2048,
        )
    except Exception as e:
        print("[ERROR] OpenAI Responses API 呼び出し失敗:", repr(e))
        raise HTTPException(status_code=502, detail=f"AI 小説生成 API 呼び出しに失敗しました: {e!r}")

    # ---- テキスト部分を抽出 ----
    raw = ""
    try:
        # 新しい Responses API 形式
        raw = resp.output[0].content[0].text
    except Exception:
        # 念のため互換用のフィールドも試す
        raw = getattr(resp, "output_text", "") or ""

    if not raw:
        raise HTTPException(status_code=500, detail="AI からの応答が空でした。")

    if strict_json:
        try:
            _parse_json_payload(raw)
        except Exception as e:
            _log_ai_raw_response(raw, "openai_novel")
            print("[ERROR] AI JSON parse failed:", repr(e))
            raise HTTPException(status_code=500, detail="AI 応答の JSON 解析に失敗しました。")

    # ---- JSON パースして title/body を取り出す ----
    title, body = _parse_title_and_body(raw)

    # ---- トークン使用量 ----
    tokens: int | None = None
    usage = getattr(resp, "usage", None)
    if usage is not None:
        tokens = getattr(usage, "total_tokens", None)

    return AINovelResponse(
        generated_title=title,
        body=body,
        used_tokens=tokens,
        model=effective_model,
        prompt_used=prompt,
    )


async def call_openai_summary_candidates(text: str, model: str | None = None) -> tuple[list[str], int | None, str]:
    if client is None:
        raise HTTPException(status_code=500, detail="OpenAI クライアントの初期化に失敗しています。")
    source_text = (text or "").strip()
    if not source_text:
        raise HTTPException(status_code=400, detail="本文が空です。")

    effective_model = (model or os.getenv("OPENAI_MODEL_TEXT") or OPENAI_MODEL_TEXT).strip()
    prompt = dedent(
        f"""
        以下の本文から、小説の説明文（あらすじ）を3候補作成してください。
        それぞれ 60〜180 文字程度、内容が重複しないようにしてください。
        出力は必ず JSON のみ。形式: {{"candidates": ["候補1", "候補2", "候補3"]}}

        本文:
        {source_text}
        """
    ).strip()

    try:
        resp = await asyncio.to_thread(
            client.responses.create,
            model=effective_model,
            instructions="あなたは日本語の編集者です。必ず JSON のみを返してください。",
            input=prompt,
            max_output_tokens=512,
        )
    except Exception as e:
        print("[ERROR] OpenAI Responses API 呼び出し失敗:", repr(e))
        raise HTTPException(status_code=502, detail=f"AI 要約 API 呼び出しに失敗しました: {e!r}")

    raw = ""
    try:
        raw = resp.output[0].content[0].text
    except Exception:
        raw = getattr(resp, "output_text", "") or ""

    if not raw:
        raise HTTPException(status_code=500, detail="AI からの応答が空でした。")

    try:
        data = _parse_json_payload(raw)
    except Exception as e:
        _log_ai_raw_response(raw, "summary_candidates")
        print("[ERROR] AI JSON parse failed:", repr(e))
        raise HTTPException(status_code=500, detail="AI 応答の JSON 解析に失敗しました。")

    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not isinstance(candidates, list):
        raise HTTPException(status_code=500, detail="AI 応答の形式が不正です。")

    normalized = []
    seen = set()
    for item in candidates:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)

    if not normalized:
        raise HTTPException(status_code=500, detail="AI から候補が取得できませんでした。")

    tokens: int | None = None
    usage = getattr(resp, "usage", None)
    if usage is not None:
        tokens = getattr(usage, "total_tokens", None)

    return normalized, tokens, effective_model


async def call_openai_tag_candidates(text: str, model: str | None = None) -> tuple[list[str], int | None, str]:
    if client is None:
        raise HTTPException(status_code=500, detail="OpenAI クライアントの初期化に失敗しています。")
    source_text = (text or "").strip()
    if not source_text:
        raise HTTPException(status_code=400, detail="本文が空です。")

    effective_model = (model or os.getenv("OPENAI_MODEL_TEXT") or OPENAI_MODEL_TEXT).strip()
    prompt = dedent(
        f"""
        以下の本文から、内容を表すタグ候補を8〜12個作成してください。
        一般的な単語で、短く（10文字以内）し、ハッシュ記号は不要です。
        出力は必ず JSON のみ。形式: {{"candidates": ["タグ1", "タグ2"]}}

        本文:
        {source_text}
        """
    ).strip()

    try:
        resp = await asyncio.to_thread(
            client.responses.create,
            model=effective_model,
            instructions="あなたは日本語の編集者です。必ず JSON のみを返してください。",
            input=prompt,
            max_output_tokens=256,
        )
    except Exception as e:
        print("[ERROR] OpenAI Responses API 呼び出し失敗:", repr(e))
        raise HTTPException(status_code=502, detail=f"AI タグ生成 API 呼び出しに失敗しました: {e!r}")

    raw = ""
    try:
        raw = resp.output[0].content[0].text
    except Exception:
        raw = getattr(resp, "output_text", "") or ""

    if not raw:
        raise HTTPException(status_code=500, detail="AI からの応答が空でした。")

    try:
        data = _parse_json_payload(raw)
    except Exception as e:
        _log_ai_raw_response(raw, "tag_candidates")
        print("[ERROR] AI JSON parse failed:", repr(e))
        raise HTTPException(status_code=500, detail="AI 応答の JSON 解析に失敗しました。")

    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not isinstance(candidates, list):
        raise HTTPException(status_code=500, detail="AI 応答の形式が不正です。")

    normalized = []
    seen = set()
    for item in candidates:
        if not isinstance(item, str):
            continue
        cleaned = item.strip().lstrip("#")
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)

    if not normalized:
        raise HTTPException(status_code=500, detail="AI から候補が取得できませんでした。")

    tokens: int | None = None
    usage = getattr(resp, "usage", None)
    if usage is not None:
        tokens = getattr(usage, "total_tokens", None)

    return normalized, tokens, effective_model


async def call_openai_title_candidate(text: str, model: str | None = None) -> tuple[str, int | None, str]:
    if client is None:
        raise HTTPException(status_code=500, detail="OpenAI クライアントの初期化に失敗しています。")
    source_text = (text or "").strip()
    if not source_text:
        raise HTTPException(status_code=400, detail="本文が空です。")

    effective_model = (model or os.getenv("OPENAI_MODEL_TEXT") or OPENAI_MODEL_TEXT).strip()
    prompt = dedent(
        f"""
        以下の本文に合う小説タイトルを1つ作成してください。
        条件:
        - 日本語
        - 40文字以内
        - 記号の多用は避ける
        出力は必ず JSON のみ。形式: {{"title": "タイトル"}}

        本文:
        {source_text}
        """
    ).strip()

    try:
        resp = await asyncio.to_thread(
            client.responses.create,
            model=effective_model,
            instructions="あなたは日本語の編集者です。必ず JSON のみを返してください。",
            input=prompt,
            max_output_tokens=128,
        )
    except Exception as e:
        print("[ERROR] OpenAI Responses API 呼び出し失敗:", repr(e))
        raise HTTPException(status_code=502, detail=f"AI タイトル生成 API 呼び出しに失敗しました: {e!r}")

    raw = ""
    try:
        raw = resp.output[0].content[0].text
    except Exception:
        raw = getattr(resp, "output_text", "") or ""

    if not raw:
        raise HTTPException(status_code=500, detail="AI からの応答が空でした。")

    try:
        data = _parse_json_payload(raw)
    except Exception as e:
        _log_ai_raw_response(raw, "title_candidate")
        print("[ERROR] AI JSON parse failed:", repr(e))
        raise HTTPException(status_code=500, detail="AI 応答の JSON 解析に失敗しました。")

    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str):
        raise HTTPException(status_code=500, detail="AI 応答の形式が不正です。")
    normalized = title.strip().strip('"').strip("'")
    if not normalized:
        raise HTTPException(status_code=500, detail="AI からタイトルが取得できませんでした。")

    tokens: int | None = None
    usage = getattr(resp, "usage", None)
    if usage is not None:
        tokens = getattr(usage, "total_tokens", None)

    return normalized[:40], tokens, effective_model


async def call_openrouter_novel_api(
    req: AINovelRequest | str,
    model: str | None = None,
    strict_json: bool = False,
) -> AINovelResponse:
    if openrouter_client is None:
        raise HTTPException(status_code=500, detail="OpenRouter の API キーが設定されていません。")

    if isinstance(req, AINovelRequest):
        effective_model = (model or req.model or os.getenv("OPENROUTER_MODEL_TEXT") or "").strip()
        prompt = req.prompt or build_ai_prompt(req)
    else:
        effective_model = (model or os.getenv("OPENROUTER_MODEL_TEXT") or "").strip()
        prompt = str(req)

    if not effective_model:
        raise HTTPException(status_code=400, detail="モデルが指定されていません。")

    try:
        resp = await asyncio.to_thread(
            openrouter_client.chat.completions.create,
            model=effective_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたは日本語ライトノベル作家です。"
                        "与えられた条件に基づいて短編小説を生成してください。"
                        "出力は必ず JSON 1個のみ（前後に説明文を付けない / ``` で囲まない）。"
                        '例: {"title": "タイトル", "body": "本文"}'
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=2048,
        )
    except Exception as e:
        print("[ERROR] OpenRouter API 呼び出し失敗:", repr(e))
        raise HTTPException(status_code=502, detail=f"AI 小説生成 API 呼び出しに失敗しました: {e!r}")

    raw = ""
    try:
        raw = resp.choices[0].message.content or ""
    except Exception:
        raw = ""

    if not raw:
        raise HTTPException(status_code=500, detail="AI からの応答が空でした。")

    if strict_json:
        try:
            _parse_json_payload(raw)
        except Exception as e:
            _log_ai_raw_response(raw, "openrouter_novel")
            print("[ERROR] AI JSON parse failed:", repr(e))
            raise HTTPException(status_code=500, detail="AI 応答の JSON 解析に失敗しました。")

    title, body = _parse_title_and_body(raw)

    tokens: int | None = None
    usage = getattr(resp, "usage", None)
    if usage is not None:
        tokens = getattr(usage, "total_tokens", None)

    return AINovelResponse(
        generated_title=title,
        body=body,
        used_tokens=tokens,
        model=effective_model,
        prompt_used=prompt,
    )


async def call_deepseek_novel_api(
    req: AINovelRequest | str,
    model: str | None = None,
    strict_json: bool = False,
) -> AINovelResponse:
    if deepseek_client is None:
        raise HTTPException(status_code=500, detail="DeepSeek の API キーが設定されていません。")

    if isinstance(req, AINovelRequest):
        effective_model = (model or req.model or os.getenv("DEEPSEEK_MODEL_TEXT") or "").strip()
        prompt = req.prompt or build_ai_prompt(req)
    else:
        effective_model = (model or os.getenv("DEEPSEEK_MODEL_TEXT") or "").strip()
        prompt = str(req)

    if effective_model.startswith("deepseek:"):
        effective_model = effective_model.split(":", 1)[1].strip()

    if not effective_model:
        raise HTTPException(status_code=400, detail="モデルが指定されていません。")

    try:
        resp = await asyncio.to_thread(
            deepseek_client.chat.completions.create,
            model=effective_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたは日本語ライトノベル作家です。"
                        "与えられた条件に基づいて短編小説を生成してください。"
                        "出力は必ず JSON 1個のみ（前後に説明文を付けない / ``` で囲まない）。"
                        '例: {"title": "タイトル", "body": "本文"}'
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=2048,
        )
    except Exception as e:
        print("[ERROR] DeepSeek API 呼び出し失敗:", repr(e))
        raise HTTPException(status_code=502, detail=f"AI 小説生成 API 呼び出しに失敗しました: {e!r}")

    raw = ""
    try:
        raw = resp.choices[0].message.content or ""
    except Exception:
        raw = ""

    if not raw:
        raise HTTPException(status_code=500, detail="AI からの応答が空でした。")

    if strict_json:
        try:
            _parse_json_payload(raw)
        except Exception as e:
            _log_ai_raw_response(raw, "deepseek_novel")
            print("[ERROR] AI JSON parse failed:", repr(e))
            raise HTTPException(status_code=500, detail="AI 応答の JSON 解析に失敗しました。")

    title, body = _parse_title_and_body(raw)

    tokens: int | None = None
    usage = getattr(resp, "usage", None)
    if usage is not None:
        tokens = getattr(usage, "total_tokens", None)

    return AINovelResponse(
        generated_title=title,
        body=body,
        used_tokens=tokens,
        model=effective_model,
        prompt_used=prompt,
    )
