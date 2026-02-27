import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useI18n } from "../lib/i18n";

function slugifyCharacterName(name) {
  return String(name || "")
    .normalize("NFKC")
    .trim()
    .toLowerCase()
    .replace(/[\s_]+/g, "-")
    .replace(/[^a-z0-9\u3040-\u30ff\u3400-\u9fff-]/g, "")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function buildPublicCharacterPath(id, name) {
  const slug = slugifyCharacterName(name) || "character";
  return `/ai_chat/public/${encodeURIComponent(id)}/${encodeURIComponent(slug)}`;
}

export default function AiChatPublicPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const { characterId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const qFromUrl = (searchParams.get("q") || "").trim();
  const [q, setQ] = useState(qFromUrl);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const getAuthHeaders = () => {
    try {
      const token = localStorage.getItem("token") || localStorage.getItem("access_token");
      return token ? { Authorization: `Bearer ${token}` } : {};
    } catch {
      return {};
    }
  };
  const hasAuthToken = () => {
    try {
      return !!(localStorage.getItem("token") || localStorage.getItem("access_token"));
    } catch {
      return false;
    }
  };

  const buildUrlSearch = (query) => {
    const params = new URLSearchParams(searchParams.toString());
    const normalized = String(query || "").trim();
    if (normalized) params.set("q", normalized);
    else params.delete("q");
    return params.toString();
  };

  const search = async ({ query = q, syncUrl = true } = {}) => {
    const normalizedQuery = String(query || "").trim();
    if (syncUrl) {
      const next = new URLSearchParams(searchParams.toString());
      if (normalizedQuery) next.set("q", normalizedQuery);
      else next.delete("q");
      setSearchParams(next);
      if (normalizedQuery !== qFromUrl) return;
    }
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (normalizedQuery) params.set("q", normalizedQuery);
      params.set("limit", "50");
      const res = await fetch(`/api/ai/chat/public/characters?${params.toString()}`, {
        headers: getAuthHeaders(),
      });
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

  const loadDetail = async (id, { name = "", syncUrl = true } = {}) => {
    setSelectedId(id);
    setDetailLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/ai/chat/public/characters/${encodeURIComponent(id)}`, {
        headers: getAuthHeaders(),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "公開チャット詳細の取得に失敗しました。", en: "Failed to load public chat details." })
        );
      }
      setDetail(data);
      const query = buildUrlSearch(q);
      const targetPathBase = buildPublicCharacterPath(id, data?.name || name);
      const targetPath = query ? `${targetPathBase}?${query}` : targetPathBase;
      if (syncUrl) {
        navigate(targetPath);
      } else if (`${location.pathname}${location.search}` !== targetPath) {
        navigate(targetPath, { replace: true });
      }
    } catch (e) {
      setError(
        e?.message ||
          t({ ja: "公開チャット詳細の取得中にエラーが発生しました。", en: "Failed to load public chat details." })
      );
    } finally {
      setDetailLoading(false);
    }
  };

  const applySocialState = (id, patch) => {
    setItems((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)));
    setDetail((prev) => (prev && prev.id === id ? { ...prev, ...patch } : prev));
  };

  const toggleLike = async () => {
    if (!detail?.id) return;
    if (!hasAuthToken()) {
      alert(t({ ja: "いいねするにはログインが必要です。", en: "Login required to like." }));
      return;
    }
    const id = Number(detail.id);
    const prevLiked = !!detail.is_liked;
    const prevCount = Number(detail.like_count || 0);
    const optimistic = prevLiked
      ? { is_liked: false, like_count: Math.max(0, prevCount - 1) }
      : { is_liked: true, like_count: prevCount + 1 };
    applySocialState(id, optimistic);
    try {
      const res = await fetch(`/api/ai/chat/public/characters/${encodeURIComponent(id)}/like`, {
        method: prevLiked ? "DELETE" : "POST",
        headers: getAuthHeaders(),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail || t({ ja: "いいね操作に失敗しました。", en: "Failed to like." })
        );
      }
      applySocialState(id, {
        is_liked: typeof data?.liked === "boolean" ? data.liked : !prevLiked,
        like_count:
          typeof data?.like_count === "number" ? data.like_count : optimistic.like_count,
      });
    } catch (e) {
      applySocialState(id, { is_liked: prevLiked, like_count: prevCount });
      alert(e?.message || t({ ja: "いいね操作中にエラーが発生しました。", en: "An error occurred while liking." }));
    }
  };

  const toggleFavorite = async () => {
    if (!detail?.id) return;
    if (!hasAuthToken()) {
      alert(t({ ja: "ブックマークするにはログインが必要です。", en: "Login required to bookmark." }));
      return;
    }
    const id = Number(detail.id);
    const prevFavorited = !!detail.is_favorited;
    const prevCount = Number(detail.favorite_count || 0);
    const optimistic = prevFavorited
      ? { is_favorited: false, favorite_count: Math.max(0, prevCount - 1) }
      : { is_favorited: true, favorite_count: prevCount + 1 };
    applySocialState(id, optimistic);
    try {
      const res = await fetch(`/api/ai/chat/public/characters/${encodeURIComponent(id)}/favorite`, {
        method: prevFavorited ? "DELETE" : "POST",
        headers: getAuthHeaders(),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail || t({ ja: "ブックマーク操作に失敗しました。", en: "Failed to bookmark." })
        );
      }
      applySocialState(id, {
        is_favorited: typeof data?.favorited === "boolean" ? data.favorited : !prevFavorited,
        favorite_count:
          typeof data?.favorite_count === "number" ? data.favorite_count : optimistic.favorite_count,
      });
    } catch (e) {
      applySocialState(id, { is_favorited: prevFavorited, favorite_count: prevCount });
      alert(
        e?.message ||
          t({ ja: "ブックマーク操作中にエラーが発生しました。", en: "An error occurred while bookmarking." })
      );
    }
  };

  useEffect(() => {
    setQ(qFromUrl);
    search({ query: qFromUrl, syncUrl: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qFromUrl]);

  useEffect(() => {
    if (!characterId) {
      setSelectedId(null);
      setDetail(null);
      return;
    }
    const parsedId = Number(characterId);
    if (!Number.isFinite(parsedId) || parsedId <= 0) return;
    loadDetail(parsedId, { syncUrl: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [characterId]);

  return (
    <div style={{ maxWidth: 980, margin: "0 auto" }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <Link to="/ai_chat" className="btn btn-border">{t({ ja: "AIチャットへ", en: "Go to AI Chat" })}</Link>
        <Link to="/" className="btn btn-border">{t({ ja: "トップへ", en: "Home" })}</Link>
      </div>

      <h2>{t({ ja: "公開チャット検索", en: "Public Chat Search" })}</h2>
      <p style={{ color: "#666" }}>
        {t({
          ja: "他ユーザーが公開したAIキャラクターを探せるページです。気になるキャラクターは詳細を見て、そのまま会話を始められます。",
          en: "This page helps you find AI characters shared by other users. Check details and start chatting right away.",
        })}
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") search({ query: q, syncUrl: true });
          }}
          placeholder={t({ ja: "キャラ名 / 性格で検索", en: "Search by character name / personality" })}
          style={{ flex: 1 }}
        />
        <button type="button" className="btn btn-border" onClick={() => search({ query: q, syncUrl: true })} disabled={loading}>
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
            className="btn btn-border public-chat-character-card"
            onClick={() => loadDetail(item.id, { name: item.name, syncUrl: true })}
            style={{
              textAlign: "left",
              padding: 10,
              borderColor: selectedId === item.id ? "#4a87c2" : undefined,
              background: selectedId === item.id ? "#eef6ff" : "#fff",
            }}
          >
            <div style={{ fontWeight: 800, fontSize: "1.2rem", lineHeight: 1.3, color: "var(--text)" }}>
              {item.name || t({ ja: "無名", en: "Unnamed" })}
            </div>
            <div style={{ fontSize: "0.88rem", color: "#666" }}>
              @{item.author_username || "unknown"}
            </div>
            <div style={{ marginTop: 6, color: "#444", whiteSpace: "pre-wrap" }}>
              {item.personality || t({ ja: "性格設定なし", en: "No personality description" })}
            </div>
            <div style={{ marginTop: 8, fontSize: "0.86rem", color: "#666" }}>
              <span style={{ marginRight: 10 }}>
                {t({ ja: "いいね", en: "Likes" })}: {item.like_count ?? 0}
              </span>
              <span>
                {t({ ja: "ブックマーク", en: "Bookmarks" })}: {item.favorite_count ?? 0}
              </span>
            </div>
          </button>
        ))}
      </div>

      {detailLoading && <p>{t({ ja: "詳細読み込み中...", en: "Loading details..." })}</p>}
      {detail && !detailLoading && (
        <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
          <h3 style={{ marginTop: 0, fontSize: "1.5rem", lineHeight: 1.25 }}>{detail.name}</h3>
          <div style={{ marginBottom: 8 }}>
            <Link
              to={`${buildPublicCharacterPath(detail.id, detail.name)}${buildUrlSearch(q) ? `?${buildUrlSearch(q)}` : ""}`}
              className="btn btn-border"
            >
              {t({ ja: "この公開チャットへのリンク", en: "Link to this public chat" })}
            </Link>
            <Link
              to="/ai_chat"
              className="btn btn-border"
              style={{ marginLeft: 8 }}
              state={{
                source: "public_chat_character",
                characterId: detail.id,
                prefillCharacterName: detail.name || "",
                prefillPersonality: detail.personality || "",
              }}
            >
              {t({ ja: "このキャラでAIチャットを開始", en: "Start AI chat with this character" })}
            </Link>
          </div>
          <div style={{ marginBottom: 8 }}>
            <button type="button" className="btn btn-border" onClick={toggleLike}>
              {detail.is_liked
                ? t({ ja: "♥ いいね済み", en: "♥ Liked" })
                : t({ ja: "♡ いいね", en: "♡ Like" })}{" "}
              ({detail.like_count ?? 0})
            </button>
            <button type="button" className="btn btn-border" onClick={toggleFavorite} style={{ marginLeft: 8 }}>
              {detail.is_favorited
                ? t({ ja: "★ ブックマーク済み", en: "★ Bookmarked" })
                : t({ ja: "☆ ブックマーク", en: "☆ Bookmark" })}{" "}
              ({detail.favorite_count ?? 0})
            </button>
          </div>
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
