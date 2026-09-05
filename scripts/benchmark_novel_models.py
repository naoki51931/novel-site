from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx


MODELS = [
    "local-doujinshi-14b",
    "local-llama3-jprp-8b",
    "local-qwen3-8b-nsfw-jp",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8008")
    parser.add_argument("--max-tokens", type=int, default=600)
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args()

    out_dir = Path("benchmark_results")
    out_dir.mkdir(exist_ok=True)
    summary = []
    messages = [
        {
            "role": "system",
            "content": (
                "あなたは日本語の小説執筆AIです。登場人物は全員25歳以上の成人です。"
                "本文だけを生成し、設定と文体の連続性を維持してください。"
            ),
        },
        {
            "role": "user",
            "content": (
                "PREVIOUS TEXT\n"
                "雨の夜、編集者の綾乃は、閉店後の小さな書店で古い手紙を見つけた。\n\n"
                "USER INSTRUCTION\n"
                "成人同士の恋愛小説として、この続きを日本語で情感豊かに書いてください。"
            ),
        },
    ]
    with httpx.Client(timeout=args.timeout) as client:
        for model in MODELS:
            started = time.monotonic()
            row = {"model": model, "error": None}
            try:
                resp = client.post(
                    f"{args.base_url.rstrip('/')}/generate",
                    json={
                        "model": model,
                        "messages": messages,
                        "generation": {"max_tokens": args.max_tokens},
                    },
                )
                row["http_status"] = resp.status_code
                data = resp.json()
                if resp.status_code >= 400:
                    row["error"] = data.get("detail") or data.get("error") or resp.text[:300]
                else:
                    text = str(data.get("text") or "")
                    (out_dir / f"{model}.txt").write_text(text, encoding="utf-8")
                    row.update(
                        {
                            "first_load_time": data.get("load_seconds"),
                            "generation_time": data.get("generation_time"),
                            "tokens_per_sec": data.get("tokens_per_sec"),
                            "memory": data.get("memory"),
                            "input_tokens": data.get("input_tokens"),
                            "output_tokens": data.get("output_tokens"),
                        }
                    )
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            row["wall_time"] = time.monotonic() - started
            summary.append(row)
            print(json.dumps(row, ensure_ascii=False))

    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
