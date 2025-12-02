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

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError("");

        // 小説本体
        const novelRes = await fetch(`${API_BASE}/api/novels/${id}`);
        if (!novelRes.ok) {
          throw new Error(`小説の取得に失敗しました (${novelRes.status})`);
        }
        const novelData = await novelRes.json();

        // エピソード一覧
        const epRes = await fetch(`${API_BASE}/api/novels/${id}/episodes`);
        if (!epRes.ok) {
          throw new Error(`エピソード一覧の取得に失敗しました (${epRes.status})`);
        }
        const epData = await epRes.json();

        setNovel(novelData);
        setEpisodes(Array.isArray(epData) ? epData : []);
      } catch (e) {
        console.error(e);
        setError(e.message || "小説情報の取得中にエラーが発生しました");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [id]);

  // いいねトグル
  const handleToggleLike = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      alert("いいねするにはログインが必要です。");
      navigate("/login");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/novels/${id}/like`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "いいねの更新に失敗しました");
      }

      const data = await res.json().catch(() => ({}));

      // バックエンドが { liked, like_count } を返す想定で反映
      setNovel((prev) => {
        if (!prev) return prev;
        const newLikeCount =
          data.like_count !== undefined
            ? data.like_count
            : (prev.like_count || 0) + (prev.liked_by_me ? -1 : 1);

        const newLiked =
          data.liked !== undefined ? data.liked : !prev.liked_by_me;

        return {
          ...prev,
          like_count: newLikeCount,
          liked_by_me: newLiked,
        };
      });
    } catch (e) {
      console.error(e);
      alert(e.message || "いいね処理中にエラーが発生しました");
    }
  };

  // 小説削除
  const handleDeleteNovel = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      alert("小説を削除するにはログインが必要です。");
      navigate("/login");
      return;
    }

    if (
      !window.confirm(
        `「${novel?.title ?? ""}」を本当に削除しますか？\nこの小説に紐づくエピソードも削除されます。`
      )
    ) {
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
        throw new Error(data.detail || "小説の削除に失敗しました");
      }

      alert("小説を削除しました。");
      navigate("/");
    } catch (e) {
      console.error(e);
      alert(e.message || "小説の削除中にエラーが発生しました");
    }
  };

  // エピソード削除
  const handleDeleteEpisode = async (episodeId, title) => {
    const token = localStorage.getItem("token");
    if (!token) {
      alert("エピソードを削除するにはログインが必要です。");
      navigate("/login");
      return;
    }

    if (
      !window.confirm(
        `エピソード「${title ?? ""}」を本当に削除しますか？`
      )
    ) {
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
        throw new Error(data.detail || "エピソードの削除に失敗しました");
      }

      // フロント側の一覧から消す
      setEpisodes((prev) => prev.filter((ep) => ep.id !== episodeId));
    } catch (e) {
      console.error(e);
      alert(e.message || "エピソードの削除中にエラーが発生しました");
    }
  };

  if (loading) {
    return <p>読み込み中...</p>;
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

  const tags =
    Array.isArray(novel.tag_names) && novel.tag_names.length > 0
      ? novel.tag_names
      : [];

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← 一覧に戻る</Link>
      </div>

      <h2 style={{ marginBottom: 4 }}>{novel.title}</h2>

      {/* 作者・日時など */}
      <p style={{ margin: 0, color: "#666" }}>
        作者: {novel.author_username || "名無し"}
      </p>
      {novel.created_at && (
        <p style={{ margin: 0, color: "#999", fontSize: "0.9rem" }}>
          作成日時:{" "}
          {new Date(novel.created_at).toLocaleString("ja-JP") || "-"}
        </p>
      )}

      {/* タグ表示 */}
      {tags.length > 0 && (
        <div style={{ marginTop: 8, marginBottom: 8 }}>
          {tags.map((name, idx) => (
            <span
              key={idx}
              style={{
                display: "inline-block",
                marginRight: 4,
                padding: "2px 8px",
                borderRadius: 12,
                border: "1px solid #ccc",
                fontSize: "0.85rem",
              }}
            >
              #{name}
            </span>
          ))}
        </div>
      )}

      {/* 説明文 */}
      {novel.description && (
        <p
          style={{
            marginTop: 8,
            marginBottom: 12,
            whiteSpace: "pre-wrap",
            lineHeight: 1.6,
          }}
        >
          {novel.description}
        </p>
      )}

      {/* ビュー数・いいね */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 16,
          flexWrap: "wrap",
        }}
      >
        <span style={{ color: "#666", fontSize: "0.9rem" }}>
          👀 閲覧数: {novel.view_count ?? 0}
        </span>

        <button
          type="button"
          className="btn btn-border"
          onClick={handleToggleLike}
        >
          {novel.liked_by_me ? "♥ いいね済み" : "♡ いいね"}
          {"　"}
          ({novel.like_count ?? 0})
        </button>
      </div>

      {/* 小説の編集・削除ボタン */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          marginBottom: 16,
        }}
      >
        <Link
          to={`/novels/${novel.id}/edit`}
          className="btn btn-border"
        >
          小説を編集
        </Link>
        <button
          type="button"
          className="btn btn-border"
          onClick={handleDeleteNovel}
        >
          小説を削除
        </button>
      </div>

      <hr />

      {/* エピソード一覧 */}
      <div style={{ marginTop: 12 }}>
        <h3>エピソード一覧</h3>
        {episodes.length === 0 ? (
          <p>まだエピソードがありません。</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0 }}>
            {episodes.map((ep) => (
              <li
                key={ep.id}
                style={{
                  padding: "8px 0",
                  borderBottom: "1px solid #eee",
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
                  <div>
                    <Link to={`/episodes/${ep.id}`}>
                      第{ep.episode_number ?? ep.number}話 {ep.title}
                    </Link>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      gap: 4,
                      flexShrink: 0,
                    }}
                  >
                    <Link
                      to={`/episodes/${ep.id}/edit`}
                      className="btn btn-border"
                      style={{
                        padding: "2px 6px",
                        fontSize: "0.8rem",
                      }}
                    >
                      編集
                    </Link>
                    <button
                      type="button"
                      className="btn btn-border"
                      style={{
                        padding: "2px 6px",
                        fontSize: "0.8rem",
                      }}
                      onClick={() =>
                        handleDeleteEpisode(ep.id, ep.title)
                      }
                    >
                      削除
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* エピソード追加ボタン */}
      <div style={{ marginTop: 16 }}>
        <Link
          to={`/novels/${novel.id}/episodes/new`}
          className="btn btn-border"
        >
          この小説にエピソードを追加
        </Link>
      </div>
    </div>
  );
}
