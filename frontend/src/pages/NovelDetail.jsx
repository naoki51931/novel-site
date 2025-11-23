import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function NovelDetail() {
  const { id } = useParams();
  const [novel, setNovel] = useState(null);
  const [episodes, setEpisodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
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
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [id]);

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString("ja-JP");
  };

  const shorten = (text, max = 160) => {
    if (!text) return "";
    if (text.length <= max) return text;
    return text.slice(0, max) + "…";
  };

  if (loading) return <p>読み込み中...</p>;
  if (!novel) return <p>小説が見つかりませんでした。</p>;

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← 一覧に戻る</Link>
      </div>

      <h2 style={{ marginBottom: 8 }}>{novel.title}</h2>

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
        <div>作者: demo</div>
        <div>作成日時: {formatDateTime(novel.created_at)}</div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <button
          className="btn btn-border"
          onClick={() => navigate(`/novels/${id}/episodes/new`)}
        >
          この小説にエピソードを追加
        </button>
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
              <Link
                to={`/episodes/${ep.id}`}
                className="btn btn-border"
              >
                このエピソードを読む
              </Link>

              <Link
                to={`/episodes/${ep.id}/edit`}
                className="btn btn-border"
              >
                編集
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
