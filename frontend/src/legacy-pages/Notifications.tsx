import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { formatDateTimeInUserTimeZone, setUserTimeZone } from "../lib/timezone";

type NotificationGroup = "all" | "reaction" | "follow" | "update" | "system";

type NotificationCounts = Record<NotificationGroup, number>;

type NotificationType =
  | "user_follow"
  | "followed_author_new_novel"
  | "followed_author_new_episode"
  | "tag_follow_new"
  | "novel_like"
  | "episode_like"
  | "novel_comment"
  | "episode_comment"
  | "novel_favorite"
  | "favorite_update"
  | "dm_message"
  | "recommended_novel_new"
  | "ai_generation_done"
  | "ai_generation_failed"
  | "support_paid"
  | "membership_paid"
  | "multilingual_ready";

type NotificationItem = {
  id: number | string;
  type?: string | null;
  title?: string | null;
  body?: string | null;
  created_at?: string | null;
  is_read?: boolean | null;
  actor_username?: string | null;
  link_url?: string | null;
};

export default function Notifications() {
  const navigate = useNavigate();
  const { t, lang } = useI18n();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [bulkDeletingType, setBulkDeletingType] = useState<string>("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [emailNotificationsEnabled, setEmailNotificationsEnabled] = useState(true);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [activeFilter, setActiveFilter] = useState<NotificationGroup>("all");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [counts, setCounts] = useState<NotificationCounts>({
    all: 0,
    reaction: 0,
    follow: 0,
    update: 0,
    system: 0,
  });
  const [unreadCountsByGroup, setUnreadCountsByGroup] = useState<NotificationCounts>({
    all: 0,
    reaction: 0,
    follow: 0,
    update: 0,
    system: 0,
  });
  const [unreadCount, setUnreadCount] = useState(0);
  const [reloadTick, setReloadTick] = useState(0);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      navigate("/login");
      return;
    }

    const load = async () => {
      try {
        setLoading(true);
        setError("");
        const res = await fetch("/api/users/me", {
          headers: { Authorization: "Bearer " + token },
        });
        if (res.status === 401) {
          navigate("/login");
          return;
        }
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(
            data.detail || t({ ja: "通知設定の取得に失敗しました", en: "Failed to load notification settings." })
          );
        }
        const profile = await res.json();
        if (profile?.timezone) setUserTimeZone(profile.timezone);
        setEmailNotificationsEnabled(
          profile.email_notifications_enabled !== false
        );
        const params = new URLSearchParams();
        if (activeFilter !== "all") params.set("group", activeFilter);
        if (unreadOnly) params.set("unread_only", "true");
        params.set("limit", String(pageSize));
        params.set("offset", String(page * pageSize));
        const notificationsPath = params.toString()
          ? `/api/notifications?${params.toString()}`
          : "/api/notifications";

        const [resNotifications, resCounts, resUnreadCounts] = await Promise.all([
          fetch(notificationsPath, {
            headers: { Authorization: "Bearer " + token },
          }),
          fetch("/api/notifications/counts", {
            headers: { Authorization: "Bearer " + token },
          }),
          fetch("/api/notifications/counts?unread_only=true", {
            headers: { Authorization: "Bearer " + token },
          }),
        ]);
        if (resNotifications.status === 401) {
          navigate("/login");
          return;
        }
        if (!resNotifications.ok) {
          const data = await resNotifications.json().catch(() => ({}));
          throw new Error(
            data.detail || t({ ja: "通知の取得に失敗しました", en: "Failed to load notifications." })
          );
        }
        const items = await resNotifications.json();
        setNotifications(items || []);
        const countsData = await resCounts.json().catch(() => ({}));
        const unreadCountsData = await resUnreadCounts.json().catch(() => ({}));
        setCounts({
          all: Number(countsData?.all || 0),
          reaction: Number(countsData?.reaction || 0),
          follow: Number(countsData?.follow || 0),
          update: Number(countsData?.update || 0),
          system: Number(countsData?.system || 0),
        });
        setUnreadCountsByGroup({
          all: Number(unreadCountsData?.all || 0),
          reaction: Number(unreadCountsData?.reaction || 0),
          follow: Number(unreadCountsData?.follow || 0),
          update: Number(unreadCountsData?.update || 0),
          system: Number(unreadCountsData?.system || 0),
        });
        setUnreadCount(Number(unreadCountsData?.all || 0));
      } catch (e) {
        setError(
          getErrorMessage(e, t({ ja: "通知の取得に失敗しました", en: "Failed to load notifications." }))
        );
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [navigate, activeFilter, unreadOnly, page, pageSize, reloadTick, t]);

  const handleSave = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");

    try {
      const token = localStorage.getItem("token");
      if (!token) throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));

      const res = await fetch("/api/users/me", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        body: JSON.stringify({
          email_notifications_enabled: emailNotificationsEnabled,
        }),
      });

      if (res.status === 401) {
        navigate("/login");
        return;
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || t({ ja: "保存に失敗しました", en: "Failed to save." }));
      }

      setMessage(t({ ja: "保存しました。", en: "Saved." }));
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "保存に失敗しました", en: "Failed to save." })));
    } finally {
      setSaving(false);
    }
  };

  const handleMarkRead = async (notificationId: NotificationItem["id"]) => {
    try {
      const token = localStorage.getItem("token");
      if (!token) throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));
      const res = await fetch(`/api/notifications/${notificationId}/read`, {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || t({ ja: "既読に失敗しました", en: "Failed to mark as read." }));
      }
      setNotifications((prev) =>
        prev.map((n) =>
          n.id === notificationId ? { ...n, is_read: true } : n
        )
      );
      setReloadTick((v) => v + 1);
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "既読に失敗しました", en: "Failed to mark as read." })));
    }
  };

  const handleMarkAllRead = async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));
      const res = await fetch("/api/notifications/read_all", {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || t({ ja: "既読に失敗しました", en: "Failed to mark as read." }));
      }
      setReloadTick((v) => v + 1);
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "既読に失敗しました", en: "Failed to mark as read." })));
    }
  };

  const handleDelete = async (notificationId: NotificationItem["id"]) => {
    try {
      const token = localStorage.getItem("token");
      if (!token) throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));
      const res = await fetch(`/api/notifications/${notificationId}`, {
        method: "DELETE",
        headers: { Authorization: "Bearer " + token },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || t({ ja: "削除に失敗しました", en: "Failed to delete." }));
      }
      setReloadTick((v) => v + 1);
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "削除に失敗しました", en: "Failed to delete." })));
    }
  };

  const handleDeleteByType = async (notifType: "ai_generation_done" | "ai_generation_failed") => {
    try {
      const token = localStorage.getItem("token");
      if (!token) throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));
      setBulkDeletingType(notifType);
      setError("");
      setMessage("");
      const res = await fetch(`/api/notifications/type/${encodeURIComponent(notifType)}`, {
        method: "DELETE",
        headers: { Authorization: "Bearer " + token },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || t({ ja: "一括削除に失敗しました", en: "Failed to bulk delete." }));
      }
      const data = await res.json().catch(() => ({}));
      const deleted = Number(data?.deleted || 0);
      setMessage(
        notifType === "ai_generation_done"
          ? t(
              { ja: "成功通知を {{count}} 件削除しました。", en: "Deleted {{count}} success notifications." },
              { count: deleted }
            )
          : t(
              { ja: "失敗通知を {{count}} 件削除しました。", en: "Deleted {{count}} failure notifications." },
              { count: deleted }
            )
      );
      setPage(0);
      setReloadTick((v) => v + 1);
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "一括削除に失敗しました", en: "Failed to bulk delete." })));
    } finally {
      setBulkDeletingType("");
    }
  };

  const filterOptions: Array<{ key: NotificationGroup; label: string }> = [
    { key: "all", label: t({ ja: "すべて", en: "All" }) },
    { key: "reaction", label: t({ ja: "反応", en: "Reactions" }) },
    { key: "follow", label: t({ ja: "フォロー", en: "Follow" }) },
    { key: "update", label: t({ ja: "作品更新", en: "Updates" }) },
  ];
  const visibleTotal = unreadOnly
    ? Number(unreadCountsByGroup[activeFilter] || 0)
    : Number(counts[activeFilter] || 0);
  const maxPage = Math.max(0, Math.ceil(visibleTotal / Math.max(1, pageSize)) - 1);
  const canPrev = page > 0;
  const canNext = page < maxPage;
  const typeLabelMap: Record<NotificationType, string> = {
    user_follow: t({ ja: "フォロー", en: "Follow" }),
    followed_author_new_novel: t({ ja: "新作公開", en: "New novel" }),
    followed_author_new_episode: t({ ja: "新話公開", en: "New episode" }),
    tag_follow_new: t({ ja: "タグ新着", en: "Tag update" }),
    novel_like: t({ ja: "いいね", en: "Like" }),
    episode_like: t({ ja: "いいね", en: "Like" }),
    novel_comment: t({ ja: "コメント", en: "Comment" }),
    episode_comment: t({ ja: "コメント", en: "Comment" }),
    novel_favorite: t({ ja: "ブックマーク", en: "Bookmark" }),
    favorite_update: t({ ja: "更新", en: "Update" }),
    dm_message: t({ ja: "DM", en: "DM" }),
    recommended_novel_new: t({ ja: "おすすめ", en: "Recommended" }),
    ai_generation_done: t({ ja: "AI生成完了", en: "AI done" }),
    ai_generation_failed: t({ ja: "AI生成失敗", en: "AI failed" }),
    support_paid: t({ ja: "支援", en: "Support" }),
    membership_paid: t({ ja: "月額支援", en: "Membership" }),
    multilingual_ready: t({ ja: "翻訳対応", en: "Translation" }),
  };
  const aiDoneCount = notifications.filter((n) => n.type === "ai_generation_done").length;
  const aiFailedCount = notifications.filter((n) => n.type === "ai_generation_failed").length;
  const getTypeLabel = (type: string | null | undefined) => {
    const key = String(type || "").trim() as NotificationType | "";
    if (!key) return t({ ja: "通知", en: "Notice" });
    return key in typeLabelMap ? typeLabelMap[key as NotificationType] : key;
  };
  const resolveNotificationLink = (n: NotificationItem) => {
    const explicit = String(n?.link_url || "").trim();
    if (explicit) return explicit;
    const type = String(n?.type || "").trim();
    if (type === "user_follow" && n?.actor_username) {
      return `/users/${encodeURIComponent(n.actor_username)}`;
    }
    if (type === "dm_message") {
      return "/dms";
    }
    if (
      type === "followed_author_new_novel" ||
      type === "followed_author_new_episode" ||
      type === "tag_follow_new" ||
      type === "favorite_update" ||
      type === "recommended_novel_new"
    ) {
      return "/";
    }
    return "/notifications";
  };
  const getBodyText = (n: NotificationItem) => {
    const raw = String(n?.body || "").trim();
    if (raw) return raw;
    return t({ ja: "詳細は通知リンクから確認できます。", en: "Open the notification link for details." });
  };

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <h2 style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        {t({ ja: "通知センター", en: "Notifications" })}
        {unreadCount > 0 && (
          <span
            style={{
              display: "inline-block",
              minWidth: 22,
              textAlign: "center",
              padding: "2px 8px",
              borderRadius: "999px",
              backgroundColor: "var(--accent)",
              color: "var(--on-accent)",
              fontSize: 12,
              lineHeight: 1.4,
            }}
          >
            {unreadCount}
          </span>
        )}
      </h2>

      <section
        style={{
          marginTop: 16,
          padding: 12,
          border: "1px solid var(--border)",
          borderRadius: 8,
        }}
      >
        <h3 style={{ margin: 0, marginBottom: 8 }}>
          {t({ ja: "サイト内通知", en: "Site notifications" })}
        </h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
          {filterOptions.map((option) => (
            <button
              key={option.key}
              type="button"
              className="btn btn-border"
              onClick={() => {
                setActiveFilter(option.key);
                setPage(0);
              }}
              disabled={activeFilter === option.key}
            style={activeFilter === option.key ? { opacity: 0.7 } : undefined}
          >
              {option.label} ({counts[option.key] ?? 0})
            </button>
          ))}
          <button
            type="button"
            className="btn btn-border"
            onClick={() => {
              setUnreadOnly((prev) => !prev);
              setPage(0);
            }}
            style={unreadOnly ? { borderColor: "var(--cta)", color: "var(--cta)" } : undefined}
          >
            {unreadOnly
              ? t({ ja: "未読のみ: ON", en: "Unread only: ON" })
              : t({ ja: "未読のみ: OFF", en: "Unread only: OFF" })}
          </button>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 6, marginLeft: "auto" }}>
            <span style={{ fontSize: 12, color: "var(--muted-text)" }}>
              {t({ ja: "件数", en: "Per page" })}
            </span>
            <select
              className="search-input"
              value={pageSize}
              onChange={(e: ChangeEvent<HTMLSelectElement>) => {
                const next = Number(e.target.value || 50);
                setPageSize(next);
                setPage(0);
              }}
              style={{ width: 88, minWidth: 88 }}
            >
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </label>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={!canPrev}
          >
            {t({ ja: "前へ", en: "Prev" })}
          </button>
          <span style={{ fontSize: 12, color: "var(--muted-text)" }}>
            {t({ ja: "{{current}} / {{total}} ページ", en: "Page {{current}} / {{total}}" }, { current: page + 1, total: maxPage + 1 })}
          </span>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => setPage((p) => p + 1)}
            disabled={!canNext}
          >
            {t({ ja: "次へ", en: "Next" })}
          </button>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => handleDeleteByType("ai_generation_done")}
            disabled={bulkDeletingType !== "" || counts.all <= 0}
          >
            {bulkDeletingType === "ai_generation_done"
              ? t({ ja: "成功通知を削除中...", en: "Deleting success notifications..." })
              : t({ ja: "成功通知を消す", en: "Delete success notifications" })}
          </button>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => handleDeleteByType("ai_generation_failed")}
            disabled={bulkDeletingType !== "" || counts.all <= 0}
          >
            {bulkDeletingType === "ai_generation_failed"
              ? t({ ja: "失敗通知を削除中...", en: "Deleting failure notifications..." })
              : t({ ja: "失敗通知を消す", en: "Delete failure notifications" })}
          </button>
          <span style={{ fontSize: 12, color: "var(--muted-text)", alignSelf: "center" }}>
            {t(
              { ja: "このページ内: 成功 {{done}} 件 / 失敗 {{failed}} 件", en: "On this page: success {{done}} / failed {{failed}}" },
              { done: aiDoneCount, failed: aiFailedCount }
            )}
          </span>
        </div>
        {error && <p style={{ color: "red", marginTop: 0 }}>{error}</p>}
        {message && <p style={{ color: "green", marginTop: 0 }}>{message}</p>}
        {notifications.length === 0 ? (
          <p style={{ margin: 0, color: "var(--muted-text)" }}>
            {activeFilter === "all"
              ? t({ ja: "まだ通知はありません。", en: "No notifications yet." })
              : t({ ja: "この条件の通知はありません。", en: "No notifications for this filter." })}
          </p>
        ) : (
          <div>
            <button
              type="button"
              className="btn btn-border"
              onClick={handleMarkAllRead}
              style={{ marginBottom: 8 }}
            >
              {t({ ja: "すべて既読にする", en: "Mark all as read" })}
            </button>
            <div style={{ display: "grid", gap: 10 }}>
                  {notifications.map((n: NotificationItem) => (
                <div
                  key={n.id}
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    padding: 10,
                    backgroundColor: n.is_read ? "var(--surface)" : "var(--surface-2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>
                      {!n.is_read && (
                        <span
                          style={{
                            display: "inline-block",
                            marginRight: 6,
                            padding: "2px 6px",
                            borderRadius: 999,
                            backgroundColor: "var(--accent)",
                            color: "var(--on-accent)",
                            fontSize: 11,
                          }}
                        >
                          {t({ ja: "未読", en: "Unread" })}
                        </span>
                      )}
                      <span
                        style={{
                          display: "inline-block",
                          marginRight: 6,
                          padding: "2px 6px",
                          borderRadius: 999,
                          border: "1px solid var(--border)",
                          color: "var(--muted-text)",
                          fontSize: 11,
                        }}
                      >
                        {getTypeLabel(n.type)}
                      </span>
                      <Link to={resolveNotificationLink(n)}>{n.title}</Link>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--muted-text)" }}>
                      {n.created_at
                        ? formatDateTimeInUserTimeZone(n.created_at, lang === "en" ? "en-US" : "ja-JP")
                        : ""}
                    </div>
                  </div>
                  <p style={{ margin: "6px 0 0", whiteSpace: "pre-wrap" }}>
                    {n.actor_username ? (
                      <>
                        <strong>@{n.actor_username}</strong>{" "}
                      </>
                    ) : null}
                    {getBodyText(n)}
                  </p>
                  <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                    {!n.is_read && (
                      <button
                        type="button"
                        className="btn btn-border"
                        onClick={() => handleMarkRead(n.id)}
                      >
                        {t({ ja: "既読にする", en: "Mark as read" })}
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn-border"
                      onClick={() => handleDelete(n.id)}
                    >
                      {t({ ja: "削除", en: "Delete" })}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      <section
        style={{
          marginTop: 16,
          padding: 12,
          border: "1px solid var(--border)",
          borderRadius: 8,
        }}
      >
        <h3 style={{ margin: 0, marginBottom: 8 }}>
          {t({ ja: "メール通知", en: "Email notifications" })}
        </h3>
        <form onSubmit={handleSave}>
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              type="checkbox"
              checked={emailNotificationsEnabled}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setEmailNotificationsEnabled(e.target.checked)}
            />
            {t({ ja: "メール通知を受け取る", en: "Receive email notifications" })}
          </label>
          <div style={{ marginTop: 8, fontSize: 12, color: "var(--muted-text)" }}>
            {t({ ja: "アカウントに紐づいたメールに通知を送ります。", en: "Notifications will be sent to your account email." })}
          </div>
          {error && <p style={{ color: "red" }}>{error}</p>}
          {message && <p style={{ color: "green" }}>{message}</p>}
          <button className="btn btn-border" type="submit" disabled={saving}>
            {saving ? t({ ja: "保存中...", en: "Saving..." }) : t({ ja: "保存する", en: "Save" })}
          </button>
        </form>
      </section>
    </div>
  );
}
