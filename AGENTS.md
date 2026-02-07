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
- OAuth: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `X_OAUTH_CONSUMER_KEY`, `X_OAUTH_CONSUMER_SECRET`（環境によって `X_OAUTH_CLIENT_ID/SECRET` 名を使う設定が残っている場合あり）
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

- 自動テストは最小限（`frontend/tests/aiPolish.test.mjs`）。必要なら API の手動確認手順を記載する。

## 現状の機能（実装ベース）

- 認証: ユーザー登録 / ログイン、パスワードリセット、OAuth（Google/X）、2段階ログインコード（`/api/auth/login/start`,`/api/auth/login/verify`）
- 小説: 作成・編集・削除、公開/下書き、タグ、年齢区分（`all/r15/r18`）、創作区分（`original/fanfic`）
- エピソード: 作成・編集・削除、公開/下書き、カバー画像・挿絵アップロード、タグ
- コミュニティ: 小説/エピソードのコメント、いいね、ブックマーク（favorite）
- ユーザー機能: マイページ編集、通知センター、DM、作者ページ・ユーザーページ
- 支援/課金: Stripe Checkout（単発支援・月額）、作者の支援プラン、残高/振込プロフィール、管理者の支払生成・状態更新
- AI 機能: 小説生成、続き生成、タイトル/タグ/要約候補、生成ジョブ管理、AIログ
- 翻訳/SEO: 小説・エピソード翻訳 API、共有ページ（`/share/episodes/...`）、sitemap、Google Indexing 送信 API（管理者）

## 追加の注意点

- API の主実装は `backend/app/main.py` に集中している。`backend/app/routers/*.py` は一部旧実装が残るため、修正対象を取り違えない。
- DB マイグレーションツール未導入。起動時 `ensure_*` は「不足カラムの補完」が中心で、型変更・不要カラム整理・複雑なDDLは手動対応が必要。
- 公開状態は互換のため `status` と `is_public` を併用している箇所がある。公開制御を変える場合は一覧/詳細/権限チェックを必ず横断確認する。
- フロント変更は `frontend/src` を編集し、`npm run build` 後に nginx 配信物（`frontend/dist`）へ反映される前提。
- 画像は `static/episode_images` に保存し、nginx から `/static` 配下で配信する。保存パス変更時は backend・nginx・compose を同時に確認する。
