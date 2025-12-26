## 目的

読者の「投げ銭 / 月額支援」を Stripe Checkout で受け付け、作者の残高を表示し、運営が精算バッチを管理できるフロント実装を Codex が作業しやすい形でまとめる。

前提:
- フロントは React (Vite 想定)
- API は `/api/...`
- 認証は既存 JWT (Bearer)

---

## 画面/コンポーネント構成 (最小)

### A. 作者/作品ページに「支援」UI

追加先候補:
- `NovelDetail` (小説詳細)
- `UserProfile` (作者ページ)
- `EpisodeDetail` (エピソード詳細)

新コンポーネント:
- `SupportPanel.jsx`

配置方針:
- 作品詳細: 作者名付近 or 本文下 (読了後) にカード表示
- 作者ページ: プロフィール下に固定

### B. 作者マイページに「残高」+「精算設定」

追加先候補:
- `Mypage.jsx`
- または `CreatorDashboard.jsx` 新設

新コンポーネント:
- `AuthorBalanceCard.jsx`
- `PayoutProfileForm.jsx`
- `PayoutHistory.jsx` (最小なら後回し可)

### C. 管理画面に「精算生成/確定」

追加先候補:
- `AdminPage.jsx` (なければ新設)

新コンポーネント:
- `AdminPayouts.jsx`

---

## API 呼び出し仕様 (フロント側)

### 認証ヘッダ

通常ユーザー:
- `Authorization: Bearer <token>`

管理API:
- `X-Admin-Token: <ADMIN_API_KEY>`
- フロントに直書き禁止。`VITE_ADMIN_API_KEY` など運営ローカル環境のみ。

### A. 投げ銭 Checkout

`POST /api/supports/checkout`

body:
```json
{
  "author_user_id": 123,
  "amount_yen": 500,
  "novel_id": 10,
  "episode_id": null,
  "mode": "one_time"
}
```

response:
```json
{ "checkout_url": "https://checkout.stripe.com/..." }
```

フロント挙動:
- 成功時 `window.location.href = checkout_url`
- 失敗時 toast / alert

### B. 月額支援 Checkout

`POST /api/memberships/checkout`

body:
```json
{ "author_user_id": 123, "plan_id": 2 }
```

response:
```json
{ "checkout_url": "https://checkout.stripe.com/..." }
```

### C. 支援プラン取得

バックエンド未実装なら追加が必要:

例:
- `GET /api/support_plans?author_user_id=123`
- または `GET /api/support_plans` (公開プラン一覧)

返却例:
```json
[
  { "id": 1, "name": "月額300", "price_yen": 300, "stripe_price_id": "price_...", "is_active": true },
  { "id": 2, "name": "月額500", "price_yen": 500, "stripe_price_id": "price_...", "is_active": true }
]
```

### D. 作者残高取得

`GET /api/authors/me/balance`

response:
```json
{ "available_yen": 12345, "pending_yen": 0 }
```

### E. 作者精算設定 (銀行口座)

`POST /api/authors/me/payout_profile`

body 例:
```json
{
  "bank_name": "○○銀行",
  "bank_branch": "△△支店",
  "bank_account_type": "ordinary",
  "bank_account_number": "1234567",
  "bank_account_holder": "ウエダ ナオキ"
}
```

### F. 運営: 精算生成

`POST /api/admin/payouts/generate?period=2025-12`

header:
- `X-Admin-Token`

response 例:
```json
{ "count": 5, "total_amount_yen": 123000 }
```

### G. 運営: 支払確定/失敗

`POST /api/admin/payouts/{payout_id}/mark_paid`
`POST /api/admin/payouts/{payout_id}/mark_failed`

body:
```json
{ "note": "振込控えID: XXXX" }
```

---

## UI 詳細 (Codex 向け)

### SupportPanel.jsx (投げ銭 + 月額)

props:
- `authorUserId` (必須)
- `novelId` (任意)
- `episodeId` (任意)
- `authorName` (表示用)

投げ銭 UI:
- 金額プリセット: 100 / 300 / 500 / 1000
- 任意入力: `min=100`, `max=100000`, `step=100`
- 「支援する」ボタン

バリデーション:
- 100 未満はエラー
- 数字以外は弾く

月額 UI:
- プラン一覧ラジオ (name + price_yen)
- 「月額で支援」ボタン

注意表示:
- 「決済は Stripe へ移動します」
- 「反映は数秒〜数分かかる場合があります (Webhook 反映)」

### AuthorBalanceCard.jsx

表示:
- `available_yen` (未払い残高)
- `pending_yen` (不要なら非表示でも可)
- 右上に「更新」ボタン
- 「精算は運営が月次で行います」など一言

### PayoutProfileForm.jsx

入力:
- 銀行名
- 支店
- 口座種別 (普通/当座)
- 口座番号
- 口座名義 (カナ)
- 保存ボタン (成功 toast)

### AdminPayouts.jsx

表示/操作:
- period 入力 (YYYY-MM)
- generate ボタン
- 結果表示 (作成数/合計)
- payout 一覧があれば表示 (最小は生成のみでも可)
- note 入力 + `mark_paid` / `mark_failed`

---

## ルーティング案

- `/support/success`, `/support/cancel` (Stripe return)
- `/me/creator` (作者ダッシュボード)
- `/admin/payouts` (運営管理)

---

## 共通 API ラッパ

`apiFetch(path, { method, body, auth, admin })`
- `auth=true` → Bearer token 付与
- `admin=true` → `X-Admin-Token` 付与 (管理画面のみ)
- JSON/エラー処理を統一

---

## 作者が月額支援額を設定できるようにする方針

### 推奨: 作者ごとの支援プラン方式

作者が複数プラン (例: 300/500/1000) を作成できる。

DB (例):
```
support_plans:
  id
  author_user_id
  name
  price_yen
  stripe_product_id
  stripe_price_id (UNIQUE)
  is_active
  created_at
  updated_at
```

作者向け API (例):
- `GET /api/authors/me/support_plans`
- `POST /api/authors/me/support_plans` body: `{ name, price_yen }`
- `PATCH /api/authors/me/support_plans/{id}` (名称変更 or 価格変更)
- `POST /api/authors/me/support_plans/{id}/deactivate`

Stripe 運用:
- 価格変更は「新しい Price を作って切替」が基本
- 旧 Price は `active=false`

読者の月額 Checkout:
- `plan_id` を送る
- バックエンドで `stripe_price_id` を参照して Checkout 作成

---

## Codex への実装指示 (コピペ用)

React (Vite) で以下を追加/編集:
- `components/SupportPanel.jsx` を新規作成し、作者/作品/エピソードページに埋め込む
- `pages/CreatorDashboard.jsx` を新規作成し、`/me/creator` ルーティング追加
- `AuthorBalanceCard` と `PayoutProfileForm` を表示
- `pages/AdminPayouts.jsx` を新規作成し、`/admin/payouts` にルーティング追加
- `X-Admin-Token` は `import.meta.env.VITE_ADMIN_API_KEY` から読む (運営ローカルのみ設定)
- `lib/api.js` (または既存 API ラッパ) に `apiFetch` を実装し全てここ経由にする
- Checkout API の `checkout_url` を受け取ったら `window.location.href` で遷移

---

## セキュリティ注記 (短く)

- `VITE_ADMIN_API_KEY` を一般公開ビルドに含めないこと
- 管理画面は別ビルド or 内部配布のみ推奨
