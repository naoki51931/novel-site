import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function NovelDetail() {
  const { id } = useParams();
  const [novel, setNovel] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/novels/${id}`)
      .then((res) => {
        if (!res.ok) throw new Error("Not found");
        return res.json();
      })
      .then((data) => {
        const episodes = (data.episodes || []).slice().sort((a, b) => {
          return (a.episode_number || 0) - (b.episode_number || 0);
        });
        setNovel({ ...data, episodes });
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString("ja-JP");
  };

  if (loading) return <p>読み込み中...</p>;
  if (!novel) return <p>小説が見つかりませんでした。</p>;

  const episodes = novel.episodes || [];

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← 一覧に戻る</Link>
      </div>
      <h2>{novel.title}</h2>
      {novel.description && (
        <p style={{ whiteSpace: "pre-wrap" }}>{novel.description}</p>
      )}
      <div style={{ fontSize: 12, color: "#555", marginBottom: 12 }}>
        <div>作者: demo</div>
        <div>作成日時: {formatDateTime(novel.created_at)}</div>
      </div>

      <button
        onClick={() => navigate(`/novels/${id}/episodes/new`)}
        style={{ marginBottom: 16 }}
      >
        この小説にエピソードを追加
      </button>

      <h3>エピソード一覧</h3>
      {episodes.length === 0 && <p>まだエピソードがありません。</p>}
      <ul style={{ listStyle: "none", paddingLeft: 0 }}>
        {episodes.map((ep) => (
          <li
            key={ep.id}
            style={{
              border: "1px solid #ddd",
              borderRadius: 6,
              padding: 8,
              marginBottom: 8,
            }}
          >
            <strong>
              第{ep.episode_number}話 {ep.title}
            </strong>
            <div style={{ fontSize: 12, color: "#555", marginBottom: 4 }}>
              投稿日時: {formatDateTime(ep.created_at)}
            </div>
            <div style={{ whiteSpace: "pre-wrap" }}>{ep.body}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}
