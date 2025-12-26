import { Link } from "react-router-dom";

export default function SupportReturn({ mode, label = "支援" }) {
  const isSuccess = mode === "success";
  const title = isSuccess ? `${label}が完了しました` : `${label}がキャンセルされました`;
  const message = isSuccess
    ? "ご利用ありがとうございます。反映に数秒〜数分かかる場合があります。"
    : "決済処理は完了しませんでした。もう一度お試しください。";

  return (
    <div style={{ maxWidth: 640, margin: "32px auto", padding: "16px" }}>
      <h2 style={{ marginBottom: 16 }}>{title}</h2>
      <p style={{ marginBottom: 16, lineHeight: 1.6 }}>{message}</p>

      <div style={{ display: "flex", gap: 8 }}>
        <Link to="/" className="btn btn-border">
          トップに戻る
        </Link>
        <Link to="/mypage" className="btn btn-border">
          マイページへ
        </Link>
      </div>
    </div>
  );
}
