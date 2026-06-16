import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";

const API_BASE = getApiBase();

type DMListItem = {
  id: number | string;
  partner_username?: string | null;
  unread_count?: number | null;
  updated_at?: string | null;
  last_message?: {
    body?: string | null;
    created_at?: string | null;
    sender_username?: string | null;
  } | null;
};

export default function DirectMessages() {
  const navigate = useNavigate();
  const { t, lang } = useI18n();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [threads, setThreads] = useState<DMListItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      navigate("/login");
      return;
    }

    const load = async () => {
      try {
        setLoading(true);
        setError("");
        const res = await fetch(`${API_BASE}/api/dms`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json().catch(() => ({}));
        if (res.status === 401) {
          navigate("/login");
          return;
        }
        if (!res.ok) {
          throw new Error(
            data?.detail || t({ ja: "DM一覧の取得に失敗しました", en: "Failed to load DMs." })
          );
        }
        setThreads(Array.isArray(data?.threads) ? data.threads : []);
        setUnreadCount(Number(data?.unread_count || 0));
      } catch (e) {
        setError(
          getErrorMessage(e, t({ ja: "DM一覧の取得に失敗しました", en: "Failed to load DMs." }))
        );
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [navigate, t]);

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">{t({ ja: "← トップに戻る", en: "← Back to Home" })}</Link>
      </div>
      <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {t({ ja: "DM一覧", en: "Direct Messages" })}
        {unreadCount > 0 ? (
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
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        ) : null}
      </h2>
      {error && <p style={{ color: "red" }}>{error}</p>}
      {threads.length === 0 ? (
        <p style={{ color: "var(--muted-text)" }}>
          {t({ ja: "進行中のDMはありません。", en: "No direct messages yet." })}
        </p>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {threads.map((thread) => (
            <div
              key={thread.id}
              style={{
                border: "1px solid var(--border)",
                borderRadius: 10,
                padding: 12,
                background: "var(--surface)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  alignItems: "center",
                  marginBottom: 6,
                }}
              >
                <div style={{ fontWeight: 700 }}>
                  @{thread.partner_username || t({ ja: "不明なユーザー", en: "Unknown user" })}
                  {Number(thread.unread_count || 0) > 0 ? (
                    <span
                      style={{
                        marginLeft: 8,
                        fontSize: 12,
                        color: "var(--accent)",
                      }}
                    >
                      {t(
                        { ja: "未読 {{count}} 件", en: "{{count}} unread" },
                        { count: Number(thread.unread_count || 0) }
                      )}
                    </span>
                  ) : null}
                </div>
                <Link className="btn btn-border" to={`/dms/${thread.id}`}>
                  {t({ ja: "詳細", en: "Open" })}
                </Link>
              </div>
              <div style={{ fontSize: 12, color: "var(--muted-text)", marginBottom: 6 }}>
                {thread.updated_at
                  ? new Date(thread.updated_at).toLocaleString(lang === "en" ? "en-US" : "ja-JP", {
                      timeZone: "Asia/Tokyo",
                    })
                  : ""}
              </div>
              <div style={{ whiteSpace: "pre-wrap", color: "var(--text)" }}>
                {thread.last_message?.sender_username ? (
                  <strong>@{thread.last_message.sender_username}: </strong>
                ) : null}
                {thread.last_message?.body ||
                  t({ ja: "まだメッセージはありません。", en: "No messages yet." })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
