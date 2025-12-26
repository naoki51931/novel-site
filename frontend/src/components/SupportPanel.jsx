import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, authTokenExists } from "../lib/api";

const SUPPORT_PRESETS = [100, 300, 500, 1000];
const MIN_AMOUNT = 100;
const MAX_AMOUNT = 100000;

export default function SupportPanel({
  authorUserId,
  novelId = null,
  episodeId = null,
  authorName = "作者",
}) {
  const navigate = useNavigate();
  const [amount, setAmount] = useState(500);
  const [customAmount, setCustomAmount] = useState("");
  const [supportLoading, setSupportLoading] = useState(false);
  const [membershipLoading, setMembershipLoading] = useState(false);
  const [error, setError] = useState("");
  const [plans, setPlans] = useState([]);
  const [plansError, setPlansError] = useState("");
  const [selectedPlanId, setSelectedPlanId] = useState(null);

  const effectiveAmount = useMemo(() => {
    if (customAmount === "") return amount;
    const parsed = Number(customAmount);
    return Number.isFinite(parsed) ? parsed : NaN;
  }, [amount, customAmount]);

  useEffect(() => {
    if (!authorUserId) return;
    let mounted = true;

    const fetchPlans = async () => {
      try {
        setPlansError("");
        const data = await apiFetch(`/api/support_plans?author_user_id=${authorUserId}`);
        if (!mounted) return;
        const list = Array.isArray(data) ? data : [];
        const active = list.filter((p) => p.is_active);
        setPlans(active);
        if (active.length > 0) {
          setSelectedPlanId(active[0].id);
        }
      } catch (e) {
        if (!mounted) return;
        setPlans([]);
        setPlansError(e.message || "月額プランの取得に失敗しました");
      }
    };

    fetchPlans();
    return () => {
      mounted = false;
    };
  }, [authorUserId]);

  const validateAmount = () => {
    if (!Number.isFinite(effectiveAmount)) {
      return "金額は数字で入力してください";
    }
    if (effectiveAmount < MIN_AMOUNT) {
      return `金額は${MIN_AMOUNT}円以上で入力してください`;
    }
    if (effectiveAmount > MAX_AMOUNT) {
      return `金額は${MAX_AMOUNT}円以下で入力してください`;
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
      throw new Error("決済URLが取得できませんでした");
    } catch (e) {
      setError(e.message || "支援処理中にエラーが発生しました");
    } finally {
      setSupportLoading(false);
    }
  };

  const handleMembership = async () => {
    if (!authorUserId || !selectedPlanId) {
      setError("月額プランを選択してください");
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
      throw new Error("決済URLが取得できませんでした");
    } catch (e) {
      setError(e.message || "支援処理中にエラーが発生しました");
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
        border: "1px solid #ddd",
        background: "#fffdf7",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
      }}
    >
      <h3 style={{ marginTop: 0, marginBottom: 12 }}>
        {authorName} さんを支援する
      </h3>

      {error && (
        <p style={{ color: "red", marginTop: 0, marginBottom: 8 }}>{error}</p>
      )}

      <div style={{ display: "grid", gap: 12 }}>
        <div>
          <div style={{ fontWeight: "bold", marginBottom: 6 }}>投げ銭 (単発)</div>
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
                {preset}円
              </button>
            ))}
          </div>

          <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
            <label htmlFor="support-amount">任意金額</label>
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
            <span>円</span>
          </div>

          <button
            type="button"
            className="btn btn-border"
            onClick={handleSupport}
            disabled={supportLoading}
            style={{ marginTop: 8 }}
          >
            {supportLoading ? "処理中..." : "支援する"}
          </button>
        </div>

        <div>
          <div style={{ fontWeight: "bold", marginBottom: 6 }}>月額支援</div>
          {plansError && (
            <p style={{ color: "red", marginTop: 0, marginBottom: 8 }}>{plansError}</p>
          )}
          {plans.length === 0 ? (
            <p style={{ marginTop: 0, color: "#666" }}>月額プランがありません。</p>
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
                    border: "1px solid #ddd",
                    background: "#fff",
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
                    {plan.name} / {plan.price_yen ?? plan.amount_yen ?? ""}円
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
            {membershipLoading ? "処理中..." : "月額で支援"}
          </button>
        </div>
      </div>

      <div style={{ marginTop: 12, fontSize: 12, color: "#666" }}>
        <p style={{ margin: 0 }}>決済は Stripe に移動します。</p>
        <p style={{ margin: 0 }}>
          支援の反映は数秒〜数分かかる場合があります (Webhook 反映)。
        </p>
      </div>
    </section>
  );
}
