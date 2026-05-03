import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, authTokenExists } from "../lib/api";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";

const SUPPORT_PRESETS = [100, 300, 500, 1000];
const MIN_AMOUNT = 100;
const MAX_AMOUNT = 100000;

type SupportPlan = {
  id: number | string;
  name?: string | null;
  price_yen?: number | string | null;
  amount_yen?: number | string | null;
  is_active?: boolean | null;
};

type SupportPanelProps = {
  authorUserId: number | string | null;
  novelId?: number | string | null;
  episodeId?: number | string | null;
  authorName?: string | null;
};

export default function SupportPanel({
  authorUserId,
  novelId = null,
  episodeId = null,
  authorName = null,
}: SupportPanelProps) {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [amount, setAmount] = useState(500);
  const [customAmount, setCustomAmount] = useState("");
  const [supportLoading, setSupportLoading] = useState(false);
  const [membershipLoading, setMembershipLoading] = useState(false);
  const [error, setError] = useState("");
  const [plans, setPlans] = useState<SupportPlan[]>([]);
  const [plansError, setPlansError] = useState("");
  const [selectedPlanId, setSelectedPlanId] = useState<number | string | null>(null);

  const effectiveAmount = useMemo(() => {
    if (customAmount === "") return amount;
    const parsed = Number(customAmount);
    return Number.isFinite(parsed) ? parsed : NaN;
  }, [amount, customAmount]);
  const displayAuthorName = authorName || t({ ja: "作者", en: "Author" });

  useEffect(() => {
    if (!authorUserId) return;
    let mounted = true;

    const fetchPlans = async () => {
      try {
        setPlansError("");
        const data = await apiFetch(`/api/support_plans?author_user_id=${authorUserId}`);
        if (!mounted) return;
        const list = Array.isArray(data) ? data : [];
        const active = list.filter((p: SupportPlan) => p.is_active);
        setPlans(active);
        if (active.length > 0) {
          setSelectedPlanId(active[0].id);
        }
      } catch (e) {
        if (!mounted) return;
        setPlans([]);
        setPlansError(
          getErrorMessage(
            e,
            t({ ja: "月額プランの取得に失敗しました", en: "Failed to load monthly plans." })
          )
        );
      }
    };

    fetchPlans();
    return () => {
      mounted = false;
    };
  }, [authorUserId]);

  const validateAmount = () => {
    if (!Number.isFinite(effectiveAmount)) {
      return t({
        ja: "金額は数字で入力してください",
        en: "Please enter a numeric amount.",
      });
    }
    if (effectiveAmount < MIN_AMOUNT) {
      return t(
        { ja: "金額は{{amount}}円以上で入力してください", en: "Please enter at least {{amount}} JPY." },
        { amount: MIN_AMOUNT }
      );
    }
    if (effectiveAmount > MAX_AMOUNT) {
      return t(
        { ja: "金額は{{amount}}円以下で入力してください", en: "Please enter no more than {{amount}} JPY." },
        { amount: MAX_AMOUNT }
      );
    }
    return "";
  };

  const handleSupport = async () => {
    if (!authorUserId) return;
    const message = validateAmount();
    if (message) {
      setError(message);
      return;
    }

    try {
      setSupportLoading(true);
      setError("");
      const payload = {
        author_user_id: authorUserId,
        amount_yen: Math.round(effectiveAmount),
        novel_id: novelId,
        episode_id: episodeId,
        mode: "one_time",
      };
      const data = await apiFetch("/api/supports/checkout", {
        method: "POST",
        body: payload,
        auth: authTokenExists(),
      });
      if (data?.checkout_url) {
        window.location.href = data.checkout_url;
        return;
      }
      throw new Error(
        t({ ja: "決済URLが取得できませんでした", en: "Could not get the checkout URL." })
      );
    } catch (e) {
      setError(
        getErrorMessage(
          e,
          t({ ja: "支援処理中にエラーが発生しました", en: "An error occurred during support." })
        )
      );
    } finally {
      setSupportLoading(false);
    }
  };

  const handleMembership = async () => {
    if (!authorUserId || !selectedPlanId) {
      setError(t({ ja: "月額プランを選択してください", en: "Please select a monthly plan." }));
      return;
    }
    if (!authTokenExists()) {
      navigate("/login");
      return;
    }

    try {
      setMembershipLoading(true);
      setError("");
      const data = await apiFetch("/api/memberships/checkout", {
        method: "POST",
        body: { author_user_id: authorUserId, plan_id: selectedPlanId },
        auth: true,
      });
      if (data?.checkout_url) {
        window.location.href = data.checkout_url;
        return;
      }
      throw new Error(
        t({ ja: "決済URLが取得できませんでした", en: "Could not get the checkout URL." })
      );
    } catch (e) {
      setError(
        getErrorMessage(
          e,
          t({ ja: "支援処理中にエラーが発生しました", en: "An error occurred during support." })
        )
      );
    } finally {
      setMembershipLoading(false);
    }
  };

  return (
    <section
      style={{
        margin: "16px 0",
        padding: "16px",
        borderRadius: 12,
        border: "1px solid var(--border)",
        background: "var(--surface-2)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
      }}
    >
      <h3 style={{ marginTop: 0, marginBottom: 12 }}>
        {t({ ja: "{{name}} さんを支援する", en: "Support {{name}}" }, { name: displayAuthorName })}
      </h3>

      {error && (
        <p style={{ color: "red", marginTop: 0, marginBottom: 8 }}>{error}</p>
      )}

      <div style={{ display: "grid", gap: 12 }}>
        <div>
          <div style={{ fontWeight: "bold", marginBottom: 6 }}>
            {t({ ja: "投げ銭 (単発)", en: "Tip (one-time)" })}
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {SUPPORT_PRESETS.map((preset) => (
              <button
                key={preset}
                type="button"
                className="btn btn-border"
              onClick={() => {
                setAmount(preset);
                setCustomAmount("");
              }}
            >
              {t({ ja: "{{amount}}円", en: "¥{{amount}}" }, { amount: preset })}
            </button>
            ))}
          </div>

          <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
            <label htmlFor="support-amount">
              {t({ ja: "任意金額", en: "Custom amount" })}
            </label>
            <input
              id="support-amount"
              type="number"
              min={MIN_AMOUNT}
              max={MAX_AMOUNT}
              step={100}
              value={customAmount}
              placeholder={`${amount}`}
              onChange={(e) => setCustomAmount(e.target.value)}
              style={{ width: 140 }}
            />
            <span>{t({ ja: "円", en: "JPY" })}</span>
          </div>

          <button
            type="button"
            className="btn btn-border"
            onClick={handleSupport}
            disabled={supportLoading}
            style={{ marginTop: 8 }}
          >
            {supportLoading ? t({ ja: "処理中...", en: "Processing..." }) : t({ ja: "支援する", en: "Support" })}
          </button>
        </div>

        <div>
          <div style={{ fontWeight: "bold", marginBottom: 6 }}>
            {t({ ja: "月額支援", en: "Monthly support" })}
          </div>
          {plansError && (
            <p style={{ color: "red", marginTop: 0, marginBottom: 8 }}>{plansError}</p>
          )}
          {plans.length === 0 ? (
            <p style={{ marginTop: 0, color: "var(--muted-text)" }}>
              {t({ ja: "月額プランがありません。", en: "No monthly plans available." })}
            </p>
          ) : (
            <div style={{ display: "grid", gap: 6 }}>
              {plans.map((plan) => (
                <label
                  key={plan.id}
                  style={{
                    display: "flex",
                    gap: 8,
                    alignItems: "center",
                    padding: "6px 8px",
                    borderRadius: 6,
                    border: "1px solid var(--border)",
                    background: "var(--surface)",
                  }}
                >
                  <input
                    type="radio"
                    name={`support-plan-${authorUserId}`}
                    value={plan.id}
                    checked={selectedPlanId === plan.id}
                    onChange={() => setSelectedPlanId(plan.id)}
                  />
                  <span>
                    {plan.name} /{" "}
                    {t(
                      { ja: "{{amount}}円", en: "¥{{amount}}" },
                      { amount: plan.price_yen ?? plan.amount_yen ?? "" }
                    )}
                  </span>
                </label>
              ))}
            </div>
          )}

          <button
            type="button"
            className="btn btn-border"
            onClick={handleMembership}
            disabled={membershipLoading || plans.length === 0}
            style={{ marginTop: 8 }}
          >
            {membershipLoading
              ? t({ ja: "処理中...", en: "Processing..." })
              : t({ ja: "月額で支援", en: "Support monthly" })}
          </button>
        </div>
      </div>

      <div style={{ marginTop: 12, fontSize: 12, color: "var(--muted-text)" }}>
        <p style={{ margin: 0 }}>
          {t({ ja: "決済は Stripe に移動します。", en: "Payment is handled on Stripe." })}
        </p>
        <p style={{ margin: 0 }}>
          {t({
            ja: "支援の反映は数秒〜数分かかる場合があります (Webhook 反映)。",
            en: "Support may take a few seconds to a few minutes to reflect (via webhook).",
          })}
        </p>
      </div>
    </section>
  );
}
