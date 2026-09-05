# Local CPU LLM for AI Novel Generation

Lexis AI小説生成の外部APIとは別に、`local-llm` サービスで llama.cpp / GGUF のCPU推論を行う構成です。FastAPI本体は `LOCAL_LLM_BASE_URL` 経由でローカル推論サーバへジョブを投入します。

## Architecture

```
React AINovelPage
  -> FastAPI AI novel routes
  -> local LLM provider/proxy
  -> local-llm FastAPI queue
  -> llama-cpp-python
  -> GGUF model file
```

外部OpenAI/OpenRouter/DeepSeek経路は維持しています。ローカル推論サーバはlazy loadで、起動時に14Bをロードしません。`LOCAL_LLM_PRELOAD_MODEL` を指定した場合のみ起動時ロードします。


## Current Setup

2026-08-31時点で `local-llm` はDocker Composeサービスとして有効化済みです。

- Compose service: `local-llm`
- Container: `lexis-local-llm`
- Backend URL: `LOCAL_LLM_BASE_URL=http://local-llm:8000`
- Host URL: `http://127.0.0.1:8008`
- Host port setting: `LOCAL_LLM_HOST_PORT=8008`
- Model volume: `./models:/models:ro`
- Startup mode: lazy load。`LOCAL_LLM_PRELOAD_MODEL` が空なら起動時にモデルをロードしません。

起動確認済みの状態:

```bash
docker compose ps local-llm
curl -sS http://127.0.0.1:8008/health
curl -sS http://127.0.0.1:8008/models
```

`/health` が `{"ok":true,"loaded_model":null,...}` を返せばサーバーは起動済みです。`loaded_model:null` はlazy loadの正常状態です。

## Startup

通常起動:

```bash
docker compose up -d local-llm
```

バックエンドも含めて再起動する場合:

```bash
docker compose up -d local-llm backend
```

ログ確認:

```bash
docker compose logs --tail=100 local-llm
```

停止:

```bash
docker compose stop local-llm
```

モデルをメモリから明示的に降ろす場合:

```bash
curl -sS -X POST http://127.0.0.1:8008/unload
```

## Model Download and Placement

このリポジトリではGGUFモデル本体をGit管理しません。`models/` は `.gitignore` 対象です。必要なモデルを1つずつ配置してください。この環境の空き容量は2026-08-31時点で約17GBのため、3モデルを同時に置く運用は避けます。

配置先:

```bash
mkdir -p models/doujinshi-14b models/llama3-jprp-8b models/qwen3-8b-nsfw-jp
```

推奨はまず軽い8Bモデルを1つだけ配置して疎通確認することです。

```bash
# 例: huggingface-cli を使う場合。ライセンスと利用規約を確認してから実行してください。
huggingface-cli download mradermacher/Qwen3-8B-NSFW-JP-GGUF \
  Qwen3-8B-NSFW-JP.Q4_K_M.gguf \
  --local-dir models/qwen3-8b-nsfw-jp \
  --local-dir-use-symlinks False
```

配置後、`available:true` になることを確認します。

```bash
curl -sS http://127.0.0.1:8008/models
```

## Backend Connectivity Check

バックエンドコンテナから疎通を確認するには以下を実行します。

```bash
docker compose exec -T backend python - <<'PY'
import os, httpx
url = os.getenv('LOCAL_LLM_BASE_URL', 'http://local-llm:8000').rstrip('/')
print('LOCAL_LLM_BASE_URL=' + url)
print(httpx.get(url + '/health', timeout=5).text)
PY
```

モデル配置後は、管理APIからも確認できます。

```bash
# admin認証が必要
GET /api/admin/local-llm/status
```

## Generation Smoke Test

モデル配置後の最小テストです。モデルファイルがない状態では `503 model file is not configured or missing` が返ります。

```bash
curl -sS -X POST http://127.0.0.1:8008/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"local-qwen3-8b-nsfw-jp",
    "messages":[{"role":"user","content":"短い日本語の挨拶を1文で書いて"}],
    "generation":{"max_tokens":80}
  }'
```

## Models

| Lexis ID | Model | HF repo | GGUF | Quant | Size | RAM目安 | License | Status |
| --- | --- | --- | --- | --- | ---: | ---: | --- | --- |
| `local-doujinshi-14b` | Doujinshi-14B-roleplay | https://huggingface.co/puwaer/Doujinshi-14b-roleplay / https://huggingface.co/puwaer/Doujinshi-14b-roleplay-gguf | `Doujinshi-14b-roleplay-Q4_K_M.gguf` | Q4_K_M | 約8.38GiB | 13GB以上 | Apache-2.0 | 導入対象 |
| `local-llama3-jprp-8b` | Llama-3-JPRP-NSFW-8B | https://huggingface.co/melt-adzuki/Llama-3-JPRP-NSFW-8B / https://huggingface.co/mradermacher/Llama-3-JPRP-NSFW-8B-GGUF | `Llama-3-JPRP-NSFW-8B.Q4_K_M.gguf` | Q4_K_M | 約4.58GiB | 8GB以上 | llama3 | 導入対象、Meta Llama 3 license要確認 |
| `local-qwen3-8b-nsfw-jp` | Qwen3-8B-NSFW-JP | https://huggingface.co/Aratako/Qwen3-8B-NSFW-JP / https://huggingface.co/mradermacher/Qwen3-8B-NSFW-JP-GGUF | `Qwen3-8B-NSFW-JP.Q4_K_M.gguf` | Q4_K_M | 約4.68GiB | 8GB以上 | MIT | 導入対象 |

Notes:

- Doujinshi GGUF repo is published as Apache-2.0 and lists Q4_K_M as about 9GB. The model card states adult/sensitive training data. Webサービスで使う前にLexisの成人向け規約、年齢確認、公開範囲制御を維持してください。
- Llama-3-JPRP is Llama 3 licensed. Commercial/service use is not automatically forbidden, but Meta Llama 3 attribution/acceptable-use/license obligations must be reviewed before production use.
- Qwen3-8B-NSFW-JP base repo is MIT. The mradermacher GGUF page is MIT and provides Q4_K_M.
- 2026-08-30時点の空き容量は `/home/ubuntu` が約16GBです。Q4三本合計は約17.64GiB以上になるため、この環境へ3本同時ダウンロードしないでください。

## Model Paths

モデルファイルはGit管理しません。配置例:

```
models/doujinshi-14b/Doujinshi-14b-roleplay-Q4_K_M.gguf
models/llama3-jprp-8b/Llama-3-JPRP-NSFW-8B.Q4_K_M.gguf
models/qwen3-8b-nsfw-jp/Qwen3-8B-NSFW-JP.Q4_K_M.gguf
```

環境変数で上書きできます。

```
LOCAL_LLM_THREADS=8
LOCAL_LLM_CONTEXT_SIZE=32768
LOCAL_LLM_DOUJINSHI_MODEL_PATH=/models/doujinshi-14b/Doujinshi-14b-roleplay-Q4_K_M.gguf
LOCAL_LLM_JPRP_MODEL_PATH=/models/llama3-jprp-8b/Llama-3-JPRP-NSFW-8B.Q4_K_M.gguf
LOCAL_LLM_QWEN_MODEL_PATH=/models/qwen3-8b-nsfw-jp/Qwen3-8B-NSFW-JP.Q4_K_M.gguf
```

## APIs

- `GET /api/ai/novels/models`: 外部AI既定モデルとローカルモデル候補
- `POST /api/ai/novels/local/generate`: ローカルジョブ作成。premium user required。
- `GET /api/ai/novels/local/jobs/{job_id}`: ローカルジョブ状態取得。`queued/running/completed/failed/cancelled`。
- `DELETE /api/ai/novels/local/jobs/{job_id}`: queued job cancel、running jobはbest effort。
- `GET /api/admin/local-llm/status`: admin required。ロード済みモデル、利用可能モデル、running/queued、RSSを返す。

## Queue and Loading

`local-llm` は1 workerだけを起動し、CPU推論の同時実行を1に制限します。別モデルが選択された場合は現在のモデルをunloadし、`gc.collect()` 後に新モデルをロードします。3モデル同時常駐はしません。

## Benchmark

実モデルが配置された環境で以下を実行します。

```
python scripts/benchmark_novel_models.py --base-url http://localhost:8008 --max-tokens 1000
```

この作業時点では容量不足のためモデルをダウンロードしておらず、実測ベンチマークは未実施です。
