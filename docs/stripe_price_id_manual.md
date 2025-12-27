## stripe_price_id 追加マニュアル

目的: 作者が月額支援プランを作る際に必要な `stripe_price_id` を Stripe で発行し、管理画面に登録する。

---

## 1. Stripe ダッシュボードで Price を作成

1) Stripe にログイン
2) 左メニューの「商品」(Products) を開く
3) 「商品を追加」(Add product) をクリック
4) 商品名を入力 (例: `作者名 支援プラン`)
5) 価格設定で以下を選択
   - 価格タイプ: 定期 (Recurring)
   - 間隔: 月 (Monthly)
   - 通貨: JPY
   - 金額: 300 / 500 / 1000 など
6) 保存

保存後、Price の詳細画面に `price_...` 形式の ID が表示される。
これが `stripe_price_id`。

---

## 2. サイト側でプラン登録

1) 作者でログイン
2) `/me/support-plans` を開く
3) 「stripe_price_id」欄に `price_...` を貼り付け
4) 金額とプラン名を入力して作成

---

## 3. 注意点

- `stripe_price_id` は公開可能な ID だが、価格や商品に紐づくので誤入力に注意
- 価格を変えたい場合は Stripe で新しい Price を作り、既存プランを更新する
- 同一作者で同額の active プランは作れない (重複防止)
