import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";

const API_BASE = "";

export default function NovelDetail() {
  const { id } = useParams(); // novel_id
  const navigate = useNavigate();

  const [novel, setNovel] = useState(null);
  const authorName = novel?.author_username;
  const [isFavorited, setIsFavorited] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // ★ いいね / 閲覧数
  const [likeCount, setLikeCount] = useState(0);
  const [isLiked, setIsLiked] = useState(false);

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString("ja-JP");
  };

  const AGE_LABELS = {
    all: "全年齢",
    r15: "R15",
    r18: "R18",
  };

  const getAgeLabel = (ageLimit) => {
    if (!ageLimit) return "全年齢";
    return AGE_LABELS[ageLimit] ?? ageLimit;
  };


  const toggleFavorite = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      alert("お気に入りにするにはログインが必要です。");
      navigate("/login");
      return;
    }
    if (!novel) return;

    const method = isFavorited ? "DELETE" : "POST";

    try {
      const res = await fetch(API_BASE + "/api/novels/" + novel.id + "/favorite", {
        method,
        headers: {
          Authorization: "Bearer " + token,
        },
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || "お気に入りの操作に失敗しました");
      }

      if (typeof data.favorited === "boolean") {
        setIsFavorited(data.favorited);
      } else {
        setIsFavorited((prev) => !prev);
      }
    } catch (e) {
      console.error(e);
      alert(e.message || "お気に入り操作中にエラーが発生しました");
    }
  };

  useEffect(() => {
    const fetchNovel = async () => {
      try {
        setLoading(true);
        setError("");

        const token = localStorage.getItem("token");
  const toggleFavorite = async () => {
    if (!token) {
      alert("ログインが必要です");
      return;
    }
    if (!novel) return;
    const method = isFavorited ? "DELETE" : "POST";
    try {
      const res = await fetch(`${API_BASE}/api/novels/${novel.id}/favorite`, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        console.error("favorite toggle failed");
        return;
      }
      const data = await res.json();
      setIsFavorited(!!data.favorited);
    } catch (e) {
      console.error(e);
    }
  };
        const res = await fetch(`${API_BASE}/api/novels/${id}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });

        if (!res.ok) {
          throw new Error(`小説の取得に失敗しました (${res.status})`);
        }

        const data = await res.json();
        console.log("NOVEL DATA:", data);
        setNovel(data);
        setIsFavorited(!!data.is_favorited);

        // ★ いいね / 閲覧数
        if (typeof data.like_count === "number") {
          setLikeCount(data.like_count);
        }
        if (typeof data.is_liked === "boolean") {
          setIsLiked(data.is_liked);
        }
      } catch (e) {
        console.error(e);
        setError(e.message || "小説の取得中にエラーが発生しました");
      } finally {
        setLoading(false);
      }
    };

    fetchNovel();
  }, [id]);

  // ★ 小説 いいねトグル
  const handleToggleLike = async () => {
    const token = localStorage.getItem("token");
  const toggleFavorite = async () => {
    if (!token) {
      alert("ログインが必要です");
      return;
    }
    if (!novel) return;
    const method = isFavorited ? "DELETE" : "POST";
    try {
      const res = await fetch(`${API_BASE}/api/novels/${novel.id}/favorite`, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        console.error("favorite toggle failed");
        return;
      }
      const data = await res.json();
      setIsFavorited(!!data.favorited);
    } catch (e) {
      console.error(e);
    }
  };
    if (!token) {
      alert("いいねするにはログインが必要です。");
      navigate("/login");
      return;
    }

    const method = isLiked ? "DELETE" : "POST";
    const endpoint = `/api/novels/${id}/like`;

    try {
      const res = await fetch(API_BASE + endpoint, {
        method,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || "いいね操作に失敗しました");
      }

      if (typeof data.like_count === "number") {
        setLikeCount(data.like_count);
      } else {
        setLikeCount((prev) => prev + (isLiked ? -1 : 1));
      }
      setIsLiked((prev) => !prev);
    } catch (e) {
      console.error(e);
      alert(e.message || "いいね操作中にエラーが発生しました");
    }
  };

  // ★ 小説編集ボタン
  const handleEditNovel = () => {
    navigate(`/novels/${id}/edit`);
  };

  // ★ 小説削除ボタン
  const handleDeleteNovel = async () => {
    if (!window.confirm("この小説と全エピソードを削除します。よろしいですか？")) {
      return;
    }
    const token = localStorage.getItem("token");
  const toggleFavorite = async () => {
    if (!token) {
      alert("ログインが必要です");
      return;
    }
    if (!novel) return;
    const method = isFavorited ? "DELETE" : "POST";
    try {
      const res = await fetch(`${API_BASE}/api/novels/${novel.id}/favorite`, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        console.error("favorite toggle failed");
        return;
      }
      const data = await res.json();
      setIsFavorited(!!data.favorited);
    } catch (e) {
      console.error(e);
    }
  };
    if (!token) {
      alert("削除するにはログインが必要です。");
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

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || "小説の削除に失敗しました");
      }

      alert("小説を削除しました。");
      navigate("/");
    } catch (e) {
      console.error(e);
      alert(e.message || "削除中にエラーが発生しました");
    }
  };

  // ★ エピソード編集ボタン
  const handleEditEpisode = (episodeId) => {
    navigate(`/episodes/${episodeId}/edit`);
  };

  // ★ エピソード削除ボタン
  // ★ 新規エピソード作成ボタン
  const handleCreateEpisode = () => {
    navigate(`/novels/${id}/episodes/new`);
  };

  const handleDeleteEpisode = async (episodeId) => {
    if (!window.confirm("このエピソードを削除します。よろしいですか？")) {
      return;
    }

    const token = localStorage.getItem("token");
  const toggleFavorite = async () => {
    if (!token) {
      alert("ログインが必要です");
      return;
    }
    if (!novel) return;
    const method = isFavorited ? "DELETE" : "POST";
    try {
      const res = await fetch(`${API_BASE}/api/novels/${novel.id}/favorite`, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        console.error("favorite toggle failed");
        return;
      }
      const data = await res.json();
      setIsFavorited(!!data.favorited);
    } catch (e) {
      console.error(e);
    }
  };
    if (!token) {
      alert("削除するにはログインが必要です。");
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

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || "エピソードの削除に失敗しました");
      }

      // ローカル状態からも削除
      setNovel((prev) => {
        if (!prev) return prev;
        const eps = Array.isArray(prev.episodes) ? prev.episodes : [];
        return {
          ...prev,
          episodes: eps.filter((ep) => ep.id !== episodeId),
        };
      });

      alert("エピソードを削除しました。");
    } catch (e) {
      console.error(e);
      alert(e.message || "削除中にエラーが発生しました");
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

  const episodes = Array.isArray(novel.episodes) ? novel.episodes : [];
  const tags = Array.isArray(novel.tags) ? novel.tags : [];

  return (
    <div>
      <button className="btn btn-border" onClick={() => navigate(-1)}>
        ← 一覧に戻る
      </button>

      <div
        style={{
          marginTop: 12,
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <h2 style={{ margin: 0 }}>{novel.title}</h2>

        {/* 小説編集・削除ボタン */}
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button
            type="button"
            className="btn btn-border"
            onClick={handleEditNovel}
          >
            小説を編集
          </button>
          <button
            type="button"
            className="btn btn-border"
            style={{ borderColor: "#c00", color: "#c00" }}
            onClick={handleDeleteNovel}
          >
            小説を削除
          </button>
        </div>
      </div>
            {/* 年齢区分 & AI創作バッジ */}
      <div
        style={{
          marginTop: 8,
          marginBottom: 4,
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
          alignItems: "center",
          fontSize: "0.85rem",
        }}
      >
        <span
          style={{
            display: "inline-block",
            padding: "2px 8px",
            borderRadius: 999,
            border: "1px solid #888",
          }}
        >
          {getAgeLabel(novel.age_limit)}
        </span>

        {novel.is_ai_generated && (
          <span
            style={{
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: 999,
              border: "1px solid #888",
            }}
          >
            AI創作
          </span>
        )}
      </div>

      {/* 著者 / 日付 / 閲覧数 / いいね */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          alignItems: "center",
          marginTop: 8,
          marginBottom: 8,
          fontSize: "0.9rem",
          color: "#666",
        }}
      >
          {authorName && (
            <span>作者: {authorName}</span>
          )}
	{novel.created_at && (
          <span>作成日時: {formatDateTime(novel.created_at)}</span>
        )}
        {typeof novel.view_count === "number" && (
          <span>閲覧数: {novel.view_count}</span>
        )}
        {/* お気に入りボタン */}
        <button
          type="button"
          className="btn btn-border"
          onClick={toggleFavorite}
        >
          {isFavorited ? "★ お気に入り済み" : "☆ お気に入りに追加"}
        </button>

        <button
          type="button"
          className="btn btn-border"
          onClick={handleToggleLike}
          style={{ marginLeft: "auto" }}
        >
          {isLiked ? "♥ いいね済み" : "♡ いいね"} ({likeCount})
        </button>
      </div>

      {/* タグ */}
      {tags.length > 0 && (
        <div style={{ marginBottom: 12 }}>
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

      {/* 説明文 */}
      {novel.description && (
        <div
          style={{
            marginTop: 8,
            marginBottom: 16,
            whiteSpace: "pre-wrap",
            lineHeight: 1.6,
          }}
        >
          {novel.description}
        </div>
      )}

      <hr />

      {/* エピソード一覧 */}
      <h3 style={{ marginTop: 16 }}>エピソード一覧</h3>

      {/* エピソード追加ボタン */}
      <div style={{ marginTop: 8, marginBottom: 8 }}>
        <button
          type="button"
          className="btn btn-border"
          onClick={handleCreateEpisode}
        >
          ＋ エピソードを追加
        </button>
      </div>
      {episodes.length === 0 ? (
        <p>まだエピソードがありません。</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, marginTop: 8 }}>
          {episodes.map((ep) => (
            <li
              key={ep.id}
              style={{
                padding: "8px 0",
                borderBottom: "1px solid #eee",
                display: "flex",
                flexDirection: "column",
                gap: 4,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  flexWrap: "wrap",
                }}
              >
                <Link
                  to={`/episodes/${ep.id}`}
                  style={{ fontWeight: "bold", marginRight: "auto" }}
                >
                  第{ep.number || ep.episode_number}話 {ep.title}
                </Link>

                {/* エピソード編集・削除ボタン */}
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => handleEditEpisode(ep.id)}
                >
                  編集
                </button>
                <button
                  type="button"
                  className="btn btn-border"
                  style={{ borderColor: "#c00", color: "#c00" }}
                  onClick={() => handleDeleteEpisode(ep.id)}
                >
                  削除
                </button>
              </div>

              <div
                style={{
                  fontSize: "0.85rem",
                  color: "#777",
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 8,
                }}
              >
                {ep.created_at && (
                  <span>作成日時: {formatDateTime(ep.created_at)}</span>
                )}
                {typeof ep.view_count === "number" && (
                  <span>閲覧数: {ep.view_count}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
