import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";

type Balance = {
  available_yen?: number | string | null;
  pending_yen?: number | string | null;
};

export default function AuthorBalanceCard() {
  const { t } = useI18n();
  const [balance, setBalance] = useState<Balance | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchBalance = async () => {
    try {
      setLoading(true);
      setError("");
      const data = await apiFetch("/api/authors/me/balance", { auth: true });
      setBalance(data);
    } catch (e) {
      setError(
        getErrorMessage(e, t({ ja: "残高の取得に失敗しました", en: "Failed to load balance." }))
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBalance();
  }, []);

  return (
    <section
      style={{
        border: "1px solid #ddd",
        borderRadius: 10,
        padding: 16,
        background: "#f8fafc",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3 style={{ margin: 0 }}>{t({ ja: "売上残高", en: "Revenue Balance" })}</h3>
        <button type="button" className="btn btn-border" onClick={fetchBalance}>
          {loading ? t({ ja: "更新中...", en: "Refreshing..." }) : t({ ja: "更新", en: "Refresh" })}
        </button>
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {balance && (
        <div style={{ marginTop: 12 }}>
          <p style={{ margin: 0, fontSize: 20, fontWeight: "bold" }}>
            {t(
              { ja: "{{amount}} 円", en: "¥{{amount}}" },
              { amount: Number(balance.available_yen ?? 0).toLocaleString() }
            )}
          </p>
          {Number(balance.pending_yen ?? 0) > 0 && (
            <p style={{ margin: "4px 0", color: "#666" }}>
              {t(
                { ja: "確定待ち: {{amount}} 円", en: "Pending: ¥{{amount}}" },
                { amount: Number(balance.pending_yen ?? 0).toLocaleString() }
              )}
            </p>
          )}
          <p style={{ margin: "8px 0 0", fontSize: 12, color: "#666" }}>
            {t({
              ja: "精算は運営が月次で行います。",
              en: "Payouts are processed monthly by the admin.",
            })}
          </p>
        </div>
      )}
    </section>
  );
}
