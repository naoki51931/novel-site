import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";

const API_BASE = "";

export default function NovelDetail() {
  const { id } = useParams(); // novel_id
  const navigate = useNavigate();

  const [novel, setNovel] = useState(null);
  const [episodes, setEpisodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // いいね・閲覧数（あれば使う）
  const [likeCount, setLikeCount] = useState(0);
  const [viewCount, setViewCount] = useState(0);
  const [isLiked, setIsLiked] = useState(false);

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString("ja-JP");
  };

  const fetchDetail = async () => {
    try {
      setLoading(true);
      setError("");

      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};

      // 小説詳細
      const res = await fetch(API_BASE + `/api/novels/${id}`, {
        headers,
      });
      if (!res.ok) {
        throw new Error(`小説詳細の取得に失敗しました (${res.status})`);
      }
      const data = await res.json();
      setNovel(data);

      if (typeof data.like_count === "number") setLikeCount(data.like_count);
      if (typeof data.view_count === "number") setViewCount(data.view_count);
      if (typeof data.is_liked === "boolean") setIsLiked(data.is_liked);

      // エピソード一覧
      const resEp = await fetch(API_BASE + `/api/novels/${id}/episodes`, {
        headers,
      });
      if (!resEp.ok) {
        throw new Error(`エピソード一覧の取得に失敗しました (${resEp.status})`);
      }
      const eps = await resEp.json();
      setEpisodes(Array.isArray(eps) ? eps : []);
    } catch (e) {
      console.error(e);
      setError(e.message || "小説詳細の取得中にエラーが発生しました");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [id]);

  // 小説削除
  const handleDeleteNovel = async () => {
    if (!window.confirm("この小説と全エピソードを削除します。よろしいですか？")) {
      return;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      alert("削除するにはログインが必要です。");
      navigate("/login");
      return;
    }

    try {
      const res = await fetch(API_BASE + `/api/novels/${id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || "小説の削除に失敗しました");
      }

      alert("小説を削除しました。");
      navigate("/");
    } catch (e) {
      console.error(e);
      alert(e.message || "小説削除中にエラーが発生しました");
    }
  };

  // エピソード削除
  const handleDeleteEpisode = async (episodeId) => {
    if (!window.confirm("このエピソードを削除します。よろしいですか？")) {
      return;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      alert("削除するにはログインが必要です。");
      navigate("/login");
      return;
    }

    try {
      const res = await fetch(API_BASE + `/api/episodes/${episodeId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || "エピソードの削除に失敗しました");
      }

      // ローカル状態更新
      setEpisodes((prev) => prev.filter((ep) => ep.id !== episodeId));
      alert("エピソードを削除しました。");
    } catch (e) {
      console.error(e);
      alert(e.message || "エピソード削除中にエラーが発生しました");
    }
  };

  if (loading) {
    return <div>読み込み中...</div>;
  }

  if (error) {
    return (
      <div>
        <p style={{ color: "red" }}>{error}</p>
        <button className="btn btn-border" onClick={() => navigate(-1)}>
          戻る
        </button>
      </div>
    );
  }

  if (!novel) {
    return (
      <div>
        <p>小説が見つかりませんでした。</p>
        <button className="btn btn-border" onClick={() => navigate(-1)}>
          戻る
        </button>
      </div>
    );
  }

  const tags = Array.isArray(novel.tags) ? novel.tags : [];

  return (
    <div>
      <button className="btn btn-border" onClick={() => navigate(-1)}>
        ← 一覧に戻る
      </button>

      <h2 style={{ marginTop: 12 }}>{novel.title}</h2>

      <div style={{ marginBottom: 8, color: "#666", fontSize: "0.9rem" }}>
        <div>作者: {novel.author_username || "不明"}</div>
        {novel.created_at && (
          <div>作成日時: {formatDateTime(novel.created_at)}</div>
        )}
        <div>閲覧数: {viewCount}</div>
        <div>いいね: {likeCount}</div>
      </div>

      {tags.length > 0 && (
        <div style={{ marginBottom: 8 }}>
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
        </div>
      )}

      <p style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>{novel.description}</p>

      {/* 小説 編集・削除 ボタン */}
      <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
        <Link to={`/novels/${novel.id}/edit`} className="btn btn-border">
          小説を編集
        </Link>
        <button type="button" className="btn btn-border" onClick={handleDeleteNovel}>
          小説を削除
        </button>
      </div>

      <hr style={{ margin: "24px 0" }} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>エピソード一覧</h3>
        <Link to={`/novels/${novel.id}/episodes/new`} className="btn btn-border">
          新しいエピソードを追加
        </Link>
      </div>

      {episodes.length === 0 ? (
        <p>まだエピソードがありません。</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {episodes.map((ep) => (
            <li
              key={ep.id}
              style={{
                border: "1px solid #eee",
                borderRadius: 8,
                padding: 8,
                marginBottom: 8,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Link to={`/episodes/${ep.id}`}>
                  第{ep.number || ep.episode_number}話 {ep.title}
                </Link>

                <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                  <Link
                    to={`/episodes/${ep.id}/edit`}
                    className="btn btn-border"
                    style={{ padding: "2px 8px", fontSize: "0.8rem" }}
                  >
                    編集
                  </Link>
                  <button
                    type="button"
                    className="btn btn-border"
                    style={{ padding: "2px 8px", fontSize: "0.8rem" }}
                    onClick={() => handleDeleteEpisode(ep.id)}
                  >
                    削除
                  </button>
                </div>
              </div>

              <div style={{ fontSize: "0.8rem", color: "#666" }}>
                作成日時: {ep.created_at ? formatDateTime(ep.created_at) : "-"}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
