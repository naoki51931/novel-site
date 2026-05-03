import { Link } from "react-router-dom";
import { useEffect } from "react";
import { useI18n } from "../lib/i18n";

export default function StripeReturn({ mode }: { mode: "success" | "cancel" }) {
  const { t } = useI18n();
  const isSuccess = mode === "success";

  useEffect(() => {
    if (!isSuccess) return;

    if (typeof window !== "undefined" && window.gtag) {
      window.gtag("event", "conversion", {
        send_to: "AW-781963249/Y5UkCJugivEbEPGf7_QC",
        value: 1000.0,
        currency: "JPY",
        transaction_id: "",
      });
    }
  }, [isSuccess]);

  const title = isSuccess
    ? t({ ja: "課金が完了しました", en: "Payment completed" })
    : t({ ja: "決済がキャンセルされました", en: "Payment canceled" });

  const message = isSuccess
    ? t({
        ja: "ご利用ありがとうございます。プレミアム会員への反映に数秒〜数十秒かかる場合があります。マイページでステータスをご確認ください。",
        en: "Thanks for your support. Premium status may take a few seconds to reflect. Check My Page for status.",
      })
    : t({
        ja: "決済処理は完了しませんでした。もう一度お試しになる場合は、マイページから再度お申し込みください。",
        en: "Payment was not completed. If you want to try again, please apply from My Page.",
      });

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
            {t({
              ja: "※ もし数分待ってもプレミアムにならない場合は、ログアウト・ログインをお試しのうえ、それでも反映されないときはお問い合わせください。",
              en: "If premium doesn't update after a few minutes, try logging out/in. If it still doesn't update, contact support.",
            })}
          </p>
        </div>
      )}

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
