from pathlib import Path

path = Path("frontend/src/pages/StripeReturn.jsx")

code = r'''import { Link } from "react-router-dom";

/**
 * Stripe 決済結果表示ページ
 *
 * App.jsx で
 *   <Route path="/stripe/success" element={<StripeReturn mode="success" />} />
 *   <Route path="/stripe/cancel"  element={<StripeReturn mode="cancel"  />} />
 * のように使う前提。
 */
export default function StripeReturn({ mode }) {
  const isSuccess = mode === "success";
  const title = isSuccess ? "課金が完了しました" : "決済がキャンセルされました";
  const message = isSuccess
    ? "ご利用ありがとうございます。プレミアム会員への反映に数秒〜数十秒かかる場合があります。マイページでステータスをご確認ください。"
    : "決済処理は完了しませんでした。もう一度お試しになる場合は、マイページから再度お申し込みください。";

  return (
    <div style={{ maxWidth: 640, margin: "32px auto", padding: "16px" }}>
      <h2 style={{ marginBottom: 16 }}>{title}</h2>
      <p style={{ marginBottom: 16, lineHeight: 1.6 }}>{message}</p>

      {isSuccess && (
        <div
          style={{
            marginBottom: 24,
            padding: 12,
            borderRadius: 8,
            backgroundColor: "#f0fff4",
            border: "1px solid #c6f6d5",
            fontSize: 14,
          }}
        >
          <p style={{ margin: 0 }}>
            ※ もし数分待ってもプレミアムにならない場合は、
            ログアウト・ログインをお試しのうえ、
            それでも反映されないときはお問い合わせください。
          </p>
        </div>
      )}

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
'''

path.write_text(code, encoding="utf-8")
print("✅ frontend/src/pages/StripeReturn.jsx を課金完了ページ対応で上書きしました")
