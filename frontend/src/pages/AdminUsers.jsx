import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";
import { useI18n } from "../lib/i18n";

export default function AdminUsers() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [users, setUsers] = useState([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [expandedUsers, setExpandedUsers] = useState(() => new Set());
  const [novelsByUser, setNovelsByUser] = useState({});
  const [novelsLoading, setNovelsLoading] = useState({});
  const [novelsError, setNovelsError] = useState({});

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
      if (String(e?.message || "").includes("401")) {
        navigate("/admin/login", { replace: true });
        return;
      }
      setError(e.message || t({ ja: "ユーザー情報の取得に失敗しました。", en: "Failed to load users." }));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleToggleNovels = async (userId) => {
    setExpandedUsers((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });

    if (novelsByUser[userId]) return;
    try {
      setNovelsLoading((prev) => ({ ...prev, [userId]: true }));
      setNovelsError((prev) => ({ ...prev, [userId]: "" }));
      const data = await apiFetch(`/api/admin/users/${userId}/novels`, {
        credentials: "include",
      });
      setNovelsByUser((prev) => ({ ...prev, [userId]: data || [] }));
    } catch (e) {
      setNovelsError((prev) => ({
        ...prev,
        [userId]: e.message || t({ ja: "小説情報の取得に失敗しました。", en: "Failed to load novels." }),
      }));
    } finally {
      setNovelsLoading((prev) => ({ ...prev, [userId]: false }));
    }
  };

  const handleDelete = async (user) => {
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
      setError(e.message || t({ ja: "ユーザー削除に失敗しました。", en: "Failed to delete user." }));
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

      {error && <div style={{ color: "red", marginBottom: 12 }}>{error}</div>}
      {loading && <div>{t({ ja: "読み込み中...", en: "Loading..." })}</div>}

      {!loading && (
        <div style={{ display: "grid", gap: 12 }}>
          {users.length ? (
            users.map((user) => {
              const novels = novelsByUser[user.id] || [];
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
                      {novelsLoading[user.id] && (
                        <div style={{ fontSize: 13 }}>{t({ ja: "小説を取得中...", en: "Loading novels..." })}</div>
                      )}
                      {novelsError[user.id] && (
                        <div style={{ fontSize: 13, color: "red" }}>{novelsError[user.id]}</div>
                      )}
                      {!novelsLoading[user.id] && !novelsError[user.id] && (
                        <>
                          {novels.length ? (
                            <div style={{ display: "grid", gap: 8 }}>
                              {novels.map((novel) => (
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
                                    {new Date(novel.created_at).toLocaleDateString()}
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
