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
      </div>
    </div>
  );
}
