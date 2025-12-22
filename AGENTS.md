# AGENTS.md

このリポジトリは小説投稿サイト（FastAPI + React + MySQL + nginx + Docker）です。  
Codex で作業するときの要点と入口をまとめます。

## 構成と主な入口

- Backend: `backend/app/main.py`（FastAPI 本体、OAuth/Stripe/AI 生成などもここ）
- Backend routers: `backend/app/routers/*.py`（novels/episodes/two_factor）
- DB: `backend/app/models.py`, `backend/app/schemas.py`, `backend/app/database.py`
- Frontend: `frontend/src/main.jsx` → `frontend/src/App.jsx` → `frontend/src/pages/*`
- 静的ファイル: `static/episode_images`, `frontend/public`
- nginx: `nginx/`
- Docker: `docker-compose.yml`, `docker-compose.free.yml`
- バックアップ類: `backend/app/main.py.bak*`, `backend/app/models.py.bak*` は参照用。基本は編集しない。

## 開発コマンド（ローカル）

- Docker 起動: `docker compose up --build`（または `docker compose -f docker-compose.free.yml up --build`）
- Backend 単体起動: `cd backend` → `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Frontend dev: `cd frontend` → `npm install` → `npm run dev`
- Frontend build: `cd frontend` → `npm run build`

## 重要な環境変数（抜粋）

- DB: `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_NAME`
- Auth/JWT: `JWT_SECRET_KEY`
- OAuth: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `X_OAUTH_CLIENT_ID`, `X_OAUTH_CLIENT_SECRET`
- OAuth URL: `FRONTEND_ORIGIN`, `BACKEND_ORIGIN`, `OAUTH_STATE_EXPIRE_MINUTES`
- Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID`
- Mail: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`
- AI: `OPENAI_MODEL_TEXT`, `OPENROUTER_MODEL_TEXT`, `DEEPSEEK_MODEL_TEXT` など

## DB/スキーマ運用の注意

- マイグレーションツールは未導入。`backend/app/main.py` の `ensure_*` が起動時にカラム補完する前提。
- schema/models を変えたら DB の `ALTER TABLE` も必要。

## 編集の指針

- フロントは `frontend/dist` を手で触らず、`frontend/src` を変更して `npm run build`。
- 既存挙動への影響が大きい変更は `backend/app/main.py` で広範に波及するため、関係 API を確認してから編集。

## テスト

- 自動テストは未整備。必要なら API の手動確認手順を記載する。
