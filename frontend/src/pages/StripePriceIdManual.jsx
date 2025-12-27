import { Link } from "react-router-dom";

export default function StripePriceIdManual() {
  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/me/support-plans">← 月額支援プラン管理へ戻る</Link>
      </div>

      <h2 style={{ marginBottom: 16 }}>stripe_price_id 追加マニュアル</h2>

      <p style={{ lineHeight: 1.6 }}>
        目的: 作者が月額支援プランを作る際に必要な stripe_price_id を Stripe で発行し、
        管理画面に登録します。
      </p>

      <h3>1. Stripe ダッシュボードで Price を作成</h3>
      <ol style={{ lineHeight: 1.8 }}>
        <li>Stripe にログイン</li>
        <li>左メニューの「商品」(Products) を開く</li>
        <li>「商品を追加」(Add product) をクリック</li>
        <li>商品名を入力 (例: 作者名 支援プラン)</li>
        <li>
          価格設定で以下を選択:
          <ul style={{ marginTop: 6 }}>
            <li>価格タイプ: 定期 (Recurring)</li>
            <li>間隔: 月 (Monthly)</li>
            <li>通貨: JPY</li>
            <li>金額: 300 / 500 / 1000 など</li>
          </ul>
        </li>
        <li>保存</li>
      </ol>

      <p style={{ lineHeight: 1.6 }}>
        保存後、Price の詳細画面に price_... 形式の ID が表示されます。これが
        stripe_price_id です。
      </p>

      <h3>2. サイト側でプラン登録</h3>
      <ol style={{ lineHeight: 1.8 }}>
        <li>作者でログイン</li>
        <li>/me/support-plans を開く</li>
        <li>stripe_price_id 欄に price_... を貼り付け</li>
        <li>金額とプラン名を入力して作成</li>
      </ol>

      <h3>3. 注意点</h3>
      <ul style={{ lineHeight: 1.8 }}>
        <li>stripe_price_id は公開可能な ID だが、誤入力に注意</li>
        <li>価格変更は Stripe で新しい Price を作成し、プランを更新</li>
        <li>同一作者で同額の active プランは作れない</li>
      </ul>
    </div>
  );
}
