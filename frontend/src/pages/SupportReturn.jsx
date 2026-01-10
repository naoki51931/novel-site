import { Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";

export default function SupportReturn({ mode, label = "支援" }) {
  const { t } = useI18n();
  const isSuccess = mode === "success";
  const title = isSuccess
    ? t({ ja: "{{label}}が完了しました", en: "{{label}} completed" }, { label })
    : t({ ja: "{{label}}がキャンセルされました", en: "{{label}} canceled" }, { label });
  const message = isSuccess
    ? t({
        ja: "ご利用ありがとうございます。反映に数秒〜数分かかる場合があります。",
        en: "Thank you. It may take a few seconds to a few minutes to reflect.",
      })
    : t({
        ja: "決済処理は完了しませんでした。もう一度お試しください。",
        en: "Payment was not completed. Please try again.",
      });

  return (
    <div style={{ maxWidth: 640, margin: "32px auto", padding: "16px" }}>
      <h2 style={{ marginBottom: 16 }}>{title}</h2>
      <p style={{ marginBottom: 16, lineHeight: 1.6 }}>{message}</p>

      <div style={{ display: "flex", gap: 8 }}>
        <Link to="/" className="btn btn-border">
          {t({ ja: "トップに戻る", en: "Back to Home" })}
        </Link>
        <Link to="/mypage" className="btn btn-border">
          {t({ ja: "マイページへ", en: "Go to My Page" })}
        </Link>
      </div>
    </div>
  );
}
