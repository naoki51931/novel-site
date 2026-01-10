import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";
import { useI18n } from "../lib/i18n";

const yen = (value, locale) =>
  new Intl.NumberFormat(locale || "ja-JP").format(value || 0);

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
  const { t, lang } = useI18n();
  const locale = lang === "en" ? "en-US" : "ja-JP";
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
        setError(e.message || t({ ja: "データ取得に失敗しました", en: "Failed to load data." }));
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
      setProfileError(
        e.message || t({ ja: "口座情報の取得に失敗しました", en: "Failed to load bank details." })
      );
    } finally {
      setProfileLoading(false);
    }
  };

  const supportWindow = supports
    ? t(
        { ja: "{{start}} 〜 ({{days}}日)", en: "{{start}} – ({{days}} days)" },
        { start: supports.start_date, days: supports.days }
      )
    : "";
  const payoutWindow = payouts
    ? t(
        { ja: "{{start}} 〜 ({{days}}日)", en: "{{start}} – ({{days}} days)" },
        { start: payouts.start_date, days: payouts.days }
      )
    : "";

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/admin">{t({ ja: "← 管理画面に戻る", en: "← Back to Admin" })}</Link>
      </div>

      <h2 style={{ marginBottom: 8 }}>
        {t({ ja: "支援・振込ダッシュボード", en: "Support & Payout Dashboard" })}
      </h2>
      <p style={{ marginTop: 0, marginBottom: 16, color: "#555" }}>
        {t({
          ja: "支援発生と振込タイミングを直近の流れで確認できます。",
          en: "Review recent support activity and payout timing.",
        })}
      </p>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {loading && <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>}

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
              <h3 style={{ marginTop: 0 }}>
                {t({ ja: "支援タイミング（ユーザー別）", en: "Support timing (by user)" })}
              </h3>
              <label style={{ fontSize: 13, color: "#666" }}>
                {t({ ja: "表示対象", en: "View by" })}
                <select
                  value={supportBy}
                  onChange={(e) => setSupportBy(e.target.value)}
                  style={{ marginLeft: 8 }}
                >
                  <option value="author">{t({ ja: "作者（受け取り）", en: "Author (recipient)" })}</option>
                  <option value="supporter">{t({ ja: "支援者", en: "Supporter" })}</option>
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
                        {t(
                          { ja: "合計 {{amount}}円 / {{count}}件", en: "Total ¥{{amount}} / {{count}} items" },
                          { amount: yen(user.total_amount_yen, locale), count: user.total_count }
                        )}
                      </div>
                    </div>
                    <SparkBars data={user.amounts} />
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: "#666", fontSize: 14 }}>
                {t({ ja: "該当期間の支援データがありません。", en: "No support data for this period." })}
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
            <h3 style={{ marginTop: 0 }}>{t({ ja: "振込タイミング", en: "Payout timing" })}</h3>
            <div style={{ fontSize: 12, color: "#777", marginBottom: 12 }}>
              {payoutWindow} /{" "}
              {t({ ja: "振込最低額", en: "Minimum payout" })}{" "}
              {t(
                { ja: "{{amount}}円", en: "¥{{amount}}" },
                { amount: yen(payouts?.payout_minimum_yen, locale) }
              )}
            </div>

            {payouts && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 13, color: "#666", marginBottom: 6 }}>
                  {t({ ja: "振込完了（合計金額）", en: "Completed payouts (total)" })}
                </div>
                <SparkBars data={payouts.paid_amounts} color="#3b5b7a" />
              </div>
            )}

            <div style={{ display: "grid", gap: 16 }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>
                  {t({ ja: "振込待ち", en: "Pending payouts" })}
                </div>
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
                          {item.username} /{" "}
                          {t({ ja: "{{amount}}円", en: "¥{{amount}}" }, { amount: yen(item.amount_yen, locale) })}
                          <div style={{ color: "#666", fontSize: 12 }}>
                            {item.period_start} – {item.period_end}
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
                            {t({ ja: "口座情報を見る", en: "View bank details" })}
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
                    {t({ ja: "振込待ちのデータがありません。", en: "No pending payouts." })}
                  </div>
                )}
                {profileLoading && (
                  <div style={{ marginTop: 12, fontSize: 13 }}>
                    {t({ ja: "口座情報を取得中...", en: "Loading bank details..." })}
                  </div>
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
                      {t({ ja: "最低振込額", en: "Minimum payout" })}:{" "}
                      {t(
                        { ja: "{{amount}}円", en: "¥{{amount}}" },
                        { amount: yen(selectedProfile.payout_minimum_yen, locale) }
                      )}
                    </div>
                    <div>
                      {t({ ja: "銀行名", en: "Bank name" })}: {selectedProfile.bank_name || "-"}
                    </div>
                    <div>
                      {t({ ja: "支店名", en: "Branch name" })}: {selectedProfile.bank_branch || "-"}
                    </div>
                    <div>
                      {t({ ja: "口座種別", en: "Account type" })}: {selectedProfile.bank_account_type || "-"}
                    </div>
                    <div>
                      {t({ ja: "口座番号", en: "Account number" })}: {selectedProfile.bank_account_number || "-"}
                    </div>
                    <div>
                      {t({ ja: "口座名義", en: "Account holder" })}: {selectedProfile.bank_account_holder || "-"}
                    </div>
                  </div>
                )}
              </div>

              <div>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>
                  {t({ ja: "最近の振込", en: "Recent payouts" })}
                </div>
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
                          {item.username} /{" "}
                          {t({ ja: "{{amount}}円", en: "¥{{amount}}" }, { amount: yen(item.amount_yen, locale) })}
                          <div style={{ color: "#666", fontSize: 12 }}>
                            {item.period_start} – {item.period_end}
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
                    {t({ ja: "振込履歴がありません。", en: "No payout history." })}
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
