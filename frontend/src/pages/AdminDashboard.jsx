import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";

const yen = (value) => new Intl.NumberFormat("ja-JP").format(value || 0);

function SparkBars({ data, width = 260, height = 46, color = "#2f6f6d" }) {
  const max = useMemo(() => Math.max(...data, 1), [data]);
  const barWidth = width / data.length;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      {data.map((value, index) => {
        const h = Math.max(1, (value / max) * (height - 6));
        const x = index * barWidth + 0.5;
        const y = height - h - 1;
        return (
          <rect
            key={`${index}-${value}`}
            x={x}
            y={y}
            width={barWidth - 1}
            height={h}
            fill={color}
            rx={1}
          />
        );
      })}
    </svg>
  );
}

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [supports, setSupports] = useState(null);
  const [payouts, setPayouts] = useState(null);
  const [supportBy, setSupportBy] = useState("author");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [selectedProfile, setSelectedProfile] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError("");
        await apiFetch("/api/admin/auth/me", { credentials: "include" });
        const [supportsData, payoutsData] = await Promise.all([
          apiFetch(`/api/admin/supports/timeline?days=30&limit=10&by=${supportBy}`, {
            credentials: "include",
          }),
          apiFetch("/api/admin/payouts/timeline?days=90", {
            credentials: "include",
          }),
        ]);
        setSupports(supportsData);
        setPayouts(payoutsData);
      } catch (e) {
        if (String(e?.message || "").includes("401")) {
          navigate("/admin/login", { replace: true });
          return;
        }
        setError(e.message || "データ取得に失敗しました");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [navigate, supportBy]);

  const handleProfileOpen = async (authorUserId) => {
    try {
      setProfileLoading(true);
      setProfileError("");
      const data = await apiFetch(`/api/admin/authors/${authorUserId}/payout_profile`, {
        credentials: "include",
      });
      setSelectedProfile(data);
    } catch (e) {
      setProfileError(e.message || "口座情報の取得に失敗しました");
    } finally {
      setProfileLoading(false);
    }
  };

  const supportWindow = supports
    ? `${supports.start_date} 〜 (${supports.days}日)`
    : "";
  const payoutWindow = payouts
    ? `${payouts.start_date} 〜 (${payouts.days}日)`
    : "";

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/admin">← 管理画面に戻る</Link>
      </div>

      <h2 style={{ marginBottom: 8 }}>支援・振込ダッシュボード</h2>
      <p style={{ marginTop: 0, marginBottom: 16, color: "#555" }}>
        支援発生と振込タイミングを直近の流れで確認できます。
      </p>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {loading && <p>読み込み中...</p>}

      {!loading && (
        <>
          <section
            style={{
              border: "1px solid #ddd",
              borderRadius: 10,
              padding: 16,
              marginBottom: 16,
              background: "#fff",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <h3 style={{ marginTop: 0 }}>支援タイミング（ユーザー別）</h3>
              <label style={{ fontSize: 13, color: "#666" }}>
                表示対象
                <select
                  value={supportBy}
                  onChange={(e) => setSupportBy(e.target.value)}
                  style={{ marginLeft: 8 }}
                >
                  <option value="author">作者（受け取り）</option>
                  <option value="supporter">支援者</option>
                </select>
              </label>
            </div>
            <div style={{ fontSize: 12, color: "#777", marginBottom: 12 }}>
              {supportWindow}
            </div>

            {supports?.users?.length ? (
              <div style={{ display: "grid", gap: 12 }}>
                {supports.users.map((user) => (
                  <div
                    key={user.user_id}
                    style={{
                      display: "grid",
                      gap: 8,
                      gridTemplateColumns: "180px 1fr",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600 }}>{user.username}</div>
                      <div style={{ fontSize: 12, color: "#666" }}>
                        合計 {yen(user.total_amount_yen)}円 / {user.total_count}件
                      </div>
                    </div>
                    <SparkBars data={user.amounts} />
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: "#666", fontSize: 14 }}>
                該当期間の支援データがありません。
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
            <h3 style={{ marginTop: 0 }}>振込タイミング</h3>
            <div style={{ fontSize: 12, color: "#777", marginBottom: 12 }}>
              {payoutWindow} / 振込最低額 {yen(payouts?.payout_minimum_yen)}円
            </div>

            {payouts && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 13, color: "#666", marginBottom: 6 }}>
                  振込完了（合計金額）
                </div>
                <SparkBars data={payouts.paid_amounts} color="#3b5b7a" />
              </div>
            )}

            <div style={{ display: "grid", gap: 16 }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>振込待ち</div>
                {payouts?.upcoming?.length ? (
                  <div style={{ display: "grid", gap: 6 }}>
                    {payouts.upcoming.map((item) => (
                      <div
                        key={item.payout_id}
                        style={{
                          display: "grid",
                          gap: 6,
                          gridTemplateColumns: "110px 1fr 140px",
                          fontSize: 13,
                        }}
                      >
                        <div>#{item.payout_id}</div>
                        <div>
                          {item.username} / {yen(item.amount_yen)}円
                          <div style={{ color: "#666", fontSize: 12 }}>
                            {item.period_start} 〜 {item.period_end}
                          </div>
                          <button
                            type="button"
                            onClick={() => handleProfileOpen(item.author_user_id)}
                            style={{
                              marginTop: 6,
                              border: "none",
                              background: "none",
                              padding: 0,
                              color: "#1f5a7a",
                              cursor: "pointer",
                              textDecoration: "underline",
                              fontSize: 12,
                            }}
                          >
                            口座情報を見る
                          </button>
                        </div>
                        <div style={{ textTransform: "uppercase", color: "#666" }}>
                          {item.status}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: "#666", fontSize: 13 }}>
                    振込待ちのデータがありません。
                  </div>
                )}
                {profileLoading && (
                  <div style={{ marginTop: 12, fontSize: 13 }}>口座情報を取得中...</div>
                )}
                {profileError && (
                  <div style={{ marginTop: 12, fontSize: 13, color: "red" }}>
                    {profileError}
                  </div>
                )}
                {selectedProfile && (
                  <div
                    style={{
                      marginTop: 12,
                      border: "1px solid #e0e0e0",
                      padding: 12,
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
              </div>

              <div>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>最近の振込</div>
                {payouts?.recent_paid?.length ? (
                  <div style={{ display: "grid", gap: 6 }}>
                    {payouts.recent_paid.map((item) => (
                      <div
                        key={item.payout_id}
                        style={{
                          display: "grid",
                          gap: 6,
                          gridTemplateColumns: "110px 1fr 140px",
                          fontSize: 13,
                        }}
                      >
                        <div>#{item.payout_id}</div>
                        <div>
                          {item.username} / {yen(item.amount_yen)}円
                          <div style={{ color: "#666", fontSize: 12 }}>
                            {item.period_start} 〜 {item.period_end}
                          </div>
                        </div>
                        <div style={{ color: "#666" }}>
                          {item.paid_at ? item.paid_at.slice(0, 10) : "-"}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: "#666", fontSize: 13 }}>
                    振込履歴がありません。
                  </div>
                )}
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
