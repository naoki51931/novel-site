# backend/app/ai_novel.py

import os
import re
import json
import asyncio
import time
from textwrap import dedent
from typing import Tuple

from fastapi import HTTPException
from openai import OpenAI
from dotenv import load_dotenv

from pydantic import BaseModel

import httpx

from .local_llm_models import get_local_model, is_local_model, public_local_models

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


def _read_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)) or default)
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


OPENROUTER_NOVEL_MAX_TOKENS = _read_int_env(
    "OPENROUTER_NOVEL_MAX_TOKENS",
    2048,
    512,
    4096,
)


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
    if is_local_model(model):
        return "local"
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


CLAUDE_MODEL_WHITELIST: set[str] = {
    "anthropic/claude-3-haiku",
    "anthropic/claude-3.5-haiku",
}


def is_openrouter_model_blocked_for_pricing(model: str | None) -> bool:
    normalized = str(model or "").strip().lower()
    if not normalized:
        return False
    if "/" not in normalized:
        return False
    if "claude" not in normalized:
        return False
    # Claude は許可IDのみ通す（ホワイトリスト方式）。
    return normalized not in CLAUDE_MODEL_WHITELIST


def assert_openrouter_model_allowed_for_pricing(model: str | None) -> None:
    if not is_openrouter_model_blocked_for_pricing(model):
        return
    raise HTTPException(
        status_code=400,
        detail=(
            "このClaudeモデルは利用できません。"
            f"許可モデル: {', '.join(sorted(CLAUDE_MODEL_WHITELIST))}"
        ),
    )


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
    title: str | None = None
    rating: str | None = None
    setting: str | None = None
    style: str | None = None
    previous_text: str | None = None
    instruction: str | None = None
    max_new_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None
    repetition_penalty: float | None = None
    length: str | None = "medium"  # "short" | "medium" | "long" | "xlong" | "xxlong"
    prompt: str | None = None
    model: str | None = None
    provider: str | None = None
    r18: bool = False
    retry_mode: bool = False
    retry_max: int | None = None
    chunked_generation_enabled: bool = False
    chunked_generation_count: int | None = None
    chunked_generation_plans: list[dict] | None = None
    client_job_kind: str | None = None


class AINovelResponse(BaseModel):
    generated_title: str
    body: str
    used_tokens: int | None = None  # OpenAIの使用トークン数
    model: str | None = None        # 実際に使ったモデル名
    prompt_used: str | None = None
    guest_remaining: int | None = None
    user_remaining: int | None = None
    retry_attempts: int | None = None
    retry_max: int | None = None


class AINovelJobCreateResponse(BaseModel):
    job_id: int
    status: str


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


def list_ai_novel_models() -> dict:
    return {
        "default_model": os.getenv("AI_NOVEL_DEFAULT_MODEL", "local-qwen3-8b-nsfw-jp"),
        "local_models": public_local_models(),
    }


def _normalize_rating(req: AINovelRequest) -> str:
    rating = str(getattr(req, "rating", None) or "").strip().lower()
    if not rating:
        rating = "r18" if bool(getattr(req, "r18", False)) else "general"
    aliases = {"all": "general", "adult": "r18", "r-18": "r18", "r-15": "r15"}
    rating = aliases.get(rating, rating)
    if rating not in {"general", "r15", "r18"}:
        raise HTTPException(status_code=400, detail="rating は general / r15 / r18 のいずれかを指定してください。")
    return rating


_MINOR_PATTERNS = [
    r"未成年",
    r"小学生",
    r"中学生",
    r"高校生",
    r"女子高生",
    r"男子高生",
    r"児童",
    r"幼い",
    r"幼女",
    r"少年",
    r"少女",
    r"(?:^|[^\d])(?:[0-9]|1[0-7])\s*歳",
    r"年齢\s*[:：]?\s*(?:[0-9]|1[0-7])(?:\D|$)",
]


def _assert_r18_adult_characters(req: AINovelRequest) -> None:
    if _normalize_rating(req) != "r18":
        return
    text = "\n".join(
        [
            str(getattr(req, "characters", "") or ""),
            str(getattr(req, "setting", "") or ""),
            str(getattr(req, "prompt", "") or ""),
            str(getattr(req, "instruction", "") or ""),
        ]
    )
    for pattern in _MINOR_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            raise HTTPException(
                status_code=400,
                detail="R18生成では成人キャラクターのみ指定できます。未成年または年齢が成人未満に見える設定を修正してください。",
            )
    adult_markers = ("成人", "大人", "20歳", "21歳", "22歳", "23歳", "24歳", "25歳", "30歳", "社会人")
    if text.strip() and not any(marker in text for marker in adult_markers):
        raise HTTPException(
            status_code=400,
            detail="R18生成では登場人物が成人であることを明記してください。",
        )


def _target_chars_from_length(length: str | None) -> int | None:
    raw = str(length or "").strip().lower()
    if not raw:
        return None
    if raw.isdigit():
        try:
            return max(200, min(120000, int(raw)))
        except Exception:
            return None
    return {
        "short": 1000,
        "medium": 2500,
        "long": 5000,
        "xlong": 7000,
        "xxlong": 9000,
    }.get(raw)


def _local_max_tokens_for_target_chars(target_chars: int | None, default_tokens: int) -> int:
    if not target_chars:
        return default_tokens
    # Japanese prose is often near one token per character on local tokenizers.
    # Add headroom so a 2000-char block is not cut short by the sampler limit.
    estimated = int(target_chars * 1.25) + 256
    return max(default_tokens, min(4096, estimated))


def _local_length_instruction(length: str | None) -> str:
    target_chars = _target_chars_from_length(length)
    if target_chars:
        lower = max(200, int(target_chars * 0.9))
        upper = int(target_chars * 1.1)
        return f"- 出力本文は約{target_chars}文字、可能な限り{lower}〜{upper}文字に収める"
    return "- 指定された長さに合わせて本文量を調整する"


def _merge_generation_config(req: AINovelRequest) -> dict:
    model_def = get_local_model(req.model)
    defaults = model_def.generation
    target_chars = _target_chars_from_length(getattr(req, "length", None))
    try:
        max_new_tokens = int(
            req.max_new_tokens
            if req.max_new_tokens is not None
            else _local_max_tokens_for_target_chars(target_chars, defaults.max_tokens)
        )
    except Exception:
        max_new_tokens = _local_max_tokens_for_target_chars(target_chars, defaults.max_tokens)
    max_new_tokens = max(64, min(4096, max_new_tokens))

    def _float_value(value, default, minimum, maximum):
        try:
            parsed = float(value if value is not None else default)
        except Exception:
            parsed = default
        return max(minimum, min(maximum, parsed))

    def _int_value(value, default, minimum, maximum):
        try:
            parsed = int(value if value is not None else default)
        except Exception:
            parsed = default
        return max(minimum, min(maximum, parsed))

    return {
        "max_tokens": max_new_tokens,
        "temperature": _float_value(req.temperature, defaults.temperature, 0.0, 2.0),
        "top_p": _float_value(req.top_p, defaults.top_p, 0.0, 1.0),
        "top_k": _int_value(req.top_k, defaults.top_k, 0, 200),
        "repeat_penalty": _float_value(req.repetition_penalty, defaults.repeat_penalty, 0.8, 2.0),
    }


def _build_local_novel_messages(req: AINovelRequest) -> tuple[list[dict], dict]:
    model_def = get_local_model(req.model)
    rating = _normalize_rating(req)
    _assert_r18_adult_characters(req)

    genre = req.genre or "指定なし"
    style = req.style or req.tone or "novel"
    characters = req.characters or "指定なし"
    setting = req.setting or "指定なし"
    title = req.title or req.title_hint or "指定なし"
    instruction = req.instruction or req.prompt or req.title_hint or "この条件で日本語小説を書いてください。"
    rating_rule = {
        "general": "- 一般向けとして露骨な性的描写を避ける",
        "r15": "- R15相当として過度に露骨な性的描写は避ける",
        "r18": "- 成人キャラクターのみを扱い、未成年または年齢不明の性的描写を含めない",
    }[rating]

    system_prompt = dedent(
        f"""
        あなたは日本語の小説執筆AIです。

        ジャンル:
        {genre}

        レーティング:
        {rating}

        文体:
        {style}

        登場人物:
        {characters}

        設定:
        {setting}

        タイトル:
        {title}

        制約:
        - 日本語で書く
        - 指定された人物設定を維持する
        - 既存本文との連続性を維持する
        - 本文だけを生成する
        {_local_length_instruction(req.length)}
        {rating_rule}
        """
    ).strip()

    previous_text = req.previous_text or ""
    user_prompt = dedent(
        f"""
        PREVIOUS TEXT
        {previous_text or "なし"}

        USER INSTRUCTION
        {instruction}

        /no_think
        """
    ).strip()
    return ([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], {"context_window": model_def.generation.context_window, "generation": _merge_generation_config(req)})


async def call_local_novel_api(
    req: AINovelRequest | str,
    model: str | None = None,
    strict_json: bool = False,
) -> AINovelResponse:
    effective_model = (model or (req.model if isinstance(req, AINovelRequest) else None) or "").strip()
    if not is_local_model(effective_model):
        raise HTTPException(status_code=400, detail="ローカルLLMモデルが指定されていません。")

    if isinstance(req, AINovelRequest):
        request_for_prompt = req.copy(update={"model": effective_model})
        messages, prompt_meta = _build_local_novel_messages(request_for_prompt)
        generation = prompt_meta["generation"]
    else:
        model_def = get_local_model(effective_model)
        messages = [
            {"role": "system", "content": "あなたは日本語の小説執筆AIです。本文だけを生成してください。"},
            {"role": "user", "content": str(req)},
        ]
        generation = {
            "max_tokens": model_def.generation.max_tokens,
            "temperature": model_def.generation.temperature,
            "top_p": model_def.generation.top_p,
            "top_k": model_def.generation.top_k,
            "repeat_penalty": model_def.generation.repeat_penalty,
        }

    started = time.monotonic()
    data = await run_local_novel_job_until_complete(
        model=effective_model,
        messages=messages,
        generation=generation,
        strict_json=bool(strict_json),
    )
    raw_body = str(data.get("text") or "").strip()
    body = _clean_local_llm_text(raw_body)
    if not body:
        raise HTTPException(status_code=500, detail="ローカルLLMからの応答が空でした。")
    title = str(getattr(req, "title_hint", None) or getattr(req, "title", None) or "生成された小説").strip()
    parsed_json: dict | None = None
    if body.startswith("{") or body.startswith("["):
        try:
            candidate = _parse_json_payload(body)
            if isinstance(candidate, dict):
                parsed_json = candidate
        except Exception:
            parsed_json = None
    if parsed_json is not None:
        parsed_title = str(parsed_json.get("generated_title") or parsed_json.get("title") or "").strip()
        parsed_body = str(
            parsed_json.get("body")
            or parsed_json.get("text")
            or parsed_json.get("content")
            or parsed_json.get("novel")
            or ""
        ).strip()
        if parsed_title:
            title = parsed_title
        if parsed_body:
            body = _clean_local_llm_text(parsed_body)
    elif strict_json:
        parsed_title, parsed_body = _parse_title_and_body(body)
        title = parsed_title or title
        body = _clean_local_llm_text(parsed_body or body)
    target_chars = _target_chars_from_length(getattr(req, "length", None) if isinstance(req, AINovelRequest) else None)
    if strict_json and target_chars and target_chars >= 1000:
        min_chars = max(400, int(target_chars * 0.7))
        if len(body) < min_chars:
            raise HTTPException(
                status_code=500,
                detail=f"AI 応答の文字数が不足しています（{len(body)}/{target_chars}文字）。",
            )
    try:
        tokens = int(data["total_tokens"]) if data.get("total_tokens") is not None else None
    except Exception:
        tokens = None
    print("[INFO] local_llm_generation", json.dumps({"model_id": effective_model, "provider": "local", "generation_time": round(time.monotonic() - started, 3), "input_tokens": data.get("input_tokens"), "output_tokens": data.get("output_tokens"), "chars": len(body), "target_chars": target_chars, "gpu_vram": data.get("gpu_vram"), "success": True}, ensure_ascii=False))
    return AINovelResponse(generated_title=title or "生成された小説", body=body, used_tokens=tokens, model=effective_model, prompt_used=None)


def _local_llm_base_url() -> str:
    return os.getenv("LOCAL_LLM_BASE_URL", "http://local-llm:8000").rstrip("/")


def _local_llm_timeout() -> float:
    return float(os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", "900") or 900)


async def submit_local_novel_job(
    *,
    req: AINovelRequest,
    strict_json: bool = False,
) -> dict:
    effective_model = (req.model or "").strip()
    if not is_local_model(effective_model):
        raise HTTPException(status_code=400, detail="ローカルLLMモデルが指定されていません。")
    request_for_prompt = req.copy(update={"model": effective_model})
    messages, prompt_meta = _build_local_novel_messages(request_for_prompt)
    payload = {
        "model": effective_model,
        "messages": messages,
        "generation": prompt_meta["generation"],
        "strict_json": bool(strict_json),
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.post(f"{_local_llm_base_url()}/jobs", json=payload)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="ローカルLLM推論サーバに接続できません。") from e
    if resp.status_code >= 400:
        detail = "ローカルLLMジョブの作成に失敗しました。"
        try:
            data = resp.json()
            detail = str(data.get("detail") or data.get("error") or detail)
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code if resp.status_code < 500 else 502, detail=detail)
    return resp.json()


async def get_local_novel_job(job_id: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(f"{_local_llm_base_url()}/jobs/{job_id}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="ローカルLLM推論サーバに接続できません。") from e
    if resp.status_code >= 400:
        detail = "ローカルLLMジョブ状態の取得に失敗しました。"
        try:
            data = resp.json()
            detail = str(data.get("detail") or data.get("error") or detail)
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code if resp.status_code < 500 else 502, detail=detail)
    data = resp.json()
    result = data.get("result") if isinstance(data, dict) else None
    if isinstance(result, dict) and data.get("status") == "completed":
        body = str(result.get("text") or "").strip()
        result["body"] = body
        result["generated_title"] = "生成された小説"
        result["used_tokens"] = result.get("total_tokens")
    return data


async def cancel_local_novel_job(job_id: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.delete(f"{_local_llm_base_url()}/jobs/{job_id}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="ローカルLLM推論サーバに接続できません。") from e
    if resp.status_code >= 400:
        detail = "ローカルLLMジョブのキャンセルに失敗しました。"
        try:
            data = resp.json()
            detail = str(data.get("detail") or data.get("error") or detail)
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code if resp.status_code < 500 else 502, detail=detail)
    return resp.json()


async def get_local_llm_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(f"{_local_llm_base_url()}/status")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="ローカルLLM推論サーバに接続できません。") from e
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail="ローカルLLM状態の取得に失敗しました。")
    return resp.json()


async def run_local_novel_job_until_complete(
    *,
    model: str,
    messages: list[dict],
    generation: dict,
    strict_json: bool = False,
) -> dict:
    timeout = _local_llm_timeout()
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            create_resp = await http.post(
                f"{_local_llm_base_url()}/jobs",
                json={"model": model, "messages": messages, "generation": generation, "strict_json": bool(strict_json)},
            )
            if create_resp.status_code >= 400:
                detail = create_resp.text
                try:
                    detail = create_resp.json().get("detail") or detail
                except Exception:
                    pass
                raise HTTPException(status_code=create_resp.status_code if create_resp.status_code < 500 else 502, detail=detail)
            job_id = create_resp.json().get("job_id")
            if not job_id:
                raise HTTPException(status_code=502, detail="ローカルLLMジョブIDが返されませんでした。")
            while time.monotonic() - started < timeout:
                await asyncio.sleep(2.0)
                status_resp = await http.get(f"{_local_llm_base_url()}/jobs/{job_id}")
                if status_resp.status_code >= 400:
                    raise HTTPException(status_code=502, detail="ローカルLLMジョブ状態の取得に失敗しました。")
                status_data = status_resp.json()
                if status_data.get("status") == "completed":
                    return status_data.get("result") or {}
                if status_data.get("status") in {"failed", "cancelled"}:
                    raise HTTPException(status_code=502, detail=status_data.get("error") or "ローカルLLM生成に失敗しました。")
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="ローカルLLM推論サーバに接続できません。") from e
    raise HTTPException(status_code=504, detail="ローカルLLM推論がタイムアウトしました。")


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


def _clean_local_llm_text(raw: str) -> str:
    text = str(raw or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    text = re.sub(r"^<think>.*", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    text = _strip_code_fence(text).strip()
    return text


def _parse_json_payload(raw: str) -> dict:
    import ast
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
        # Fallback for pseudo-JSON like Python dict strings using single quotes.
        try:
            lit = ast.literal_eval(s)
            d = _extract_dict(lit)
            if d is not None:
                return d
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


def _is_openrouter_credit_error(err: Exception) -> bool:
    text = repr(err).lower()
    return (
        "error code: 402" in text
        or "'code': 402" in text
        or '"code": 402' in text
        or "requires more credits" in text
        or "can only afford" in text
    )


def _is_ai_credit_exhausted_error(err: Exception) -> bool:
    text = repr(err).lower()
    return (
        _is_openrouter_credit_error(err)
        or "insufficient_quota" in text
        or "quota exceeded" in text
        or "exceeded your current quota" in text
        or "check your plan and billing details" in text
        or "credit balance is too low" in text
        or "payment required" in text
    )


def _raise_ai_api_call_error(api_name: str, err: Exception) -> None:
    if _is_ai_credit_exhausted_error(err):
        raise HTTPException(
            status_code=402,
            detail="AIクレジットが不足しているため、この機能は現在利用できません。クレジット追加後に再試行してください。",
        )
    raise HTTPException(status_code=502, detail=f"{api_name} 呼び出しに失敗しました。しばらくしてから再試行してください。")


def _is_response_format_unsupported_error(err: Exception) -> bool:
    text = repr(err).lower()
    return (
        "response_format" in text
        and (
            "unsupported" in text
            or "not supported" in text
            or "invalid" in text
            or "unknown parameter" in text
            or "unrecognized" in text
        )
    )


def _extract_openrouter_affordable_tokens(err: Exception) -> int | None:
    m = re.search(r"can only afford\s+(\d+)", repr(err), flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


async def call_ai_json(
    prompt: str,
    *,
    model: str | None = None,
    provider: str | None = None,
    system_instructions: str | None = None,
    timeout_sec: float | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    max_output_tokens: int | None = None,
) -> tuple[dict, int | None, str | None]:
    if not prompt:
        raise HTTPException(status_code=400, detail="プロンプトが空です。")

    provider = (provider or "").strip().lower() or provider_from_model(model)
    system_instructions = system_instructions or "JSON 1個のみを返してください。"
    try:
        configured_max_output_tokens = (
            int(max_output_tokens)
            if max_output_tokens is not None
            else int(os.getenv("AI_JSON_MAX_OUTPUT_TOKENS", "8192"))
        )
    except Exception:
        configured_max_output_tokens = 8192
    max_output_tokens = max(128, min(16384, configured_max_output_tokens))
    effective_timeout: float | None = None
    if timeout_sec is not None:
        try:
            parsed_timeout = float(timeout_sec)
            if parsed_timeout > 0:
                effective_timeout = max(5.0, min(900.0, parsed_timeout))
        except Exception:
            effective_timeout = None

    async def _await_api_call(awaitable):
        if effective_timeout is None:
            return await awaitable
        try:
            return await asyncio.wait_for(awaitable, timeout=effective_timeout)
        except asyncio.TimeoutError as e:
            raise HTTPException(
                status_code=504,
                detail=f"AI 翻訳 API 呼び出しがタイムアウトしました（{int(effective_timeout)}秒）。",
            ) from e

    local_tokens: int | None = None
    resp = None
    if provider == "local":
        effective_model = (
            (model or "").strip()
            or (os.getenv("AI_CHAT_LOCAL_MODEL", "") or "").strip()
            or (os.getenv("LOCAL_LLM_DEFAULT_MODEL", "") or "").strip()
            or "local-qwen3-8b-nsfw-jp"
        )
        if not is_local_model(effective_model):
            raise HTTPException(status_code=400, detail="ローカルLLMモデルが指定されていません。")
        try:
            local_max_output_tokens = int(os.getenv("AI_CHAT_LOCAL_MAX_OUTPUT_TOKENS", "1200") or 1200)
        except Exception:
            local_max_output_tokens = 1200
        generation = {
            "max_tokens": max(128, min(max_output_tokens, local_max_output_tokens, 4096)),
            "temperature": max(0.0, min(2.0, float(temperature if temperature is not None else 0.7))),
            "top_p": max(0.0, min(1.0, float(top_p if top_p is not None else 0.85))),
        }
        data = await run_local_novel_job_until_complete(
            model=effective_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        system_instructions
                        + "\n推論過程、<think>タグ、説明文は出力しないでください。可能ならJSON 1個のみを返してください。"
                    ),
                },
                {"role": "user", "content": prompt + "\n\n/no_think"},
            ],
            generation=generation,
            strict_json=False,
        )
        raw = str(data.get("text") or "").strip()
        try:
            local_tokens = int(data["total_tokens"]) if data.get("total_tokens") is not None else None
        except Exception:
            local_tokens = None
    elif provider == "deepseek":
        if deepseek_client is None:
            raise HTTPException(status_code=500, detail="DeepSeek の API キーが設定されていません。")
        effective_model = (model or os.getenv("DEEPSEEK_MODEL_TEXT") or "").strip()
        if effective_model.startswith("deepseek:"):
            effective_model = effective_model.split(":", 1)[1].strip()
        if not effective_model:
            raise HTTPException(status_code=400, detail="モデルが指定されていません。")
        try:
            create_kwargs = {
                "model": effective_model,
                "messages": [
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": max_output_tokens,
            }
            if temperature is not None:
                create_kwargs["temperature"] = max(0.0, min(2.0, float(temperature)))
            if top_p is not None:
                create_kwargs["top_p"] = max(0.0, min(1.0, float(top_p)))
            resp = await _await_api_call(
                asyncio.to_thread(
                    deepseek_client.chat.completions.create,
                    **create_kwargs,
                )
            )
        except HTTPException:
            raise
        except Exception as e:
            print("[ERROR] DeepSeek API 呼び出し失敗:", repr(e))
            _raise_ai_api_call_error("AI JSON API", e)

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
        assert_openrouter_model_allowed_for_pricing(effective_model)
        try:
            create_kwargs = {
                "model": effective_model,
                "messages": [
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": max_output_tokens,
            }
            if temperature is not None:
                create_kwargs["temperature"] = max(0.0, min(2.0, float(temperature)))
            if top_p is not None:
                create_kwargs["top_p"] = max(0.0, min(1.0, float(top_p)))
            resp = await _await_api_call(
                asyncio.to_thread(
                    openrouter_client.chat.completions.create,
                    **create_kwargs,
                )
            )
        except HTTPException:
            raise
        except Exception as e:
            print("[ERROR] OpenRouter API 呼び出し失敗:", repr(e))
            _raise_ai_api_call_error("AI JSON API", e)

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
            create_kwargs = {
                "model": effective_model,
                "messages": [
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                # GPT-5系では chat.completions の出力上限は max_completion_tokens が必要。
                "max_completion_tokens": max_output_tokens,
            }
            if temperature is not None:
                create_kwargs["temperature"] = max(0.0, min(2.0, float(temperature)))
            if top_p is not None:
                create_kwargs["top_p"] = max(0.0, min(1.0, float(top_p)))
            # Use Chat Completions with response_format to guarantee valid JSON.
            resp = await _await_api_call(
                asyncio.to_thread(
                    client.chat.completions.create,
                    **create_kwargs,
                )
            )
        except HTTPException:
            raise
        except Exception as e:
            print("[ERROR] OpenAI Chat API 呼び出し失敗:", repr(e))
            _raise_ai_api_call_error("AI JSON API", e)

        raw = ""
        try:
            raw = resp.choices[0].message.content or ""
        except Exception:
            raw = ""

    if not raw:
        raise HTTPException(status_code=500, detail="AI からの応答が空でした。")

    try:
        data = _parse_json_payload(raw)
    except Exception as e:
        if provider == "local":
            fallback_reply = _clean_local_llm_text(raw)
            if fallback_reply:
                data = {"reply": fallback_reply}
            else:
                _log_ai_raw_response(raw, "call_ai_json")
                print("[ERROR] AI JSON parse failed:", repr(e))
                raise HTTPException(status_code=500, detail="AI 応答の JSON 解析に失敗しました。")
        else:
            _log_ai_raw_response(raw, "call_ai_json")
            print("[ERROR] AI JSON parse failed:", repr(e))
            raise HTTPException(status_code=500, detail="AI 応答の JSON 解析に失敗しました。")

    tokens: int | None = local_tokens
    if tokens is None:
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
        _raise_ai_api_call_error("AI 小説生成 API", e)

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

    data, tokens, effective_model = await call_ai_json(
        prompt,
        model=effective_model,
        provider=provider_from_model(effective_model),
        system_instructions="あなたは日本語の編集者です。必ず JSON のみを返してください。",
        max_output_tokens=512,
    )

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

    return normalized, tokens, effective_model


async def call_openai_catch_copy_candidates(
    text: str,
    model: str | None = None,
    suggestions_count: int = 4,
) -> tuple[list[str], int | None, str]:
    source_text = (text or "").strip()
    if not source_text:
        raise HTTPException(status_code=400, detail="本文が空です。")

    effective_model = (model or os.getenv("OPENAI_MODEL_TEXT") or OPENAI_MODEL_TEXT).strip()
    count = max(2, min(8, int(suggestions_count or 4)))
    prompt = dedent(
        f"""
        以下の作品情報から、クリック率を高めやすい日本語のキャッチコピー候補を{count}個作成してください。
        条件:
        - 18〜60文字程度
        - SNS共有文や SEO description の冒頭にも使いやすい自然な短文
        - 誇張しすぎず、内容の魅力や読後フックを簡潔に伝える
        - 候補同士は切り口を少し変える
        出力は必ず JSON のみ。形式: {{"candidates": ["候補1", "候補2"]}}

        作品情報:
        {source_text}
        """
    ).strip()

    data, tokens, effective_model = await call_ai_json(
        prompt,
        model=effective_model,
        provider=provider_from_model(effective_model),
        system_instructions="あなたは日本語の編集者兼コピーライターです。必ず JSON のみを返してください。",
        max_output_tokens=256,
    )

    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not isinstance(candidates, list):
        raise HTTPException(status_code=500, detail="AI 応答の形式が不正です。")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if not isinstance(item, str):
            continue
        cleaned = re.sub(r"\s+", " ", item).strip().strip('"').strip("'")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned[:80])

    if not normalized:
        raise HTTPException(status_code=500, detail="AI から候補が取得できませんでした。")

    return normalized, tokens, effective_model


async def call_openai_tag_candidates(text: str, model: str | None = None) -> tuple[list[str], int | None, str]:
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

    data, tokens, effective_model = await call_ai_json(
        prompt,
        model=effective_model,
        provider=provider_from_model(effective_model),
        system_instructions="あなたは日本語の編集者です。必ず JSON のみを返してください。",
        temperature=0.2,
        max_output_tokens=256,
    )

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

    return normalized, tokens, effective_model


async def call_openai_title_candidate(text: str, model: str | None = None) -> tuple[str, int | None, str]:
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

    data, tokens, effective_model = await call_ai_json(
        prompt,
        model=effective_model,
        provider=provider_from_model(effective_model),
        system_instructions="あなたは日本語の編集者です。必ず JSON のみを返してください。",
        temperature=0.2,
        max_output_tokens=128,
    )

    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str):
        raise HTTPException(status_code=500, detail="AI 応答の形式が不正です。")
    normalized = title.strip().strip('"').strip("'")
    if not normalized:
        raise HTTPException(status_code=500, detail="AI からタイトルが取得できませんでした。")

    return normalized[:40], tokens, effective_model


async def call_openai_title_candidates(
    text: str,
    model: str | None = None,
    suggestions_count: int = 5,
) -> tuple[list[str], int | None, str]:
    source_text = (text or "").strip()
    if not source_text:
        raise HTTPException(status_code=400, detail="本文が空です。")

    effective_model = (model or os.getenv("OPENAI_MODEL_TEXT") or OPENAI_MODEL_TEXT).strip()
    count = max(2, min(8, int(suggestions_count or 5)))
    prompt = dedent(
        f"""
        以下の本文に合う小説タイトル候補を{count}個作成してください。
        条件:
        - 日本語
        - 40文字以内
        - 記号の多用は避ける
        - 候補同士は語感や切り口を少し変える
        出力は必ず JSON のみ。形式: {{"candidates": ["候補1", "候補2"]}}

        本文:
        {source_text}
        """
    ).strip()

    data, tokens, effective_model = await call_ai_json(
        prompt,
        model=effective_model,
        provider=provider_from_model(effective_model),
        system_instructions="あなたは日本語の編集者です。必ず JSON のみを返してください。",
        temperature=0.2,
        max_output_tokens=256,
    )

    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not isinstance(candidates, list):
        raise HTTPException(status_code=500, detail="AI 応答の形式が不正です。")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if not isinstance(item, str):
            continue
        v = item.strip().strip('"').strip("'")
        if not v:
            continue
        v = v[:40]
        lk = v.lower()
        if lk in seen:
            continue
        seen.add(lk)
        normalized.append(v)
    if not normalized:
        raise HTTPException(status_code=500, detail="AI からタイトル候補が取得できませんでした。")

    return normalized, tokens, effective_model


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
    assert_openrouter_model_allowed_for_pricing(effective_model)

    base_max_tokens = OPENROUTER_NOVEL_MAX_TOKENS
    token_candidates = [base_max_tokens, 1536, 1400, 1200, 1000, 800, 640, 512]
    seen_tokens: set[int] = set()
    max_tokens_attempts: list[int] = []
    for value in token_candidates:
        v = max(512, min(base_max_tokens, int(value)))
        if v in seen_tokens:
            continue
        seen_tokens.add(v)
        max_tokens_attempts.append(v)

    resp = None
    last_error: Exception | None = None
    json_mode_unavailable = False
    for max_tokens in max_tokens_attempts:
        try:
            create_kwargs = {
                "model": effective_model,
                "messages": [
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
                "max_tokens": max_tokens,
            }
            if strict_json and not json_mode_unavailable:
                create_kwargs["response_format"] = {"type": "json_object"}
            resp = await asyncio.to_thread(
                openrouter_client.chat.completions.create,
                **create_kwargs,
            )
            break
        except Exception as e:
            if strict_json and not json_mode_unavailable and _is_response_format_unsupported_error(e):
                json_mode_unavailable = True
                max_tokens_attempts.insert(0, max_tokens)
                continue
            last_error = e
            if not _is_openrouter_credit_error(e):
                print("[ERROR] OpenRouter API 呼び出し失敗:", repr(e))
                _raise_ai_api_call_error("AI 小説生成 API", e)

            affordable = _extract_openrouter_affordable_tokens(e)
            if affordable is not None:
                # limit を少し下げて余裕を作る
                emergency_tokens = max(512, min(base_max_tokens, affordable - 64))
                if emergency_tokens not in seen_tokens:
                    seen_tokens.add(emergency_tokens)
                    max_tokens_attempts.append(emergency_tokens)
            continue

    if resp is None:
        print("[ERROR] OpenRouter API 呼び出し失敗:", repr(last_error))
        if last_error is None:
            raise HTTPException(status_code=502, detail="AI 小説生成 API 呼び出しに失敗しました。")
        _raise_ai_api_call_error("AI 小説生成 API", last_error)

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
