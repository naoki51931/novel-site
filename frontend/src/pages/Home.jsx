import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function Home() {
  const [novels, setNovels] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/novels`)
      .then((res) => res.json())
      .then(setNovels)
      .catch(console.error);
  }, []);

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString("ja-JP");
  };

  return (
    <div>
      <h2>新着小説</h2>
      {novels.length === 0 && <p>まだ小説が投稿されていません。</p>}
      <div>
        {novels.map((n) => {
          const episodeCount = n.episodes ? n.episodes.length : 0;
          return (
            <div
              key={n.id}
              style={{
                border: "1px solid #ccc",
                borderRadius: 8,
                padding: 12,
                marginBottom: 12,
              }}
            >
              <h3 style={{ margin: "0 0 4px" }}>
                <Link to={`/novels/${n.id}`}>{n.title}</Link>
              </h3>
              {n.description && (
                <p style={{ margin: "0 0 4px", whiteSpace: "pre-wrap" }}>
                  {n.description}
                </p>
              )}
              <div style={{ fontSize: 12, color: "#555" }}>
                <div>作者: demo</div>
                <div>エピソード数: {episodeCount}</div>
                <div>投稿日時: {formatDateTime(n.created_at)}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
