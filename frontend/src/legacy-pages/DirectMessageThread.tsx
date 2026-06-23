import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";
import { formatDateTimeInUserTimeZone } from "../lib/timezone";

const API_BASE = getApiBase();

type DirectMessageThreadInfo = {
  partner_username?: string | null;
};

type DirectMessage = {
  id: number | string;
  sender_username?: string | null;
  created_at?: string | null;
  body?: string | null;
  sender_id?: number | string | null;
  is_read?: boolean | null;
};

export default function DirectMessageThread() {
  const { threadId } = useParams();
  const { t, lang } = useI18n();
  const normalizedThreadId = useMemo(
    () => (threadId ? String(threadId).trim() : ""),
    [threadId]
  );

  const [thread, setThread] = useState<DirectMessageThreadInfo | null>(null);
  const [messages, setMessages] = useState<DirectMessage[]>([]);
  const [currentUserId, setCurrentUserId] = useState<number | string | null>(null);
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
        setError(getErrorMessage(e, t({ ja: "エラーが発生しました", en: "An error occurred." })));
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

  const handleSend = async (e: FormEvent<HTMLFormElement>) => {
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
      setMessages((prev: DirectMessage[]) => [...prev, data as DirectMessage]);
      setBody("");
    } catch (e) {
      console.error(e);
      setError(getErrorMessage(e, t({ ja: "エラーが発生しました", en: "An error occurred." })));
    } finally {
      setSending(false);
    }
  };

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/dms">{t({ ja: "← DM一覧に戻る", en: "← Back to DMs" })}</Link>
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
            {messages.map((msg: DirectMessage) => (
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
                    ? formatDateTimeInUserTimeZone(msg.created_at, lang === "en" ? "en-US" : "ja-JP")
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
