import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useI18n } from "../lib/i18n";

const API_BASE = "";

export default function DirectMessageThread() {
  const { threadId } = useParams();
  const { t } = useI18n();
  const normalizedThreadId = useMemo(
    () => (threadId ? String(threadId).trim() : ""),
    [threadId]
  );

  const [thread, setThread] = useState(null);
  const [messages, setMessages] = useState([]);
  const [currentUserId, setCurrentUserId] = useState(null);
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchThread = async () => {
      const token =
        typeof window !== "undefined" ? localStorage.getItem("token") : null;
      if (!token) {
        setError(t({ ja: "ログインが必要です", en: "Login required." }));
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError("");
        const res = await fetch(`${API_BASE}/api/dms/${normalizedThreadId}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(
            data.detail || t({ ja: "DMの取得に失敗しました", en: "Failed to load DMs." })
          );
        }
        setThread(data.thread || null);
        setMessages(Array.isArray(data.messages) ? data.messages : []);
        setCurrentUserId(data.current_user_id ?? null);
      } catch (e) {
        console.error(e);
        setError(
          e.message || t({ ja: "エラーが発生しました", en: "An error occurred." })
        );
      } finally {
        setLoading(false);
      }
    };

    if (!normalizedThreadId) {
      setError(t({ ja: "DMが指定されていません", en: "No DM specified." }));
      setLoading(false);
      return;
    }

    fetchThread();
  }, [normalizedThreadId]);

  const handleSend = async (e) => {
    e.preventDefault();
    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      setError(t({ ja: "ログインが必要です", en: "Login required." }));
      return;
    }
    const trimmed = body.trim();
    if (!trimmed) return;

    try {
      setSending(true);
      setError("");
      const res = await fetch(
        `${API_BASE}/api/dms/${normalizedThreadId}/messages`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ body: trimmed }),
        }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "送信に失敗しました", en: "Failed to send." }));
      }
      setMessages((prev) => [...prev, data]);
      setBody("");
    } catch (e) {
      console.error(e);
      setError(
        e.message || t({ ja: "エラーが発生しました", en: "An error occurred." })
      );
    } finally {
      setSending(false);
    }
  };

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">{t({ ja: "← トップに戻る", en: "← Back to Home" })}</Link>
      </div>

      {error && (
        <p style={{ color: "red", marginBottom: 12 }}>{error}</p>
      )}

      <h2 style={{ marginBottom: "1rem" }}>
        {thread?.partner_username
          ? t(
              { ja: "{{name}} とのDM", en: "DM with {{name}}" },
              { name: thread.partner_username }
            )
          : t({ ja: "DM", en: "Direct Messages" })}
      </h2>

      <div
        style={{
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: 12,
          minHeight: 240,
          backgroundColor: "#fff",
          marginBottom: 16,
        }}
      >
        {messages.length === 0 ? (
          <p style={{ color: "var(--muted-text)" }}>
            {t({ ja: "まだメッセージがありません。", en: "No messages yet." })}
          </p>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {messages.map((msg) => (
              <div
                key={msg.id}
                style={{
                  padding: "8px 10px",
                  borderRadius: 8,
                  backgroundColor: "var(--novel-card-bg)",
                  border: "1px solid var(--novel-card-border)",
                }}
              >
                <div style={{ fontSize: 12, color: "var(--muted-text)" }}>
                  {msg.sender_username || t({ ja: "ユーザー", en: "User" })} /{" "}
                  {msg.created_at
                    ? new Date(msg.created_at).toLocaleString()
                    : ""}
                  {currentUserId && msg.sender_id === currentUserId && (
                    <span style={{ marginLeft: 8 }}>
                      {msg.is_read ? t({ ja: "既読", en: "Read" }) : t({ ja: "未読", en: "Unread" })}
                    </span>
                  )}
                </div>
                <div style={{ whiteSpace: "pre-wrap", marginTop: 4 }}>
                  {msg.body}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <form onSubmit={handleSend} style={{ display: "grid", gap: 8 }}>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={4}
          placeholder={t({ ja: "メッセージを入力", en: "Type a message" })}
          style={{
            width: "100%",
            padding: 10,
            borderRadius: 6,
            border: "1px solid var(--border)",
            resize: "vertical",
          }}
        />
        <button type="submit" disabled={sending || !body.trim()}>
          {sending ? t({ ja: "送信中...", en: "Sending..." }) : t({ ja: "送信", en: "Send" })}
        </button>
      </form>
    </div>
  );
}
