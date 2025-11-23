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

        // number でソート
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

  if (loading) return <p>読み込み中...</p>;
  if (!novel) return <p>小説が見つかりませんでした。</p>;

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
        className="btn btn-border"
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
              第{ep.number || ep.episode_number}話 {ep.title}
            </strong>
            <div style={{ fontSize: 12, color: "#555", marginBottom: 4 }}>
              投稿日時: {formatDateTime(ep.created_at)}
            </div>
            <div
              style={{
                whiteSpace: "pre-wrap",
                maxHeight: "6em",
                overflow: "hidden",
              }}
            >
              {ep.body}
            </div>
            <div style={{ marginTop: 8 }}>
              <Link
                to={`/episodes/${ep.id}`}
                className="btn btn-border"
              >
                このエピソードを読む
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
