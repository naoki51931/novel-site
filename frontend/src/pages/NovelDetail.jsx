import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

// JWT の payload を取り出す簡易デコーダ
function parseJwt(token) {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = atob(base64);
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export default function NovelDetail() {
  const { id } = useParams();
  const [novel, setNovel] = useState({ tags: [] });
  const [episodes, setEpisodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // ログイン情報
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const currentUsername =
    typeof window !== "undefined" ? localStorage.getItem("username") || null : null;

  let currentUserId = null;
  if (token) {
    const payload = parseJwt(token);
    if (payload && payload.sub) {
      currentUserId = Number(payload.sub);
    }
  }

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString("ja-JP");
  };

  const shorten = (text, max = 160) => {
    if (!text) return "";
    if (text.length <= max) return text;
    return text.slice(0, max) + "…";
  };

  const fetchData = async () => {
    try {
      setLoading(true);

      // 小説本体
      const novelRes = await fetch(`${API_BASE}/api/novels/${id}`);
      if (!novelRes.ok) {
        throw new Error("小説情報の取得に失敗しました");
      }
      const novelData = await novelRes.json();

      // エピソード一覧
      const epRes = await fetch(`${API_BASE}/api/novels/${id}/episodes`);
      if (!epRes.ok) {
        throw new Error("エピソード一覧の取得に失敗しました");
      }
      const epData = await epRes.json();

      const sortedEpisodes = (epData || []).slice().sort((a, b) => {
        const an = a.number || a.episode_number || 0;
        const bn = b.number || b.episode_number || 0;
        return an - bn;
      });

      setNovel(novelData);
      setEpisodes(sortedEpisodes);
    } catch (err) {
      console.error(err);
      alert(err.message || "小説の読み込みに失敗しました。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // ✅ 作者判定ロジック（author_id or author_username どちらでも判定）
  const isOwner =
    novel &&
    (
      (currentUserId != null && novel.author_id != null &&
        Number(novel.author_id) === Number(currentUserId)) ||
      (novel.author_username &&
        currentUsername &&
        novel.author_username === currentUsername)
    );

  // 小説削除
  const handleDeleteNovel = async () => {
    if (!window.confirm("この小説を削除しますか？\n（全エピソードも削除されます）")) {
      return;
    }

    if (!token) {
      alert("削除にはログインが必要です。");
      navigate("/login");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/novels/${id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "小説の削除に失敗しました。");
      }

      alert("小説を削除しました。");
      navigate("/");
    } catch (err) {
      console.error(err);
      alert(err.message || "削除に失敗しました。");
    }
  };

  // エピソード削除
  const handleDeleteEpisode = async (episodeId) => {
    if (!window.confirm("このエピソードを削除しますか？")) {
      return;
    }

    if (!token) {
      alert("削除にはログインが必要です。");
      navigate("/login");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/episodes/${episodeId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "エピソードの削除に失敗しました。");
      }

      await fetchData();
    } catch (err) {
      console.error(err);
      alert(err.message || "削除に失敗しました。");
    }
  };

  if (loading) return <p>読み込み中...</p>;
  if (!novel) return <p>小説が見つかりませんでした。</p>;
  const tags = Array.isArray(novel.tags) ? novel.tags : [];


  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← 一覧に戻る</Link>
      </div>

      <h2 style={{ marginBottom: 8 }}>{novel.title}</h2>

	{tags.map((t) => (
          <span
            key={t.id}
              style={{
              display: "inline-block",
              marginRight: 4,
              padding: "2px 8px",
              borderRadius: 12,
              border: "1px solid #ccc",
              fontSize: "0.85rem",
             }}
           >
            #{t.name}
          </span>
         ))}

        {novel.description && (
        <p
          style={{
            whiteSpace: "pre-wrap",
            marginBottom: 12,
          }}
        >
          {novel.description}
        </p>
      )}

      <div style={{ fontSize: 12, color: "#555", marginBottom: 16 }}>
        <div>
          作者:{" "}
          {novel.author_username
            ? novel.author_username
            : novel.author_id
            ? `ユーザーID: ${novel.author_id}`
            : "不明"}
        </div>
        <div>作成日時: {formatDateTime(novel.created_at)}</div>
      </div>

      <div
        style={{
          marginBottom: 16,
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <button
          className="btn btn-border"
          onClick={() => navigate(`/novels/${id}/episodes/new`)}
        >
          この小説にエピソードを追加
        </button>

        {isOwner && (
          <>
            <button
              className="btn btn-border"
              onClick={() => navigate(`/novels/${id}/edit`)}
            >
              この小説を編集
            </button>
            <button
              className="btn btn-border"
              type="button"
              onClick={handleDeleteNovel}
            >
              この小説を削除
            </button>
          </>
        )}
      </div>

      <h3 style={{ marginBottom: 8 }}>エピソード一覧</h3>
      {episodes.length === 0 && <p>まだエピソードがありません。</p>}

      <ul style={{ listStyle: "none", paddingLeft: 0, marginTop: 8 }}>
        {episodes.map((ep) => (
          <li
            key={ep.id}
            style={{
              border: "1px solid #ddd",
              borderRadius: 8,
              padding: 10,
              marginBottom: 10,
              boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
              backgroundColor: "#fff",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                gap: 8,
                marginBottom: 4,
              }}
            >
              <strong>
                第{ep.number || ep.episode_number}話 {ep.title}
              </strong>
              <span style={{ fontSize: 12, color: "#666" }}>
                投稿日時: {formatDateTime(ep.created_at)}
              </span>
            </div>

            <div
              style={{
                whiteSpace: "pre-wrap",
                fontSize: 14,
                color: "#444",
                marginBottom: 8,
              }}
            >
              {shorten(ep.body, 160)}
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              <Link to={`/episodes/${ep.id}`} className="btn btn-border">
                このエピソードを読む
              </Link>

              {isOwner && (
                <>
                  <Link
                    to={`/episodes/${ep.id}/edit`}
                    className="btn btn-border"
                  >
                    編集
                  </Link>
                  <button
                    className="btn btn-border"
                    type="button"
                    onClick={() => handleDeleteEpisode(ep.id)}
                  >
                    削除
                  </button>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
