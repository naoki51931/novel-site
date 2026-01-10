import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useI18n } from "../lib/i18n";

export default function Notifications() {
  const navigate = useNavigate();
  const { t, lang } = useI18n();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [emailNotificationsEnabled, setEmailNotificationsEnabled] = useState(true);
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      navigate("/login");
      return;
    }

    const load = async () => {
      try {
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
        setEmailNotificationsEnabled(
          profile.email_notifications_enabled !== false
        );

        const resNotifications = await fetch("/api/notifications", {
          headers: { Authorization: "Bearer " + token },
        });
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
      } catch (e) {
        setError(
          e.message || t({ ja: "通知の取得に失敗しました", en: "Failed to load notifications." })
        );
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [navigate]);

  const handleSave = async (e) => {
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
      setError(e.message || t({ ja: "保存に失敗しました", en: "Failed to save." }));
    } finally {
      setSaving(false);
    }
  };

  const handleMarkRead = async (notificationId) => {
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
    } catch (e) {
      setError(e.message || t({ ja: "既読に失敗しました", en: "Failed to mark as read." }));
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
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch (e) {
      setError(e.message || t({ ja: "既読に失敗しました", en: "Failed to mark as read." }));
    }
  };

  const handleDelete = async (notificationId) => {
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
      setNotifications((prev) => prev.filter((n) => n.id !== notificationId));
    } catch (e) {
      setError(e.message || t({ ja: "削除に失敗しました", en: "Failed to delete." }));
    }
  };

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <h2>{t({ ja: "通知センター", en: "Notifications" })}</h2>

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
        {notifications.length === 0 ? (
          <p style={{ margin: 0, color: "var(--muted-text)" }}>
            {t({ ja: "まだ通知はありません。", en: "No notifications yet." })}
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
              {notifications.map((n) => (
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
                            backgroundColor: "#f0b400",
                            color: "#fff",
                            fontSize: 11,
                          }}
                        >
                          {t({ ja: "未読", en: "Unread" })}
                        </span>
                      )}
                      {n.link_url ? (
                        <Link to={n.link_url}>{n.title}</Link>
                      ) : (
                        n.title
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--muted-text)" }}>
                      {n.created_at
                        ? new Date(n.created_at).toLocaleString(lang === "en" ? "en-US" : "ja-JP")
                        : ""}
                    </div>
                  </div>
                  {n.body && (
                    <p style={{ margin: "6px 0 0", whiteSpace: "pre-wrap" }}>
                      {n.body}
                    </p>
                  )}
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
              onChange={(e) => setEmailNotificationsEnabled(e.target.checked)}
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
