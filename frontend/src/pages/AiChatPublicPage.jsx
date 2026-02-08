import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";

export default function AiChatPublicPage() {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const search = async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.set("q", q.trim());
      params.set("limit", "50");
      const res = await fetch(`/api/ai/chat/public/characters?${params.toString()}`);
      const data = await res.json().catch(() => []);
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "公開チャット検索に失敗しました。", en: "Failed to search public chats." })
        );
      }
      setItems(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(
        e?.message ||
          t({ ja: "公開チャット検索中にエラーが発生しました。", en: "Failed to search public chats." })
      );
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (id) => {
    setSelectedId(id);
    setDetailLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/ai/chat/public/characters/${encodeURIComponent(id)}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "公開チャット詳細の取得に失敗しました。", en: "Failed to load public chat details." })
        );
      }
      setDetail(data);
    } catch (e) {
      setError(
        e?.message ||
          t({ ja: "公開チャット詳細の取得中にエラーが発生しました。", en: "Failed to load public chat details." })
      );
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    search();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ maxWidth: 980, margin: "0 auto" }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <Link to="/ai_chat" className="btn btn-border">{t({ ja: "AIチャットへ", en: "Go to AI Chat" })}</Link>
        <Link to="/" className="btn btn-border">{t({ ja: "トップへ", en: "Home" })}</Link>
      </div>

      <h2>{t({ ja: "公開チャット検索", en: "Public Chat Search" })}</h2>
      <p style={{ color: "#666" }}>
        {t({ ja: "キャラ名・性格で公開チャットを検索できます。", en: "Search public chats by character name or personality." })}
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") search();
          }}
          placeholder={t({ ja: "キャラ名 / 性格で検索", en: "Search by character name / personality" })}
          style={{ flex: 1 }}
        />
        <button type="button" className="btn btn-border" onClick={search} disabled={loading}>
          {loading ? t({ ja: "検索中...", en: "Searching..." }) : t({ ja: "検索", en: "Search" })}
        </button>
      </div>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      <div style={{ display: "grid", gap: 10, marginBottom: 14 }}>
        {items.length === 0 && (
          <p style={{ color: "#777" }}>
            {t({ ja: "公開中のチャットが見つかりません。", en: "No public chats found." })}
          </p>
        )}
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className="btn btn-border"
            onClick={() => loadDetail(item.id)}
            style={{
              textAlign: "left",
              padding: 10,
              borderColor: selectedId === item.id ? "#4a87c2" : undefined,
              background: selectedId === item.id ? "#eef6ff" : "#fff",
            }}
          >
            <div style={{ fontWeight: 800, fontSize: "1.2rem", lineHeight: 1.3 }}>
              {item.name || t({ ja: "無名", en: "Unnamed" })}
            </div>
            <div style={{ fontSize: "0.88rem", color: "#666" }}>
              @{item.author_username || "unknown"}
            </div>
            <div style={{ marginTop: 6, color: "#444", whiteSpace: "pre-wrap" }}>
              {item.personality || t({ ja: "性格設定なし", en: "No personality description" })}
            </div>
          </button>
        ))}
      </div>

      {detailLoading && <p>{t({ ja: "詳細読み込み中...", en: "Loading details..." })}</p>}
      {detail && !detailLoading && (
        <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
          <h3 style={{ marginTop: 0, fontSize: "1.5rem", lineHeight: 1.25 }}>{detail.name}</h3>
          <p style={{ color: "#666", marginTop: 0 }}>@{detail.author_username || "unknown"}</p>
          <p style={{ whiteSpace: "pre-wrap", color: "#444" }}>
            {detail.personality || t({ ja: "性格設定なし", en: "No personality description" })}
          </p>
          <div style={{ borderTop: "1px solid #eee", paddingTop: 10 }}>
            {(detail.messages || []).map((m, idx) => (
              <div key={`${m.id || idx}`} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: "0.82rem", color: "#666" }}>
                  {(m.role === "assistant"
                    ? detail.name || t({ ja: "AI", en: "AI" })
                    : t({ ja: "ユーザー", en: "User" })) + ` / ${m.mode || "say"}`}
                  {m?.is_auto_dialogue
                    ? ` ${t({ ja: "[自動会話]", en: "[Auto]" })}`
                    : ""}
                </div>
                <div style={{ whiteSpace: "pre-wrap" }}>{m.content || ""}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
