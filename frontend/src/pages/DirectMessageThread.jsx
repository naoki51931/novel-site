import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

const API_BASE = "";

export default function DirectMessageThread() {
  const { threadId } = useParams();
  const normalizedThreadId = useMemo(
    () => (threadId ? String(threadId).trim() : ""),
    [threadId]
  );

  const [thread, setThread] = useState(null);
  const [messages, setMessages] = useState([]);
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchThread = async () => {
      const token =
        typeof window !== "undefined" ? localStorage.getItem("token") : null;
      if (!token) {
        setError("ログインが必要です");
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
          throw new Error(data.detail || "DMの取得に失敗しました");
        }
        setThread(data.thread || null);
        setMessages(Array.isArray(data.messages) ? data.messages : []);
      } catch (e) {
        console.error(e);
        setError(e.message || "エラーが発生しました");
      } finally {
        setLoading(false);
      }
    };

    if (!normalizedThreadId) {
      setError("DMが指定されていません");
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
      setError("ログインが必要です");
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
        throw new Error(data.detail || "送信に失敗しました");
      }
      setMessages((prev) => [...prev, data]);
      setBody("");
    } catch (e) {
      console.error(e);
      setError(e.message || "エラーが発生しました");
    } finally {
      setSending(false);
    }
  };

  if (loading) return <p>読み込み中...</p>;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← トップに戻る</Link>
      </div>

      {error && (
        <p style={{ color: "red", marginBottom: 12 }}>{error}</p>
      )}

      <h2 style={{ marginBottom: "1rem" }}>
        {thread?.partner_username
          ? `${thread.partner_username} とのDM`
          : "DM"}
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
            まだメッセージがありません。
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
                  {msg.sender_username || "ユーザー"} /{" "}
                  {msg.created_at
                    ? new Date(msg.created_at).toLocaleString()
                    : ""}
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
          placeholder="メッセージを入力"
          style={{
            width: "100%",
            padding: 10,
            borderRadius: 6,
            border: "1px solid var(--border)",
            resize: "vertical",
          }}
        />
        <button type="submit" disabled={sending || !body.trim()}>
          {sending ? "送信中..." : "送信"}
        </button>
      </form>
    </div>
  );
}
