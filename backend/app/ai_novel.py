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

def call_openai_novel_api(prompt: str) -> AINovelResponse:
    """
    Responses API を使って小説テキストを生成し、
    AINovelResponse を返す。
    """
    if client is None:
        raise HTTPException(status_code=500, detail="OpenAI クライアントの初期化に失敗しています。")

    try:
        response = client.responses.create(  # Responses API の推奨パターン 
            model=OPENAI_MODEL_TEXT,
            input=[
                {
                    "role": "system",
                    "content": "あなたは日本語で読みやすい小説を書く作家です。",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.9,
            max_output_tokens=4096,
            text={
                "format": {
                    "type": "text",
                }
            },
        )

    except Exception as e:
        # API 側のエラーは 502 / 503 相当で返す
        raise HTTPException(
            status_code=502,
            detail=f"AI 小説生成 API 呼び出しに失敗しました: {e}",
        )

    # Python SDK では output_text プロパティにテキスト全体が入っている 
    raw_text = getattr(response, "output_text", None)
    if not raw_text:
        # 念のため、output 配列から拾うフォールバックも用意しておく
        try:
            # 最初の message → 最初の content → text
            first_message = response.output[0]
            first_content = first_message.content[0]
            raw_text = first_content.text
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="AI 小説生成の結果を解析できませんでした。",
            )

    title, body = split_title_and_body(raw_text)

    used_tokens = None
    try:
        if response.usage:
            used_tokens = response.usage.total_tokens  # 入出力合計トークン
    except Exception:
        used_tokens = None

    return AINovelResponse(
        generated_title=title,
        body=body,
        used_tokens=used_tokens,
        model=response.model if hasattr(response, "model") else OPENAI_MODEL_TEXT,
    )

