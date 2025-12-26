import { useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../lib/api";

export default function AdminPayouts() {
  const [period, setPeriod] = useState("");
  const [result, setResult] = useState(null);
  const [payoutId, setPayoutId] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleGenerate = async () => {
    if (!period) {
      setError("精算期間を入力してください (YYYY-MM)");
      return;
    }
    try {
      setLoading(true);
      setError("");
      const data = await apiFetch(`/api/admin/payouts/generate?period=${period}`, {
        method: "POST",
        admin: true,
      });
      setResult(data);
    } catch (e) {
      setError(e.message || "精算生成に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  const handleMark = async (action) => {
    if (!payoutId) {
      setError("payout_id を入力してください");
      return;
    }
    try {
      setLoading(true);
      setError("");
      await apiFetch(`/api/admin/payouts/${payoutId}/${action}`, {
        method: "POST",
        body: { note },
        admin: true,
      });
      setResult({ message: `${action} 完了`, payout_id: payoutId });
    } catch (e) {
      setError(e.message || "更新に失敗しました");
    } finally {
      setLoading(false);
    }
  };

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

        {result && (
          <div style={{ marginTop: 12, fontSize: 14 }}>
            <div>作成件数: {result.count ?? "-"}</div>
            <div>合計金額: {result.total_amount_yen ?? "-"} 円</div>
            {result.message && <div>{result.message}</div>}
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
            payout_id
            <input
              type="number"
              value={payoutId}
              onChange={(e) => setPayoutId(e.target.value)}
              style={{ width: "100%" }}
            />
          </label>
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
            mark_paid
          </button>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => handleMark("mark_failed")}
            disabled={loading}
          >
            mark_failed
          </button>
        </div>
      </section>
    </div>
  );
}
