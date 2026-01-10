import { Link } from "react-router-dom";
import AuthorBalanceCard from "../components/AuthorBalanceCard.jsx";
import PayoutProfileForm from "../components/PayoutProfileForm.jsx";
import { useI18n } from "../lib/i18n";

export default function CreatorDashboard() {
  const { t } = useI18n();
  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/mypage">
          {t({ ja: "← マイページへ戻る", en: "← Back to My Page" })}
        </Link>
      </div>

      <h2 style={{ marginBottom: 16 }}>
        {t({ ja: "作者ダッシュボード", en: "Creator Dashboard" })}
      </h2>

      <div style={{ display: "grid", gap: 16 }}>
        <AuthorBalanceCard />
        <PayoutProfileForm />
        <section
          style={{
            border: "1px solid #ddd",
            borderRadius: 10,
            padding: 16,
            background: "#fff",
          }}
        >
          <h3 style={{ marginTop: 0 }}>{t({ ja: "支援のマニュアル", en: "Support Guide" })}</h3>
          <ol style={{ lineHeight: 1.7, paddingLeft: 18, marginTop: 8 }}>
            <li>
              {t({
                ja: "支援は Stripe 決済で行われ、支援者が決済完了すると支援額が反映されます。",
                en: "Support payments are processed via Stripe and reflect after payment completes.",
              })}
            </li>
            <li>
              {t({
                ja: "支援の取り分は「支援残高」に加算されます（管理画面の残高カードで確認）。",
                en: "Your share is added to the support balance (see the balance card in the admin area).",
              })}
            </li>
            <li>
              {t({
                ja: "振込を受け取るには「振込設定」を有効にして口座情報を登録してください。",
                en: "Enable payout settings and register your bank account to receive payouts.",
              })}
            </li>
            <li>
              {t({
                ja: "振込は合計 3000 円以上で対象になります。未満の場合は次回に繰り越されます。",
                en: "Payouts are processed when the total reaches 3,000 JPY or more; otherwise they roll over.",
              })}
            </li>
            <li>
              {t({
                ja: "運営側で月次精算を行った後、振込待ちとなり入金処理が進みます。",
                en: "After monthly reconciliation, payouts move to pending and processing starts.",
              })}
            </li>
            <li>
              {t({
                ja: "返金・チャージバックが発生した場合は残高が減算されます。",
                en: "Refunds or chargebacks reduce your balance.",
              })}
            </li>
          </ol>
        </section>
        <section
          style={{
            border: "1px solid #ddd",
            borderRadius: 10,
            padding: 16,
            background: "#fff",
          }}
        >
          <h3 style={{ marginTop: 0 }}>
            {t({ ja: "月額支援プラン", en: "Monthly Support Plans" })}
          </h3>
          <p style={{ marginTop: 8, lineHeight: 1.6 }}>
            {t({
              ja: "月額支援プランの作成・編集・無効化ができます。",
              en: "Create, edit, and disable monthly support plans.",
            })}
          </p>
          <Link className="btn btn-border" to="/me/support-plans">
            {t({ ja: "プラン管理を開く", en: "Open plan management" })}
          </Link>
        </section>
      </div>
    </div>
  );
}
