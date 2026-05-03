import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";

type AdminUser = {
  id: number | string;
  username?: string | null;
  email?: string | null;
  is_premium?: boolean | null;
  email_notifications_enabled?: boolean | null;
  novel_count?: number | null;
};

type AdminNovel = {
  id: number | string;
  title?: string | null;
  is_public?: boolean | null;
  episode_count?: number | null;
  created_at?: string | null;
};

type TokenTimelineDay = {
  tokens_used?: number | null;
};

type TokenTimelineConsumer = {
  user_id: number | string;
  username?: string | null;
  range_tokens_used?: number | null;
  current_tokens_used?: number | null;
  events?: number | null;
  days?: TokenTimelineDay[] | null;
};

type TokenTimeline = {
  start_date?: string | null;
  end_date?: string | null;
  total_range_tokens_used?: number | null;
  consumers?: TokenTimelineConsumer[] | null;
};

function SparkBars({ data, width = 220, height = 42, color = "#2f6f6d" }: { data: number[]; width?: number; height?: number; color?: string }) {
  const max = useMemo(() => Math.max(...(Array.isArray(data) ? data : [0]), 1), [data]);
  const list = Array.isArray(data) && data.length ? data : [0];
  const barWidth = width / list.length;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      {list.map((value, index) => {
        const h = Math.max(1, (Number(value || 0) / max) * (height - 6));
        const x = index * barWidth + 0.5;
        const y = height - h - 1;
        return (
          <rect
            key={`${index}-${value}`}
            x={x}
            y={y}
            width={Math.max(1, barWidth - 1)}
            height={h}
            fill={color}
            rx={1}
          />
        );
      })}
    </svg>
  );
}

export default function AdminUsers() {
  const navigate = useNavigate();
  const { t, lang } = useI18n();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [expandedUsers, setExpandedUsers] = useState<Set<AdminUser["id"]>>(() => new Set());
  const [novelsByUser, setNovelsByUser] = useState<Record<string, AdminNovel[]>>({});
  const [novelsLoading, setNovelsLoading] = useState<Record<string, boolean>>({});
  const [novelsError, setNovelsError] = useState<Record<string, string>>({});
  const [mailTestRunning, setMailTestRunning] = useState(false);
  const [mailTestMessage, setMailTestMessage] = useState("");
  const [tokenDays, setTokenDays] = useState(30);
  const [tokenLimit, setTokenLimit] = useState(20);
  const [tokenTimeline, setTokenTimeline] = useState<TokenTimeline | null>(null);
  const [tokenLoading, setTokenLoading] = useState(false);
  const [tokenError, setTokenError] = useState("");

  const loadUsers = async () => {
    try {
      setLoading(true);
      setError("");
      await apiFetch("/api/admin/auth/me", { credentials: "include" });
      const data = await apiFetch("/api/admin/users?limit=200", {
        credentials: "include",
      });
      setUsers(data.users || []);
      setTotalUsers(data.total_users || 0);
    } catch (e) {
      if (getErrorMessage(e, "").includes("401")) {
        navigate("/admin/login", { replace: true });
        return;
      }
      setError(getErrorMessage(e, t({ ja: "ユーザー情報の取得に失敗しました。", en: "Failed to load users." })));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  useEffect(() => {
    const loadTokenTimeline = async () => {
      try {
        setTokenLoading(true);
        setTokenError("");
        await apiFetch("/api/admin/auth/me", { credentials: "include" });
        const data = await apiFetch(
          `/api/admin/ai-chat/token-consumers/timeline?days=${encodeURIComponent(tokenDays)}&limit=${encodeURIComponent(tokenLimit)}`,
          { credentials: "include" }
        );
        setTokenTimeline(data || null);
      } catch (e) {
        if (getErrorMessage(e, "").includes("401")) {
          navigate("/admin/login", { replace: true });
          return;
        }
        setTokenError(
          getErrorMessage(e, t({ ja: "AIチャットトークン集計の取得に失敗しました。", en: "Failed to load AI chat token timeline." }))
        );
      } finally {
        setTokenLoading(false);
      }
    };
    loadTokenTimeline();
  }, [navigate, t, tokenDays, tokenLimit]);

  const handleToggleNovels = async (userId: AdminUser["id"]) => {
    setExpandedUsers((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });

    const userKey = String(userId);
    if (novelsByUser[userKey]) return;
    try {
      setNovelsLoading((prev) => ({ ...prev, [userKey]: true }));
      setNovelsError((prev) => ({ ...prev, [userKey]: "" }));
      const data = await apiFetch(`/api/admin/users/${userId}/novels`, {
        credentials: "include",
      });
      setNovelsByUser((prev) => ({ ...prev, [userKey]: data || [] }));
    } catch (e) {
      setNovelsError((prev) => ({
        ...prev,
        [userKey]: getErrorMessage(e, t({ ja: "小説情報の取得に失敗しました。", en: "Failed to load novels." })),
      }));
    } finally {
      setNovelsLoading((prev) => ({ ...prev, [userKey]: false }));
    }
  };

  const handleDelete = async (user: AdminUser) => {
    const confirmMessage = t(
      {
        ja: "ユーザーと関連データを削除します。よろしいですか？",
        en: "Delete the user and related data. Continue?",
      }
    );
    if (!window.confirm(confirmMessage)) return;

    try {
      await apiFetch(`/api/admin/users/${user.id}`, {
        method: "DELETE",
        credentials: "include",
      });
      setUsers((prev) => prev.filter((item) => item.id !== user.id));
      setTotalUsers((prev) => Math.max(0, prev - 1));
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "ユーザー削除に失敗しました。", en: "Failed to delete user." })));
    }
  };

  const handleSendTestEmails = async () => {
    const confirmMessage = t({
      ja: "全ユーザーへテストメールを送信します。実行しますか？",
      en: "Send test emails to all users. Continue?",
    });
    if (!window.confirm(confirmMessage)) return;

    try {
      setError("");
      setMailTestMessage("");
      setMailTestRunning(true);
      const result = await apiFetch("/api/admin/email-test-all-users", {
        method: "POST",
        credentials: "include",
      });
      setMailTestMessage(
        t({
          ja: `送信対象 ${result.target_users} 件 / 成功 ${result.sent_count} 件 / アドレス不明 ${result.invalid_address_count} 件 / 未設定 ${result.skipped_no_email_count} 件 / その他失敗 ${result.failed_other_count} 件`,
          en: `Target ${result.target_users} / Sent ${result.sent_count} / Invalid ${result.invalid_address_count} / No email ${result.skipped_no_email_count} / Other failures ${result.failed_other_count}`,
        })
      );
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "テストメール送信に失敗しました。", en: "Failed to send test emails." })));
    } finally {
      setMailTestRunning(false);
    }
  };

  const expandedIds = useMemo(() => expandedUsers, [expandedUsers]);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/admin">{t({ ja: "← 管理画面に戻る", en: "← Back to Admin" })}</Link>
      </div>
      <h2 style={{ marginBottom: 8 }}>{t({ ja: "ユーザー管理", en: "User Management" })}</h2>
      <p style={{ marginTop: 0, marginBottom: 12, color: "var(--muted-text)" }}>
        {t({
          ja: "登録ユーザー数とユーザーの小説を確認できます。",
          en: "Review total users and each user's novels.",
        })}
      </p>
      <div style={{ fontSize: 14, marginBottom: 16 }}>
        {t({ ja: "現在のユーザー数", en: "Total users" })}: {totalUsers}
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 16, flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn btn-border"
          onClick={handleSendTestEmails}
          disabled={mailTestRunning}
        >
          {mailTestRunning
            ? t({ ja: "送信中...", en: "Sending..." })
            : t({ ja: "全ユーザーへテストメール送信", en: "Send test email to all users" })}
        </button>
        {mailTestMessage && <span style={{ fontSize: 13, color: "#0a0" }}>{mailTestMessage}</span>}
      </div>

      <section
        style={{
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: 14,
          marginBottom: 16,
          background: "var(--surface)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <h3 style={{ margin: 0 }}>{t({ ja: "AIチャット トークン消費者（時系列）", en: "AI Chat Token Consumers (Timeline)" })}</h3>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <label style={{ fontSize: 13 }}>
              {t({ ja: "期間", en: "Range" })}
              <select value={tokenDays} onChange={(e) => setTokenDays(Number(e.target.value))} style={{ marginLeft: 6 }}>
                <option value={7}>7d</option>
                <option value={30}>30d</option>
                <option value={90}>90d</option>
                <option value={180}>180d</option>
              </select>
            </label>
            <label style={{ fontSize: 13 }}>
              {t({ ja: "上位", en: "Top" })}
              <select value={tokenLimit} onChange={(e) => setTokenLimit(Number(e.target.value))} style={{ marginLeft: 6 }}>
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
            </label>
          </div>
        </div>

        {tokenLoading && <div style={{ marginTop: 10, fontSize: 13 }}>{t({ ja: "集計中...", en: "Loading timeline..." })}</div>}
        {tokenError && <div style={{ marginTop: 10, fontSize: 13, color: "red" }}>{tokenError}</div>}

        {!tokenLoading && !tokenError && tokenTimeline && (
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 12, color: "var(--muted-text)", marginBottom: 8 }}>
              {t(
                {
                  ja: "{{start}} 〜 {{end}} / 期間合計 {{total}} tokens",
                  en: "{{start}} to {{end}} / Range total {{total}} tokens",
                },
                {
                  start: tokenTimeline.start_date,
                  end: tokenTimeline.end_date,
                  total: Number(tokenTimeline.total_range_tokens_used || 0).toLocaleString(lang === "en" ? "en-US" : "ja-JP"),
                }
              )}
            </div>
            {Array.isArray(tokenTimeline.consumers) && tokenTimeline.consumers.length ? (
              <div style={{ display: "grid", gap: 8 }}>
                {tokenTimeline.consumers.map((item: TokenTimelineConsumer) => (
                  <div
                    key={item.user_id}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "minmax(180px, 1fr) auto",
                      gap: 10,
                      alignItems: "center",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      padding: 10,
                      background: "var(--surface-2)",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600 }}>
                        {item.username} (ID: {item.user_id})
                      </div>
                      <div style={{ fontSize: 12, color: "var(--muted-text)", marginTop: 4 }}>
                        {t(
                          {
                            ja: "期間 {{range}} / 累計 {{current}} / イベント {{events}}",
                            en: "Range {{range}} / Lifetime {{current}} / Events {{events}}",
                          },
                          {
                            range: Number(item.range_tokens_used || 0).toLocaleString(lang === "en" ? "en-US" : "ja-JP"),
                            current: Number(item.current_tokens_used || 0).toLocaleString(lang === "en" ? "en-US" : "ja-JP"),
                            events: Number(item.events || 0).toLocaleString(lang === "en" ? "en-US" : "ja-JP"),
                          }
                        )}
                      </div>
                    </div>
                    <SparkBars
                      data={(Array.isArray(item.days) ? item.days : []).map((d: TokenTimelineDay) => Number(d?.tokens_used || 0))}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 13, color: "var(--muted-text)" }}>
                {t({ ja: "該当期間のデータがありません。", en: "No data for this period." })}
              </div>
            )}
          </div>
        )}
      </section>

      {error && <div style={{ color: "red", marginBottom: 12 }}>{error}</div>}
      {loading && <div>{t({ ja: "読み込み中...", en: "Loading..." })}</div>}

      {!loading && (
        <div style={{ display: "grid", gap: 12 }}>
          {users.length ? (
            users.map((user: AdminUser) => {
              const novels = novelsByUser[String(user.id)] || [];
              const isExpanded = expandedIds.has(user.id);
              return (
                <section
                  key={user.id}
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 10,
                    padding: 14,
                    background: "var(--surface)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 16,
                      flexWrap: "wrap",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600 }}>{user.username}</div>
                      <div style={{ fontSize: 12, color: "var(--muted-text)", marginTop: 4 }}>
                        ID: {user.id} / {user.email || "-"} /{" "}
                        {t({ ja: "有料", en: "Premium" })}:{" "}
                        {user.is_premium ? t({ ja: "有効", en: "Active" }) : t({ ja: "無効", en: "Inactive" })}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--muted-text)", marginTop: 4 }}>
                        {t({ ja: "通知メール", en: "Email notifications" })}:{" "}
                        {user.email_notifications_enabled
                          ? t({ ja: "有効", en: "Enabled" })
                          : t({ ja: "無効", en: "Disabled" })}
                        {" / "}
                        {t({ ja: "小説数", en: "Novels" })}: {user.novel_count}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <button
                        type="button"
                        className="btn btn-border"
                        onClick={() => handleToggleNovels(user.id)}
                      >
                        {isExpanded
                          ? t({ ja: "小説を閉じる", en: "Hide novels" })
                          : t({ ja: "小説を見る", en: "View novels" })}
                      </button>
                      <button
                        type="button"
                        className="btn btn-border"
                        onClick={() => handleDelete(user)}
                        style={{ borderColor: "#b3261e", color: "#b3261e" }}
                      >
                        {t({ ja: "ユーザー削除", en: "Delete user" })}
                      </button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div style={{ marginTop: 12 }}>
                      {novelsLoading[String(user.id)] && (
                        <div style={{ fontSize: 13 }}>{t({ ja: "小説を取得中...", en: "Loading novels..." })}</div>
                      )}
                      {novelsError[String(user.id)] && (
                        <div style={{ fontSize: 13, color: "red" }}>{novelsError[String(user.id)]}</div>
                      )}
                      {!novelsLoading[String(user.id)] && !novelsError[String(user.id)] && (
                        <>
                          {novels.length ? (
                            <div style={{ display: "grid", gap: 8 }}>
                              {novels.map((novel: AdminNovel) => (
                                <div
                                  key={novel.id}
                                  style={{
                                    border: "1px solid var(--border)",
                                    borderRadius: 8,
                                    padding: 10,
                                    background: "var(--surface-2)",
                                  }}
                                >
                                  <div style={{ fontWeight: 600 }}>
                                    <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
                                  </div>
                                  <div style={{ fontSize: 12, color: "var(--muted-text)", marginTop: 4 }}>
                                    {t({ ja: "公開", en: "Public" })}:{" "}
                                    {novel.is_public
                                      ? t({ ja: "公開", en: "Public" })
                                      : t({ ja: "非公開", en: "Private" })}
                                    {" / "}
                                    {t({ ja: "話数", en: "Episodes" })}: {novel.episode_count}
                                  </div>
                                  <div style={{ fontSize: 12, color: "var(--muted-text)", marginTop: 4 }}>
                                    {t({ ja: "作成日", en: "Created" })}:{" "}
                                    {novel.created_at
                                      ? new Date(novel.created_at).toLocaleDateString(
                                          lang === "en" ? "en-US" : "ja-JP",
                                          { timeZone: "Asia/Tokyo" }
                                        )
                                      : "-"}
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div style={{ fontSize: 13, color: "var(--muted-text)" }}>
                              {t({ ja: "小説がありません。", en: "No novels." })}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </section>
              );
            })
          ) : (
            <div style={{ color: "var(--muted-text)" }}>
              {t({ ja: "ユーザーが存在しません。", en: "No users found." })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
