# novel-site

小説投稿サイト（FastAPI + React + MySQL + nginx + Docker）

- 本番運用を想定した小説投稿プラットフォーム
- Docker Compose で **backend / frontend / nginx / db / certbot** を一括管理
- AWS EC2 上で https 対応済み

## 🧱 技術スタック

- **Backend**: FastAPI (Python) + Uvicorn  
- **Frontend**: React (Vite)  
- **DB**: MySQL 8.0  
- **Web サーバ**: nginx  
- **SSL**: Let’s Encrypt（certbot）  
- **コンテナオーケストレーション**: Docker Compose  

主なディレクトリ構成（抜粋）:

- `backend/` … FastAPI アプリケーション一式  
- `frontend/` … React + Vite フロントエンド  
- `nginx/` … nginx 設定・Let’s Encrypt 用ディレクトリ  
- `static/episode_images/` … エピソード画像（静的ファイル）  
- `docker-compose.yml` … 本番用 Compose  
- `docker-compose.free.yml` … ローカル / 検証用 Compose などに使用想定  

---

## 🚀 ローカル開発（Docker）

前提: Docker / Docker Compose がインストール済み

```bash
git clone https://github.com/naoki51931/novel-site.git
cd novel-site
1. 初回起動（例）
docker-compose.free.yml を使う場合:

bash
コードをコピーする
docker compose -f docker-compose.free.yml up --build
または通常の docker-compose.yml を使う場合:

bash
コードをコピーする
docker compose up --build
適宜ブラウザで:

フロント: http://localhost:3000（設定により異なる）

API: http://localhost:8000 など

※ 実際のポートは docker-compose.yml を参照してください。

☁️ 本番デプロイ手順（AWS EC2 想定）
前提
OS: Ubuntu 22.04 / 24.04 あたり

デプロイ先ディレクトリ: /home/ubuntu/novel-site

ドメインを EC2 のパブリック IP に向けていること

docker / docker compose / git がインストール済み

1. リポジトリ取得 / 更新
bash
コードをコピーする
cd /home/ubuntu

# 初回
git clone https://github.com/naoki51931/novel-site.git
cd novel-site

# 2回目以降（更新反映）
cd /home/ubuntu/novel-site
git stash push -m "before pull main $(date +%Y%m%d-%H%M%S)"
git pull origin main
dist/ などビルド成果物はコンフリクト時に削除して再ビルドすれば OK。

2. 環境変数 / 設定
必要に応じて:

backend 配下の .env

DB 接続情報（docker-compose.yml の MYSQL_***）

nginx の server_name など

を自身の環境に合わせて編集します。

3. 本番コンテナ起動
bash
コードをコピーする
cd /home/ubuntu/novel-site
docker compose up -d --build
backend / db / nginx / certbot コンテナが起動します。

初回 SSL 設定は certbot コンテナや nginx コンフィグに応じて追加作業が必要な場合があります。

4. フロントエンドのビルド & 反映
フロントのコードを変更・更新した場合は必ずビルドが必要です。

bash
コードをコピーする
cd /home/ubuntu/novel-site/frontend
npm install        # package.json を更新した場合
npm run build      # dist/ が生成される

cd ..
docker compose restart nginx
frontend/dist/ の内容が nginx コンテナの /usr/share/nginx/html にマウントされている想定です。

🔁 更新時の基本フロー
Backend を修正したとき
bash
コードをコピーする
cd /home/ubuntu/novel-site
docker compose build backend
docker compose up -d backend
# またはシンプルに
docker compose restart backend
Frontend を修正したとき
bash
コードをコピーする
cd /home/ubuntu/novel-site/frontend
npm run build
cd ..
docker compose restart nginx
反映されない / キャッシュがおかしいとき
bash
コードをコピーする
cd /home/ubuntu/novel-site/frontend
rm -rf dist
npm run build
cd ..
docker compose restart nginx
📚 機能概要（現状）
Novel（小説）
公開ステータス

public / draft

旧 is_public は廃止（互換のためレスポンスに残っている場合あり）

draft の挙動:

トップページ一覧に表示されない

URL 直打ちしても、作者以外は 404 を返す

作者本人のみログイン後に閲覧・編集可能

Episode（エピソード）
2025-12 時点:

公開 / 非公開のステータスは未実装

将来的に Novel と同様の Draft / Public 対応を追加予定

🔍 デバッグ・ログ確認
backend ログ
bash
コードをコピーする
docker logs -f novel-backend
nginx アクセスログ
basha
コードをコピーする
docker logs -f novel-nginx
コード内で status を探す例
bash
コードをコピーする
# Backend 側
grep -n "status" backend/app/main.py

# Frontend 側
grep -n "setStatus" frontend/src/pages/EditNovel.jsx
🗃 DB 操作例（MySQL）
Novel のステータス確認
bash
コードをコピーする
docker exec -it novel-db mysql -umysqluser -pmysqlpass novel_db \
  -e "SELECT id, title, status, is_public FROM novels;"
特定の Novel を強制公開にする例
bash
コードをコピーする
docker exec -it novel-db mysql -umysqluser -pmysqlpass novel_db \
  -e "UPDATE novels SET status='public', is_public=1 WHERE id=9;"
※ schema / models を変更した場合は、必ず対応する ALTER TABLE などで DB も更新してください。

🛠 代表的なワンライナー（パッチ適用など）
EditNovel.jsx の status 初期化ロジック修正例
bash
コードをコピーする
sed -i 's/setStatus(data.status.*/if (data.status === "draft" || data.is_public === false) { setStatus("draft"); } else { setStatus("public"); }/' frontend/src/pages/EditNovel.jsx
Backend の公開フィルタを status ベースに変更する例
bash
コードをコピーする
sed -i 's/query = query.filter(models.Novel.is_public == True)/query = query.filter(models.Novel.status == "public")/' backend/app/main.py
🔮 今後の改善予定・アイデア
Episode にも Draft / Public ステータスを実装

Novel 削除時の不要コード整理

タグ検索性能向上（index 追加など）

Vite のキャッシュバスティング自動化（ファイル名ハッシュ等）

検索機能強化（タグ AND/OR、全文検索など）

エピソード公開の予約日時設定（指定時刻で自動的に public へ切り替え）

小説 / エピソードの編集履歴保存と差分表示

いいね / ブックマーク機能とランキング表示

通知センター（サイト内通知 + メール通知）

下書き共有リンクの発行・失効（限定公開）

アクセス解析ダッシュボード（PV/UU、リファラ、人気タグなど）

コメントの通報・モデレーション機能

📄 ライセンス
今後必要に応じてライセンスを追加予定です。
