import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getErrorMessage } from "../lib/errorUtils";
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
  const [selectedAmount, setSelectedAmount] = useState(1000);
  const [moonToken, setMoonToken] = useState("");
  const [tokenLoading, setTokenLoading] = useState(false);

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

  const plans = [
    { amount: 1000, label: "¥1,000", name: t({ ja: "月額1000円プラン", en: "¥1,000/month plan" }), moon: false },
    { amount: 3000, label: "¥3,000", name: t({ ja: "月額3000円プラン", en: "¥3,000/month plan" }), moon: true },
    { amount: 5000, label: "¥5,000", name: t({ ja: "月額5000円プラン", en: "¥5,000/month plan" }), moon: true },
  ];
  const selectedPlanMultiplier = selectedAmount >= 5000 ? 6 : selectedAmount >= 3000 ? 3.5 : 1;
  const aiNovelDailyLimit = Math.floor(80 * selectedPlanMultiplier);
  const aiChatTokenLimit = Math.floor(4_000_000 * selectedPlanMultiplier);


  const issueMoonToken = async () => {
    if (tokenLoading) return;
    setTokenLoading(true);
    setError("");
    try {
      const token = getStoredAuthToken();
      if (!token) {
        navigate("/login");
        return;
      }
      const res = await fetch("/api/external/moon-arcana/token", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        navigate("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(String(data?.detail || t({ ja: "トークン発行に失敗しました。", en: "Failed to issue token." })));
      }
      setMoonToken(String(data?.token || ""));
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "トークン発行に失敗しました。", en: "Failed to issue token." })));
    } finally {
      setTokenLoading(false);
    }
  };

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
      const meRes = await fetch("/api/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (meRes.ok) {
        const meData = await meRes.json().catch(() => ({}));
        if (meData?.is_premium) {
          setIsPremium(true);
          throw new Error(t({ ja: "すでにプレミアム会員です。", en: "You are already Premium." }));
        }
      }
      const res = await fetch("/api/stripe/create-checkout-session", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ amount_yen: selectedAmount }),
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
      setError(getErrorMessage(e, t({ ja: "決済開始に失敗しました。", en: "Failed to start checkout." })));
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
            ja: "従来の1000円プランに加えて、3000円プランと5000円プランでは moon-arcana.com の全機能を使えるトークンを発行できます。",
            en: "The existing ¥1,000 plan remains available, and the ¥3,000 and ¥5,000 plans issue a token for full access to moon-arcana.com.",
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
            <strong>{t({ ja: `1日${aiNovelDailyLimit.toLocaleString()}回まで`, en: `Up to ${aiNovelDailyLimit.toLocaleString()} times/day` })}</strong>
          </div>
          <div style={{ border: "1px solid #d4c198", borderRadius: 10, padding: "10px 12px", background: "rgba(255,255,255,0.7)" }}>
            <div style={{ fontSize: 12, color: "#5d5039" }}>{t({ ja: "AIチャット", en: "AI chat" })}</div>
            <strong>{t({ ja: `月${aiChatTokenLimit.toLocaleString()}トークン`, en: `${aiChatTokenLimit.toLocaleString()} tokens/month` })}</strong>
          </div>
          <div style={{ border: "1px solid #d4c198", borderRadius: 10, padding: "10px 12px", background: "rgba(255,255,255,0.7)" }}>
            <div style={{ fontSize: 12, color: "#5d5039" }}>{t({ ja: "エピソード閲覧", en: "Episode access" })}</div>
            <strong>{t({ ja: "長文の全文表示", en: "Full long-text view" })}</strong>
          </div>
          <div style={{ border: "1px solid #d4c198", borderRadius: 10, padding: "10px 12px", background: "rgba(255,255,255,0.7)" }}>
            <div style={{ fontSize: 12, color: "#5d5039" }}>{t({ ja: "外部サイト連携", en: "External access" })}</div>
            <strong>{t({ ja: "外部サイトの全機能", en: "Full external-site access" })}</strong>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 10, marginBottom: 14 }}>
          {plans.map((plan) => {
            const active = selectedAmount === plan.amount;
            const isSelectionLocked = loading;
            return (
              <button
                key={plan.amount}
                type="button"
                onClick={() => setSelectedAmount(plan.amount)}
                disabled={isSelectionLocked}
                style={{
                  textAlign: "left",
                  border: active ? "2px solid #2d2010" : "1px solid #d4c198",
                  borderRadius: 8,
                  padding: "12px",
                  background: active ? "#fff7e8" : "rgba(255,255,255,0.72)",
                  cursor: isSelectionLocked ? "default" : "pointer",
                }}
              >
                <div style={{ fontWeight: 800, fontSize: 18 }}>{plan.label}</div>
                <div style={{ fontSize: 13, color: "#5d5039" }}>{plan.name}</div>
                <div style={{ fontSize: 12, color: "#5d5039", marginTop: 4 }}>
                  {plan.moon ? t({ ja: "連携トークン対象", en: "Includes linked-site token" }) : t({ ja: "従来プレミアム", en: "Standard Premium" })}
                </div>
              </button>
            );
          })}
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
                : t({ ja: `${selectedAmount.toLocaleString()}円プランで登録`, en: `Subscribe to ¥${selectedAmount.toLocaleString()}` })}
          </button>
          <Link to="/mypage" className="btn btn-border" style={{ borderRadius: 8 }}>
            {t({ ja: "マイページで状態確認", en: "Check status on My Page" })}
          </Link>
          {!statusLoading && !isPremium && (
            <span style={{ fontSize: 12, color: "#5d5039" }}>
              {t({ ja: "いつでもStripe側で解約可能です。", en: "You can cancel anytime via Stripe." })}
            </span>
          )}
          {isPremium && (
            <button type="button" className="btn btn-border" onClick={issueMoonToken} disabled={tokenLoading} style={{ borderRadius: 8 }}>
              {tokenLoading ? t({ ja: "発行中...", en: "Issuing..." }) : t({ ja: "moon-arcana.com用トークンを発行", en: "Issue moon-arcana.com token" })}
            </button>
          )}
          <a href="https://moon-arcana.com" className="btn btn-border" target="_blank" rel="noopener noreferrer" style={{ borderRadius: 8 }}>
            {t({ ja: "moon-arcana.comへ移動", en: "Go to moon-arcana.com" })}
          </a>
        </div>
        {moonToken && (
          <div style={{ marginTop: 10 }}>
            <label style={{ display: "block", fontSize: 12, color: "#5d5039", marginBottom: 4 }}>
              {t({ ja: "moon-arcana.com用トークン", en: "moon-arcana.com token" })}
            </label>
            <input readOnly value={moonToken} style={{ width: "100%", boxSizing: "border-box", fontFamily: "monospace" }} />
          </div>
        )}
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
                ja: "Stripeの管理画面から解約できます。解約後は moon-arcana.com 用トークンも利用不可になります。",
                en: "You can cancel from Stripe. After cancellation, the moon-arcana.com token becomes unusable.",
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
