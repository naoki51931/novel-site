import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";

export default function AuthorBalanceCard() {
  const [balance, setBalance] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchBalance = async () => {
    try {
      setLoading(true);
      setError("");
      const data = await apiFetch("/api/authors/me/balance", { auth: true });
      setBalance(data);
    } catch (e) {
      setError(e.message || "残高の取得に失敗しました");
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
        <h3 style={{ margin: 0 }}>売上残高</h3>
        <button type="button" className="btn btn-border" onClick={fetchBalance}>
          {loading ? "更新中..." : "更新"}
        </button>
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {balance && (
        <div style={{ marginTop: 12 }}>
          <p style={{ margin: 0, fontSize: 20, fontWeight: "bold" }}>
            {Number(balance.available_yen ?? 0).toLocaleString()} 円
          </p>
          {Number(balance.pending_yen ?? 0) > 0 && (
            <p style={{ margin: "4px 0", color: "#666" }}>
              確定待ち: {Number(balance.pending_yen ?? 0).toLocaleString()} 円
            </p>
          )}
          <p style={{ margin: "8px 0 0", fontSize: 12, color: "#666" }}>
            精算は運営が月次で行います。
          </p>
        </div>
      )}
    </section>
  );
}
