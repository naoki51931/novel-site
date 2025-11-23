import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function EpisodeDetail() {
  const { id } = useParams(); // episode_id
  const navigate = useNavigate();
  const [episode, setEpisode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchEpisode = async () => {
      try {
        setLoading(true);
        setError("");

        const res = await fetch(`${API_BASE}/api/episodes/${id}`);
        if (!res.ok) {
          throw new Error(`エピソードの取得に失敗しました (${res.status})`);
        }

        const data = await res.json();
        setEpisode(data);
      } catch (err) {
        console.error(err);
        setError(err.message || "エピソードの取得中にエラーが発生しました");
      } finally {
        setLoading(false);
      }
    };

    fetchEpisode();
  }, [id]);

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

  if (!episode) {
    return (
      <div>
        <p>エピソードが見つかりませんでした。</p>
        <button className="btn btn-border" onClick={() => navigate(-1)}>
          戻る
        </button>
      </div>
    );
  }

  return (
    <div>
      <button className="btn btn-border" onClick={() => navigate(-1)}>
        ← 戻る
      </button>

      <h2 style={{ marginTop: 12 }}>
        第{episode.number}話 {episode.title}
      </h2>

      <p style={{ color: "#666", marginBottom: 4 }}>小説ID: {episode.novel_id}</p>

      {episode.created_at && (
        <p style={{ color: "#999", fontSize: "0.9rem", marginBottom: 8 }}>
          作成日時: {new Date(episode.created_at).toLocaleString()}
        </p>
      )}

      <hr />

      <div
        style={{
          whiteSpace: "pre-wrap",
          lineHeight: 1.8,
          marginTop: 12,
        }}
      >
        {episode.body}
      </div>

      <div style={{ marginTop: 24 }}>
        <Link to={`/novels/${episode.novel_id}`} className="btn btn-border">
          小説詳細へ戻る
        </Link>
      </div>
    </div>
  );
}
