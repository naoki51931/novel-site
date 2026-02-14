import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useI18n } from "../lib/i18n";

function getStoredAuthToken() {
  if (typeof window === "undefined") return "";
  const access = String(localStorage.getItem("access_token") || "").trim();
  const token = String(localStorage.getItem("token") || "").trim();
  return access || token;
}

export default function PremiumLP() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isPremium, setIsPremium] = useState(false);
  const [statusLoading, setStatusLoading] = useState(true);

  useEffect(() => {
    const token = getStoredAuthToken();
    if (!token) {
      setStatusLoading(false);
      setIsPremium(false);
      return;
    }

    const load = async () => {
      try {
        const res = await fetch("/api/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          setIsPremium(false);
          return;
        }
        const data = await res.json().catch(() => ({}));
        setIsPremium(!!data?.is_premium);
      } finally {
        setStatusLoading(false);
      }
    };

    load();
  }, []);

  const yearlyHint = useMemo(() => {
    const monthly = 1000;
    const yearly = monthly * 12;
    return t(
      { ja: "月{{monthly}}円（年{{yearly}}円）", en: "¥{{monthly}}/month (¥{{yearly}}/year)" },
      { monthly: monthly.toLocaleString(), yearly: yearly.toLocaleString() }
    );
  }, [t]);

  const startCheckout = async () => {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      const token = getStoredAuthToken();
      if (!token) {
        navigate("/login");
        return;
      }
      const res = await fetch("/api/stripe/create-checkout-session", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        navigate("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(
          String(data?.detail || t({ ja: "決済セッションの作成に失敗しました。", en: "Failed to create checkout session." }))
        );
      }
      const url = String(data?.url || "").trim();
      if (!url) {
        throw new Error(t({ ja: "決済URLが取得できませんでした。", en: "Could not get checkout URL." }));
      }
      window.location.href = url;
    } catch (e) {
      setError(e?.message || t({ ja: "決済開始に失敗しました。", en: "Failed to start checkout." }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 980, margin: "0 auto", padding: "20px 8px 40px" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">{t({ ja: "← トップに戻る", en: "← Back to Home" })}</Link>
      </div>

      <section
        style={{
          borderRadius: 16,
          border: "1px solid #d4c198",
          padding: "26px 22px",
          background: "linear-gradient(135deg, #f7edd6 0%, #f9f3e2 45%, #fffdfa 100%)",
          boxShadow: "0 12px 28px rgba(47, 30, 7, 0.08)",
          marginBottom: 16,
        }}
      >
        <div style={{ display: "inline-block", padding: "4px 10px", borderRadius: 999, background: "#2d2010", color: "#fff", fontSize: 12, fontWeight: 700 }}>
          {t({ ja: "PREMIUM", en: "PREMIUM" })}
        </div>
        <h2 className="premium-lp-title" style={{ margin: "12px 0 8px", fontSize: "clamp(1.5rem, 3vw, 2.2rem)", lineHeight: 1.25 }}>
          {t({ ja: "創作を止めないためのプレミアム", en: "Premium to keep your creativity moving" })}
        </h2>
        <p style={{ margin: "0 0 14px", color: "#473a23", lineHeight: 1.7 }}>
          {t({
            ja: "AI生成回数の上限拡張や全文閲覧など、毎日の執筆と読書を加速させる機能をまとめて利用できます。",
            en: "Get bundled features like higher AI limits and full-text access to speed up your daily writing and reading.",
          })}
        </p>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 10,
            marginBottom: 14,
          }}
        >
          <div style={{ border: "1px solid #d4c198", borderRadius: 10, padding: "10px 12px", background: "rgba(255,255,255,0.7)" }}>
            <div style={{ fontSize: 12, color: "#5d5039" }}>{t({ ja: "AI小説生成", en: "AI novel generation" })}</div>
            <strong>{t({ ja: "1日80回まで", en: "Up to 80 times/day" })}</strong>
          </div>
          <div style={{ border: "1px solid #d4c198", borderRadius: 10, padding: "10px 12px", background: "rgba(255,255,255,0.7)" }}>
            <div style={{ fontSize: 12, color: "#5d5039" }}>{t({ ja: "エピソード閲覧", en: "Episode access" })}</div>
            <strong>{t({ ja: "長文の全文表示", en: "Full long-text view" })}</strong>
          </div>
          <div style={{ border: "1px solid #d4c198", borderRadius: 10, padding: "10px 12px", background: "rgba(255,255,255,0.7)" }}>
            <div style={{ fontSize: 12, color: "#5d5039" }}>{t({ ja: "決済", en: "Billing" })}</div>
            <strong>Stripe / {yearlyHint}</strong>
          </div>
        </div>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <button
            type="button"
            className="btn btn-border"
            onClick={startCheckout}
            disabled={loading || isPremium}
            style={{ borderRadius: 8, borderColor: "#2d2010" }}
          >
            {isPremium
              ? t({ ja: "現在プレミアム会員です", en: "You are Premium" })
              : loading
                ? t({ ja: "決済ページを準備中...", en: "Preparing checkout..." })
                : t({ ja: "プレミアム会員になる", en: "Become Premium" })}
          </button>
          <Link to="/mypage" className="btn btn-border" style={{ borderRadius: 8 }}>
            {t({ ja: "マイページで状態確認", en: "Check status on My Page" })}
          </Link>
          {!statusLoading && !isPremium && (
            <span style={{ fontSize: 12, color: "#5d5039" }}>
              {t({ ja: "いつでもStripe側で解約可能です。", en: "You can cancel anytime via Stripe." })}
            </span>
          )}
        </div>
        {error && <p style={{ margin: "10px 0 0", color: "crimson" }}>{error}</p>}
      </section>

      <section style={{ border: "1px solid var(--border)", borderRadius: 12, padding: "14px 14px 6px", background: "var(--surface)" }}>
        <h3 style={{ marginTop: 0 }}>{t({ ja: "よくある質問", en: "FAQ" })}</h3>
        <div style={{ display: "grid", gap: 12 }}>
          <div>
            <strong>{t({ ja: "課金後いつ反映されますか？", en: "When does Premium activate?" })}</strong>
            <p style={{ margin: "4px 0 0", color: "var(--muted-text)" }}>
              {t({
                ja: "通常は数秒〜数十秒で反映されます。反映が遅い場合はマイページを再読み込みしてください。",
                en: "Usually within seconds. If delayed, reload My Page.",
              })}
            </p>
          </div>
          <div>
            <strong>{t({ ja: "どこから解約できますか？", en: "How can I cancel?" })}</strong>
            <p style={{ margin: "4px 0 0", color: "var(--muted-text)" }}>
              {t({
                ja: "Stripeの管理画面から解約できます。操作に困った場合はお問い合わせからご連絡ください。",
                en: "You can cancel from Stripe. If you need help, contact support.",
              })}
            </p>
          </div>
          <div>
            <strong>{t({ ja: "決済に失敗した場合は？", en: "What if payment fails?" })}</strong>
            <p style={{ margin: "4px 0 0", color: "var(--muted-text)" }}>
              {t({
                ja: "カード情報を確認して再度お試しください。繰り返し失敗する場合は別カードまたは時間を置いて再実行してください。",
                en: "Check card details and retry. If it keeps failing, try another card or retry later.",
              })}
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
