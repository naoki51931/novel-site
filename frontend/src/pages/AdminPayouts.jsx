import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";

export default function AdminPayouts() {
  const navigate = useNavigate();
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
        setProfileError("振込先の取得に必要な作者情報がありません");
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
        setProfileError(e.message || "振込先情報の取得に失敗しました");
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
      setError("精算期間を入力してください (YYYY-MM)");
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
      setError(e.message || "精算生成に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async () => {
    if (!period) {
      setError("精算期間を入力してください (YYYY-MM)");
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
      setError(e.message || "確認に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  const handleMark = async (action) => {
    if (!payoutId) {
      setError("振込対象を選択してください");
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
      setResult({ message: `${action} 完了`, payout_id: payoutId });
      await loadPayouts();
    } catch (e) {
      setError(e.message || "更新に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  const yen = (value) => new Intl.NumberFormat("ja-JP").format(value || 0);

  return (
    <div style={{ maxWidth: 700, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← トップに戻る</Link>
      </div>

      <h2 style={{ marginBottom: 16 }}>精算管理 (運営)</h2>

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
          {loading ? "処理中..." : "generate"}
        </button>
        <button
          type="button"
          className="btn btn-border"
          style={{ marginLeft: 8 }}
          onClick={handlePreview}
          disabled={loading}
        >
          {loading ? "処理中..." : "preview"}
        </button>

        {result && (
          <div style={{ marginTop: 12, fontSize: 14 }}>
            <div>作成件数: {result.count ?? "-"}</div>
            <div>合計金額: {result.total_amount_yen ?? "-"} 円</div>
            {result.message && <div>{result.message}</div>}
          </div>
        )}
        {preview && (
          <div style={{ marginTop: 12, fontSize: 14 }}>
            <div>
              期間: {preview.period_start} 〜 {preview.period_end}
            </div>
            <div>
              対象支援: {preview.support_count ?? 0} 件 / 対象請求:{" "}
              {preview.invoice_count ?? 0} 件
            </div>
            <div style={{ marginTop: 8 }}>
              {preview.authors?.length ? (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                        作者
                      </th>
                      <th style={{ textAlign: "right", borderBottom: "1px solid #eee" }}>
                        合計
                      </th>
                      <th style={{ textAlign: "right", borderBottom: "1px solid #eee" }}>
                        支援
                      </th>
                      <th style={{ textAlign: "right", borderBottom: "1px solid #eee" }}>
                        請求
                      </th>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                        状態
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.authors.map((row) => (
                      <tr key={row.author_user_id}>
                        <td style={{ padding: "6px 4px" }}>{row.username}</td>
                        <td style={{ padding: "6px 4px", textAlign: "right" }}>
                          {row.total_amount_yen} 円
                        </td>
                        <td style={{ padding: "6px 4px", textAlign: "right" }}>
                          {row.support_amount_yen} 円
                        </td>
                        <td style={{ padding: "6px 4px", textAlign: "right" }}>
                          {row.invoice_amount_yen} 円
                        </td>
                        <td style={{ padding: "6px 4px" }}>
                          {row.eligible
                            ? "精算対象"
                            : row.reason === "payout_disabled"
                            ? "振込無効"
                            : row.reason === "below_minimum"
                            ? `最低額未満 (${row.payout_minimum_yen}円)`
                            : "対象外"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div>対象となる作者がいません。</div>
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
        <h3 style={{ marginTop: 0 }}>支払確定 / 失敗</h3>
        <div style={{ display: "grid", gap: 8 }}>
          <label>
            振込対象
            <select
              value={payoutId}
              onChange={(e) => setPayoutId(e.target.value)}
              style={{ width: "100%" }}
            >
              <option value="">選択してください</option>
              {payoutsList.map((item) => (
                <option key={item.payout_id} value={item.payout_id}>
                  #{item.payout_id} {item.username} / {item.amount_yen}円 (
                  {item.period_start}〜{item.period_end})
                </option>
              ))}
            </select>
          </label>
          {profileLoading && (
            <div style={{ fontSize: 13, color: "#666" }}>振込先情報を取得中...</div>
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
                {selectedProfile.username} の振込先
              </div>
              <div>振込有効: {selectedProfile.payout_enabled ? "有効" : "無効"}</div>
              <div>最低振込額: {yen(selectedProfile.payout_minimum_yen)}円</div>
              <div>銀行名: {selectedProfile.bank_name || "-"}</div>
              <div>支店名: {selectedProfile.bank_branch || "-"}</div>
              <div>口座種別: {selectedProfile.bank_account_type || "-"}</div>
              <div>口座番号: {selectedProfile.bank_account_number || "-"}</div>
              <div>口座名義: {selectedProfile.bank_account_holder || "-"}</div>
            </div>
          )}
          <label>
            メモ
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              style={{ width: "100%" }}
              placeholder="振込控えIDなど"
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
            振込完了にする
          </button>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => handleMark("mark_failed")}
            disabled={loading}
          >
            振込失敗にする
          </button>
        </div>
        {!payoutsList.length && (
          <div style={{ marginTop: 10, color: "#666", fontSize: 13 }}>
            振込待ちの精算がありません。
          </div>
        )}
      </section>
    </div>
  );
}
