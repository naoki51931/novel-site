import { Link } from "react-router-dom";
import AuthorBalanceCard from "../components/AuthorBalanceCard.jsx";
import PayoutProfileForm from "../components/PayoutProfileForm.jsx";

export default function CreatorDashboard() {
  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/mypage">← マイページへ戻る</Link>
      </div>

      <h2 style={{ marginBottom: 16 }}>作者ダッシュボード</h2>

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
          <h3 style={{ marginTop: 0 }}>支援のマニュアル</h3>
          <ol style={{ lineHeight: 1.7, paddingLeft: 18, marginTop: 8 }}>
            <li>
              支援は Stripe 決済で行われ、支援者が決済完了すると支援額が反映されます。
            </li>
            <li>
              支援の取り分は「支援残高」に加算されます（管理画面の残高カードで確認）。
            </li>
            <li>
              振込を受け取るには「振込設定」を有効にして口座情報を登録してください。
            </li>
            <li>
              振込は合計 3000 円以上で対象になります。未満の場合は次回に繰り越されます。
            </li>
            <li>
              運営側で月次精算を行った後、振込待ちとなり入金処理が進みます。
            </li>
            <li>
              返金・チャージバックが発生した場合は残高が減算されます。
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
          <h3 style={{ marginTop: 0 }}>月額支援プラン</h3>
          <p style={{ marginTop: 8, lineHeight: 1.6 }}>
            月額支援プランの作成・編集・無効化ができます。
          </p>
          <Link className="btn btn-border" to="/me/support-plans">
            プラン管理を開く
          </Link>
        </section>
      </div>
    </div>
  );
}
