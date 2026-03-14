# novel-site

FastAPI + React + MySQL + nginx + Docker で構成した小説投稿サイトです。

## 技術スタック

- Backend: FastAPI (Python) + Uvicorn
- Frontend: React + Vite
- DB: MySQL 8.0
- Web: nginx
- SSL: Let's Encrypt (certbot)
- Orchestration: Docker Compose

## 主な機能（現状）

- 認証
  - ユーザー登録 / ログイン
  - パスワードリセット（メール）
  - OAuth ログイン（Google / X）
  - ログインコード検証（`/api/auth/login/start`, `/api/auth/login/verify`）
- 小説
  - 作成 / 編集 / 削除
  - 公開 / 下書き
  - タグ、年齢区分（`all/r15/r18`）、創作区分（`original/fanfic`）
  - 公開ランキング、公開プロフィール連携
- エピソード
  - 作成 / 編集 / 削除
  - 公開 / 下書き
  - カバー画像・挿絵アップロード
  - 共有ページ（`/share/episodes/{id}`）
- コミュニティ
  - 小説/エピソードのコメント
  - 小説/エピソードのいいね
  - 小説のお気に入り（favorite）
  - DM（スレッド + メッセージ）
  - 通知センター（未読数 API 含む）
- 作者向け
  - 作品分析（analytics）
  - 支援プラン管理
  - 残高表示 / 振込プロフィール設定
- 支援/課金
  - Stripe Checkout（単発支援 / 月額支援）
  - Stripe webhook 連携
- AI
  - 小説生成・続き生成
  - タイトル候補 / タグ候補 / 要約候補
  - 生成ジョブ管理（ユーザー/管理者）
  - AI 利用ログ
  - AIチャット:
    - 自動会話モード（停止ボタン + チャットで「停止」「止める」停止）
    - ゲスト会話のログイン時移行（JSONバックアップ自動保存）
    - 同名キャラの複製作成 + インデックス表示（`#1`, `#2`）
    - キャラ削除は論理削除（`is_deleted`）
- 管理
  - 管理者ログイン
  - ユーザー管理
  - 問い合わせ管理
  - 支払プレビュー / 支払生成 / ステータス更新
  - Indexing URL 送信、`/sitemap.xml`

## ディレクトリ構成（抜粋）

- `backend/` FastAPI アプリ
- `frontend/` React + Vite
- `nginx/` nginx 設定・証明書関連
- `static/episode_images/` エピソード画像
- `docker-compose.yml` 本番想定構成
- `docker-compose.free.yml` ローカル検証用構成

## ローカル開発

前提: Docker / Docker Compose がインストール済み

```bash
git clone <your-repo-url>
cd novel-site
docker compose up --build
# または
# docker compose -f docker-compose.free.yml up --build
```

`frontend/dist` を nginx が配信するため、フロント変更後はビルドが必要です。

```bash
cd frontend
npm install
npm run build
cd ..
docker compose restart nginx
```

## Backend / Frontend 単体起動

Backend:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## 主要環境変数（抜粋）

- DB: `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`
- Auth/JWT: `JWT_SECRET_KEY`
- OAuth: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `X_OAUTH_CONSUMER_KEY`, `X_OAUTH_CONSUMER_SECRET`
- OAuth URL: `FRONTEND_ORIGIN`, `BACKEND_ORIGIN`
- Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID`
- Admin: `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `ADMIN_JWT_SECRET`
- Mail: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`
- Push: `WEBPUSH_VAPID_PUBLIC_KEY`, `WEBPUSH_VAPID_PRIVATE_KEY`, `WEBPUSH_VAPID_SUBJECT`
- AI: `OPENAI_API_KEY`, `OPENAI_MODEL_TEXT`, `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`

## 運用・開発時の注意点

- マイグレーションツール未導入:
  - `backend/app/main.py` の `ensure_*` で不足カラムを補完する設計。
  - schema/model 変更時は `ALTER TABLE` 等の手動DDLが必要。
- API 実装は `backend/app/main.py` に集約:
  - `backend/app/routers/*.py` は一部旧実装が残るため、修正箇所を誤らない。
- AIチャットの同名キャラ運用:
  - 同名は別IDで作成できる（上書きしない）。
  - APIレスポンスに `is_name_duplicate`, `name_duplicate_index` を含み、UIで識別表示する。
- AIチャットの削除/学習:
  - キャラ削除は `ai_chat_characters` の論理削除（`is_deleted`, `deleted_at`）。
  - 学習キー（`character_profile_key`）は同名キャラ間で継続される仕様（キャラ名 + speech_gender ベース）。
- 公開状態は互換対応が混在:
  - `status` と `is_public` を併用する箇所があるため、公開ロジック変更時は一覧/詳細/権限を横断確認する。
- フロント成果物:
  - `frontend/dist` は編集せず `frontend/src` を編集し再ビルドする。
- 機密情報管理:
  - `.env` や証明書ファイルの取り扱いに注意（本番鍵は安全な保管先で管理）。

## 現状の開発要点（2026-03 時点）

- フィードAPIのログイン要件:
  - `GET /api/feed/new` はゲスト利用可（新着順）。
  - `GET /api/feed/trending` はゲスト利用可（急上昇）。
  - `GET /api/feed/recommended` はゲスト利用可。未ログイン時は公開おすすめロジックへフォールバック。
  - 期限切れ/不正トークンが来ても、上記3APIは `401` ではなくゲスト扱いにフォールバックする実装。
- ホーム画面表示方針:
  - ホーム（`sort=new` かつ検索条件なし）では、ログイン有無に関わらず「おすすめ」「急上昇作品」を表示。
  - 「フォロー中の新着」「フォロー中タグの新着」はセクション自体は表示し、未ログイン時は案内文を表示。
- 管理画面の Google Indexing:
  - 繰越キューは送信時に最優先。
  - 未登録優先は Search Console 検査結果（`inspect=1`）を使ってフロント側で並び替える。
- AIチャット背景画像:
  - キャラ画像がある場合、背景は `position: fixed` で表示され、スクロールしても維持。

## 反映手順（重要）

- `docker compose build backend` だけでは、実行中コンテナには反映されません。
- バックエンド反映は以下を実施:

```bash
docker compose up --build -d backend
```

- フロント反映は以下を実施:

```bash
cd frontend
npm run build
cd ..
docker compose restart nginx
```

## テスト

- 自動テストは最小限です。
- 現状の実行可能テスト:

```bash
cd frontend
npm test
```

必要に応じて API の手動確認手順をPRや作業メモに記載してください。
