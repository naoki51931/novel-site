# backend/app/ai_novel.py

import os
from textwrap import dedent
from typing import Tuple

from fastapi import HTTPException
from openai import OpenAI
from dotenv import load_dotenv  # 既に他で使っていれば不要

# .env 読み込み（既にどこかでやっているならこの行は不要）
load_dotenv()

# ===== OpenAI クライアント初期化 =====

# 新SDK推奨スタイル:
# from openai import OpenAI
# client = OpenAI() で OK 
try:
    client = OpenAI()
except Exception as e:
    # 起動時に例外が出てもアプリ自体は動くようにしておく
    client = None

OPENAI_MODEL_TEXT = os.getenv("OPENAI_MODEL_TEXT", "gpt-5.1-mini")


# ===== Pydantic 用のリクエスト・レスポンス型（main.py 側でも使うならそこへ移動してもOK） =====

from pydantic import BaseModel


class AINovelRequest(BaseModel):
    title_hint: str | None = None
    genre: str | None = None
    characters: str | None = None
    tone: str | None = None
    length: str | None = "medium"  # "short" | "medium" | "long"


class AINovelResponse(BaseModel):
    generated_title: str
    body: str
    used_tokens: int | None = None
    model: str | None = None


# ===== プロンプト組み立て =====

def build_ai_prompt(req: AINovelRequest) -> str:
    """
    ユーザー入力から、モデルに渡す日本語プロンプト文字列を組み立てる。
    """
    length_map = {
        "short": "およそ 800〜1200 文字の短編",
        "medium": "およそ 2000〜3000 文字の中編",
        "long": "およそ 4000〜6000 文字のやや長めの中編",
    }
    length_text = length_map.get(req.length or "medium", length_map["medium"])

    genre = req.genre or "ジャンルは特に指定なし"
    tone = req.tone or "雰囲気は特に指定なし"
    characters = req.characters or "登場人物や設定の指定は特にない"

    title_hint = req.title_hint or "タイトルは内容に合うものをあなたが考えてほしい"

    # モデル側への指示（システム寄りメッセージ相当）は instructions でも良いが、
    # シンプルにユーザープロンプト内で完結させる。
    prompt = dedent(
        f"""
        あなたは日本語のライトノベル風の小説家です。
        以下の条件に合う短編小説を書いてください。

        # 出力フォーマット
        - 1行目に小説のタイトルだけを書く
        - 2行目は空行
        - 3行目以降に本文を書く

        # 制約
        - 一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。
        - 読みやすい段落構成にしてください。
        - 一人称 / 三人称は、物語に合うほうをあなたが選んでください。

        # 要望
        - 作品の長さ: {length_text}
        - ジャンル: {genre}
        - 雰囲気: {tone}
        - 登場人物・設定: {characters}
        - タイトルに関する要望: {title_hint}
        """
    ).strip()

    return prompt


# ===== 生成テキストからタイトルと本文を切り分ける =====

def split_title_and_body(text: str) -> Tuple[str, str]:
    """
    1行目 = タイトル, 2行目 = 空行想定で、本文と分離する。
    モデルの出力が多少ズレてもそこそこ頑丈に動くようにしている。
    """
    if not text:
        return "タイトル未設定", ""

    # 改行を統一
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = text.split("\n")
    # 先頭の空行を削る
    while lines and not lines[0].strip():
        lines.pop(0)

    if not lines:
        return "タイトル未設定", ""

    title = lines[0].strip()

    # 残りを本文として結合（2行目が空行であればそのまま残しておいてOK）
    body_lines = lines[1:] if len(lines) > 1 else []
    body = "\n".join(body_lines).lstrip("\n")

    if not title:
        title = "タイトル未設定"

    return title, body


# ===== 実際に OpenAI API を叩く関数 =====


async def call_openai_novel_api(req: AINovelRequest) -> AINovelResponse:
    """
    OpenAI Responses API を用いて小説を生成する。
    input は単一テキストで送信する。
    """
    import json
    import os

    model = (
        getattr(req, "model", None)
        or os.getenv("OPENAI_MODEL_TEXT")
        or "gpt-4.1-mini"
    ).strip()

    prompt = build_ai_prompt(req)

    # OpenAI 呼び出し
    resp = client.responses.create(
        model=model,
        instructions=(
            "あなたは日本語ライトノベル作家です。"
            "与えられた条件に基づいて短編小説を生成してください。"
            "出力は必ず JSON 1個のみ。"
            '例: {\\"title\\": \\"タイトル\\", \\"body\\": \\"本文\\"}'
        ),
        input=prompt,
        max_output_tokens=getattr(req, "max_tokens", None) or 2048,
    )

    raw = resp.output_text or ""

    # JSON パース
    title = ""
    body = raw
    try:
        data = json.loads(raw)
        title = str(data.get("title") or "")
        body = str(data.get("body") or "")
    except:
        lines = raw.splitlines()
        if lines:
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip()

    tokens = 0
    usage = getattr(resp, "usage", None)
    if usage is not None:
        tokens = getattr(usage, "total_tokens", 0) or 0

    return AINovelResponse(
        generated_title=title,
        body=body,
        prompt_used=prompt,
        model=model,
        tokens_used=tokens,
    )

