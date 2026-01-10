import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";
import { useI18n } from "../lib/i18n";

export default function AdminPayouts() {
  const navigate = useNavigate();
  const { t, lang } = useI18n();
  const [period, setPeriod] = useState("");
  const [result, setResult] = useState(null);
  const [preview, setPreview] = useState(null);
  const [payoutsList, setPayoutsList] = useState([]);
  const [payoutId, setPayoutId] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [selectedProfile, setSelectedProfile] = useState(null);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        await apiFetch("/api/admin/auth/me", { credentials: "include" });
        await loadPayouts();
      } catch {
        navigate("/admin/login", { replace: true });
      }
    };
    checkAuth();
  }, [navigate]);

  useEffect(() => {
    const loadProfile = async () => {
      if (!payoutId) {
        setSelectedProfile(null);
        setProfileError("");
        return;
      }
      const target = payoutsList.find((item) => String(item.payout_id) === String(payoutId));
      if (!target?.author_user_id) {
        setSelectedProfile(null);
        setProfileError(
          t({ ja: "振込先の取得に必要な作者情報がありません", en: "Missing author info for payout destination." })
        );
        return;
      }
      try {
        setProfileLoading(true);
        setProfileError("");
        const data = await apiFetch(
          `/api/admin/authors/${target.author_user_id}/payout_profile`,
          {
            credentials: "include",
          }
        );
        setSelectedProfile(data);
      } catch (e) {
        setProfileError(
          e.message || t({ ja: "振込先情報の取得に失敗しました", en: "Failed to load payout destination." })
        );
      } finally {
        setProfileLoading(false);
      }
    };
    loadProfile();
  }, [payoutId, payoutsList]);

  const loadPayouts = async () => {
    const data = await apiFetch("/api/admin/payouts?status=scheduled,processing", {
      credentials: "include",
    });
    setPayoutsList(data.items || []);
    if (data.items?.length && !payoutId) {
      setPayoutId(String(data.items[0].payout_id));
    }
  };

  const handleGenerate = async () => {
    if (!period) {
      setError(t({ ja: "精算期間を入力してください (YYYY-MM)", en: "Enter payout period (YYYY-MM)" }));
      return;
    }
    try {
      setLoading(true);
      setError("");
      setPreview(null);
      const data = await apiFetch(`/api/admin/payouts/generate?period=${period}`, {
        method: "POST",
        credentials: "include",
      });
      setResult(data);
      await loadPayouts();
    } catch (e) {
      setError(e.message || t({ ja: "精算生成に失敗しました", en: "Failed to generate payouts." }));
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async () => {
    if (!period) {
      setError(t({ ja: "精算期間を入力してください (YYYY-MM)", en: "Enter payout period (YYYY-MM)" }));
      return;
    }
    try {
      setLoading(true);
      setError("");
      setResult(null);
      const data = await apiFetch(`/api/admin/payouts/preview?period=${period}`, {
        credentials: "include",
      });
      setPreview(data);
    } catch (e) {
      setError(e.message || t({ ja: "確認に失敗しました", en: "Preview failed." }));
    } finally {
      setLoading(false);
    }
  };

  const handleMark = async (action) => {
    if (!payoutId) {
      setError(t({ ja: "振込対象を選択してください", en: "Select a payout target." }));
      return;
    }
    try {
      setLoading(true);
      setError("");
      await apiFetch(`/api/admin/payouts/${payoutId}/${action}`, {
        method: "POST",
        body: { note },
        credentials: "include",
      });
      setResult({ message: t({ ja: "{{action}} 完了", en: "{{action}} completed" }, { action }), payout_id: payoutId });
      await loadPayouts();
    } catch (e) {
      setError(e.message || t({ ja: "更新に失敗しました", en: "Failed to update." }));
    } finally {
      setLoading(false);
    }
  };

  const yen = (value) => new Intl.NumberFormat(lang === "en" ? "en-US" : "ja-JP").format(value || 0);

  return (
    <div style={{ maxWidth: 700, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">{t({ ja: "← トップに戻る", en: "← Back to Home" })}</Link>
      </div>

      <h2 style={{ marginBottom: 16 }}>
        {t({ ja: "精算管理 (運営)", en: "Payout Management (Admin)" })}
      </h2>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <section
        style={{
          border: "1px solid #ddd",
          borderRadius: 10,
          padding: 16,
          marginBottom: 16,
          background: "#fff",
        }}
      >
        <h3 style={{ marginTop: 0 }}>精算生成</h3>
        <input
          type="month"
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
        />
        <button
          type="button"
          className="btn btn-border"
          style={{ marginLeft: 8 }}
          onClick={handleGenerate}
          disabled={loading}
        >
          {loading ? t({ ja: "処理中...", en: "Processing..." }) : t({ ja: "generate", en: "Generate" })}
        </button>
        <button
          type="button"
          className="btn btn-border"
          style={{ marginLeft: 8 }}
          onClick={handlePreview}
          disabled={loading}
        >
          {loading ? t({ ja: "処理中...", en: "Processing..." }) : t({ ja: "preview", en: "Preview" })}
        </button>

        {result && (
          <div style={{ marginTop: 12, fontSize: 14 }}>
            <div>{t({ ja: "作成件数", en: "Created" })}: {result.count ?? "-"}</div>
            <div>{t({ ja: "合計金額", en: "Total amount" })}: {result.total_amount_yen ?? "-"} {t({ ja: "円", en: "JPY" })}</div>
            {result.message && <div>{result.message}</div>}
          </div>
        )}
        {preview && (
          <div style={{ marginTop: 12, fontSize: 14 }}>
            <div>
              {t({ ja: "期間", en: "Period" })}: {preview.period_start} – {preview.period_end}
            </div>
            <div>
              {t({ ja: "対象支援", en: "Supports" })}: {preview.support_count ?? 0}{" "}
              {t({ ja: "件", en: "items" })} / {t({ ja: "対象請求", en: "Invoices" })}:{" "}
              {preview.invoice_count ?? 0} {t({ ja: "件", en: "items" })}
            </div>
            <div style={{ marginTop: 8 }}>
              {preview.authors?.length ? (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                        {t({ ja: "作者", en: "Author" })}
                      </th>
                      <th style={{ textAlign: "right", borderBottom: "1px solid #eee" }}>
                        {t({ ja: "合計", en: "Total" })}
                      </th>
                      <th style={{ textAlign: "right", borderBottom: "1px solid #eee" }}>
                        {t({ ja: "支援", en: "Support" })}
                      </th>
                      <th style={{ textAlign: "right", borderBottom: "1px solid #eee" }}>
                        {t({ ja: "請求", en: "Invoice" })}
                      </th>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                        {t({ ja: "状態", en: "Status" })}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.authors.map((row) => (
                      <tr key={row.author_user_id}>
                        <td style={{ padding: "6px 4px" }}>{row.username}</td>
                        <td style={{ padding: "6px 4px", textAlign: "right" }}>
                          {row.total_amount_yen} {t({ ja: "円", en: "JPY" })}
                        </td>
                        <td style={{ padding: "6px 4px", textAlign: "right" }}>
                          {row.support_amount_yen} {t({ ja: "円", en: "JPY" })}
                        </td>
                        <td style={{ padding: "6px 4px", textAlign: "right" }}>
                          {row.invoice_amount_yen} {t({ ja: "円", en: "JPY" })}
                        </td>
                        <td style={{ padding: "6px 4px" }}>
                          {row.eligible
                            ? t({ ja: "精算対象", en: "Eligible" })
                            : row.reason === "payout_disabled"
                            ? t({ ja: "振込無効", en: "Payout disabled" })
                            : row.reason === "below_minimum"
                            ? t(
                                { ja: "最低額未満 ({{amount}}円)", en: "Below minimum (¥{{amount}})" },
                                { amount: row.payout_minimum_yen }
                              )
                            : t({ ja: "対象外", en: "Not eligible" })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div>{t({ ja: "対象となる作者がいません。", en: "No eligible authors." })}</div>
              )}
            </div>
          </div>
        )}
      </section>

      <section
        style={{
          border: "1px solid #ddd",
          borderRadius: 10,
          padding: 16,
        background: "#fff",
      }}
    >
        <h3 style={{ marginTop: 0 }}>{t({ ja: "支払確定 / 失敗", en: "Mark paid / failed" })}</h3>
        <div style={{ display: "grid", gap: 8 }}>
          <label>
            {t({ ja: "振込対象", en: "Payout target" })}
            <select
              value={payoutId}
              onChange={(e) => setPayoutId(e.target.value)}
              style={{ width: "100%" }}
            >
              <option value="">{t({ ja: "選択してください", en: "Select" })}</option>
              {payoutsList.map((item) => (
                <option key={item.payout_id} value={item.payout_id}>
                  {t(
                    {
                      ja: "#{{id}} {{name}} / {{amount}}円 ({{start}}〜{{end}})",
                      en: "#{{id}} {{name}} / ¥{{amount}} ({{start}}–{{end}})",
                    },
                    {
                      id: item.payout_id,
                      name: item.username,
                      amount: item.amount_yen,
                      start: item.period_start,
                      end: item.period_end,
                    }
                  )}
                </option>
              ))}
            </select>
          </label>
          {profileLoading && (
            <div style={{ fontSize: 13, color: "#666" }}>
              {t({ ja: "振込先情報を取得中...", en: "Loading payout destination..." })}
            </div>
          )}
          {profileError && <div style={{ fontSize: 13, color: "red" }}>{profileError}</div>}
          {selectedProfile && (
            <div
              style={{
                border: "1px solid #e0e0e0",
                padding: 10,
                borderRadius: 8,
                background: "#f9fbfc",
                fontSize: 13,
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 6 }}>
                {t(
                  { ja: "{{name}} の振込先", en: "Payout destination for {{name}}" },
                  { name: selectedProfile.username }
                )}
              </div>
              <div>
                {t({ ja: "振込有効", en: "Payout enabled" })}:{" "}
                {selectedProfile.payout_enabled
                  ? t({ ja: "有効", en: "Enabled" })
                  : t({ ja: "無効", en: "Disabled" })}
              </div>
              <div>
                {t({ ja: "最低振込額", en: "Minimum payout" })}: {yen(selectedProfile.payout_minimum_yen)}{" "}
                {t({ ja: "円", en: "JPY" })}
              </div>
              <div>{t({ ja: "銀行名", en: "Bank name" })}: {selectedProfile.bank_name || "-"}</div>
              <div>{t({ ja: "支店名", en: "Branch name" })}: {selectedProfile.bank_branch || "-"}</div>
              <div>{t({ ja: "口座種別", en: "Account type" })}: {selectedProfile.bank_account_type || "-"}</div>
              <div>{t({ ja: "口座番号", en: "Account number" })}: {selectedProfile.bank_account_number || "-"}</div>
              <div>{t({ ja: "口座名義", en: "Account holder" })}: {selectedProfile.bank_account_holder || "-"}</div>
            </div>
          )}
          <label>
            {t({ ja: "メモ", en: "Note" })}
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              style={{ width: "100%" }}
              placeholder={t({ ja: "振込控えIDなど", en: "e.g., payout receipt ID" })}
            />
          </label>
        </div>

        <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => handleMark("mark_paid")}
            disabled={loading}
          >
            {t({ ja: "振込完了にする", en: "Mark as paid" })}
          </button>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => handleMark("mark_failed")}
            disabled={loading}
          >
            {t({ ja: "振込失敗にする", en: "Mark as failed" })}
          </button>
        </div>
        {!payoutsList.length && (
          <div style={{ marginTop: 10, color: "#666", fontSize: 13 }}>
            {t({ ja: "振込待ちの精算がありません。", en: "No pending payouts." })}
          </div>
        )}
      </section>
    </div>
  );
}
