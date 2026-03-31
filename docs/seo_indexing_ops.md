# SEO / Indexing 運用ガイド

## 実装概要

- `GET /sitemap.xml`
  - サイトマップインデックスを返す（必要に応じて分割 sitemap を参照）。
- `GET /sitemap-static.xml`
- `GET /sitemap-novels.xml`
- `GET /sitemap-episodes.xml`
- `GET /sitemap-authors.xml`
- `GET /sitemap-tags.xml`
- `GET /robots.txt`
- `POST /api/admin/indexnow/submit`
  - 管理者API。Bing/IndexNow に URL 群を送信する。
- `GET /prerender/novels/{id}`
- `GET /prerender/episodes/{id}`
  - bot向け prerender HTML（nginx でクローラ時のみ利用）

## sitemap 仕様

- 掲載対象
  - 公開小説（`is_public=true` かつ `status=public`）
  - 公開エピソード（`is_public=true` かつ `status=public`）
  - 作者ページ（公開小説を1件以上持つユーザー）
  - タグページ（公開小説/公開エピソードに紐づくタグ）
  - 固定ページ（`/`, `/?sort=new`, `/authors`, `/tags`）
- 除外対象
  - 下書き、非公開、公開停止相当
  - R18（`novels.age_limit = r18`）
- `lastmod`
  - 小説/エピソード/作者ページで付与

## robots.txt 仕様

- `Allow: /`
- 管理系・認証系・個人領域・不要 API を `Disallow`
- `Sitemap` 行で `https://shosetsu-toukou-site.org/sitemap.xml` を案内

## React 側 SEO メタ

対象ページでページ個別メタを設定:

- 小説詳細 `/novels/:id`
- エピソード詳細 `/episodes/:id`
- 作者ページ `/users/:username`
- タグ一覧/タグ詳細 `/tags`, `/tags/:slug`

設定項目:

- `<title>`
- `<meta name="description">`
- `<link rel="canonical">`
- OGP (`og:title`, `og:description`, `og:url`, `og:type`, `og:image`)
- Twitter Card (`twitter:card`, `twitter:title`, `twitter:description`, `twitter:image`)
- robots (`robots`, `googlebot`, `bingbot`)
- JSON-LD（`Book`, `Article`, `BreadcrumbList`, `Person`）

## 自動 IndexNow 送信

- 新規公開・更新・削除時に backend が `BackgroundTasks` で IndexNow に通知
  - 小説: 作成/更新/削除
  - エピソード: 作成/更新/削除
- `INDEXNOW_ENABLED=1` かつ `INDEXNOW_KEY` 設定時のみ有効
- 送信イベント
  - 公開/更新: `urlUpdated`
  - 非公開化/削除: `urlDeleted`

注意:
- 予約公開（scheduled → public の自動昇格）は現状のSQL一括更新フロー上、即時自動通知の対象外です。
- 必要な場合は `POST /api/admin/indexnow/submit` を併用してください。

## 必要な環境変数

- 既存
  - `FRONTEND_ORIGIN`
  - `SITE_HOST_MAP_JSON`（複数ドメイン運用時）
- IndexNow（任意）
  - `INDEXNOW_ENABLED=1`
  - `INDEXNOW_KEY=<generated-key>`
  - `INDEXNOW_HOST=shosetsu-toukou-site.org`（省略時はリクエストHostを使用）
  - `INDEXNOW_ENDPOINT=https://api.indexnow.org/indexnow`（通常はデフォルトのまま）

## Search Console / Bing 運用フロー

1. 作品やエピソードを公開する
2. `sitemap.xml` が更新対象 URL を含むことを確認
3. Google Search Console
   - サイトマップ提出: `https://shosetsu-toukou-site.org/sitemap.xml`
   - URL 検査で主要 URL を確認し、必要時は再クロールをリクエスト
4. Bing Webmaster Tools
   - サイトマップ提出
   - 速報性を上げたい場合は `POST /api/admin/indexnow/submit` で対象 URL を送信

## IndexNow キー配置

- `INDEXNOW_ENABLED=1` かつ `INDEXNOW_KEY` が設定されている場合、
  `GET /<INDEXNOW_KEY>.txt` がキー文字列を返す。
- Bing 側からキー検証されるため、公開ドメインで到達できることを確認する。

## ローカル確認手順

```bash
# backend 起動後
curl -i http://localhost:8000/sitemap.xml
curl -i http://localhost:8000/sitemap-novels.xml
curl -i http://localhost:8000/robots.txt

# IndexNow (有効時)
curl -i http://localhost:8000/<INDEXNOW_KEY>.txt
```

## 本番反映手順

```bash
# backend 反映
docker compose up --build -d backend

# frontend 反映
cd frontend
npm run build
cd ..
docker compose restart nginx
```
