import { Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";

export default function StripePriceIdManual() {
  const { t } = useI18n();
  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/me/support-plans">
          {t({ ja: "← 月額支援プラン管理へ戻る", en: "← Back to Monthly Plans" })}
        </Link>
      </div>

      <h2 style={{ marginBottom: 16 }}>
        {t({ ja: "stripe_price_id 追加マニュアル", en: "stripe_price_id Setup Guide" })}
      </h2>

      <p style={{ lineHeight: 1.6 }}>
        {t({
          ja: "目的: 作者が月額支援プランを作る際に必要な stripe_price_id を Stripe で発行し、管理画面に登録します。",
          en: "Goal: Issue a stripe_price_id in Stripe for monthly support plans and register it in the admin UI.",
        })}
      </p>

      <h3>{t({ ja: "1. Stripe ダッシュボードで Price を作成", en: "1. Create a Price in Stripe Dashboard" })}</h3>
      <ol style={{ lineHeight: 1.8 }}>
        <li>{t({ ja: "Stripe にログイン", en: "Log in to Stripe" })}</li>
        <li>{t({ ja: "左メニューの「商品」(Products) を開く", en: "Open Products in the left menu" })}</li>
        <li>{t({ ja: "「商品を追加」(Add product) をクリック", en: "Click Add product" })}</li>
        <li>{t({ ja: "商品名を入力 (例: 作者名 支援プラン)", en: "Enter a product name (e.g., Author Name Support Plan)" })}</li>
        <li>
          {t({ ja: "価格設定で以下を選択:", en: "In pricing, choose:" })}
          <ul style={{ marginTop: 6 }}>
            <li>{t({ ja: "価格タイプ: 定期 (Recurring)", en: "Price type: Recurring" })}</li>
            <li>{t({ ja: "間隔: 月 (Monthly)", en: "Interval: Monthly" })}</li>
            <li>{t({ ja: "通貨: JPY", en: "Currency: JPY" })}</li>
            <li>{t({ ja: "金額: 300 / 500 / 1000 など", en: "Amount: 300 / 500 / 1000, etc." })}</li>
          </ul>
        </li>
        <li>{t({ ja: "保存", en: "Save" })}</li>
      </ol>

      <p style={{ lineHeight: 1.6 }}>
        {t({
          ja: "保存後、Price の詳細画面に price_... 形式の ID が表示されます。これが stripe_price_id です。",
          en: "After saving, the Price detail page shows an ID like price_.... This is the stripe_price_id.",
        })}
      </p>

      <h3>{t({ ja: "2. サイト側でプラン登録", en: "2. Register the plan on the site" })}</h3>
      <ol style={{ lineHeight: 1.8 }}>
        <li>{t({ ja: "作者でログイン", en: "Log in as the author" })}</li>
        <li>{t({ ja: "/me/support-plans を開く", en: "Open /me/support-plans" })}</li>
        <li>{t({ ja: "stripe_price_id 欄に price_... を貼り付け", en: "Paste price_... into stripe_price_id" })}</li>
        <li>{t({ ja: "金額とプラン名を入力して作成", en: "Enter amount and plan name, then create" })}</li>
      </ol>

      <h3>{t({ ja: "3. 注意点", en: "3. Notes" })}</h3>
      <ul style={{ lineHeight: 1.8 }}>
        <li>{t({ ja: "stripe_price_id は公開可能な ID だが、誤入力に注意", en: "stripe_price_id is public but be careful about typos" })}</li>
        <li>{t({ ja: "価格変更は Stripe で新しい Price を作成し、プランを更新", en: "For price changes, create a new Price in Stripe and update the plan" })}</li>
        <li>{t({ ja: "同一作者で同額の active プランは作れない", en: "An author cannot have multiple active plans with the same price" })}</li>
      </ul>
    </div>
  );
}
