import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function Home() {
  const [novels, setNovels] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchNovels = async () => {
      try {
        setLoading(true);
        const res = await fetch(`${API_BASE}/api/novels`);
        if (!res.ok) {
          throw new Error("小説一覧の取得に失敗しました");
        }
        const data = await res.json();

        // 新しい順に並べる（created_at があればそれで）
        const sorted = (data || []).slice().sort((a, b) => {
          const ad = a.created_at ? new Date(a.created_at).getTime() : 0;
          const bd = b.created_at ? new Date(b.created_at).getTime() : 0;
          return bd - ad;
        });

        setNovels(sorted);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchNovels();
  }, []);

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString("ja-JP");
  };

  const shorten = (text, max = 120) => {
    if (!text) return "";
    if (text.length <= max) return text;
    return text.slice(0, max) + "…";
  };

  if (loading) {
    return <p>読み込み中...</p>;
  }

  return (
    <div>
      <div style={{ marginBottom: 16, textAlign: "right" }}>
        <button
          className="btn btn-border"
          onClick={() => navigate("/novels/new")}
        >
          新規小説投稿
        </button>
      </div>

      {novels.length === 0 && <p>まだ小説がありません。</p>}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
          gap: "16px",
        }}
      >
        {novels.map((novel) => (
          <div
            key={novel.id}
            style={{
              border: "1px solid #ddd",
              borderRadius: 8,
              padding: 12,
              boxShadow: "0 2px 4px rgba(0,0,0,0.03)",
              backgroundColor: "#fff",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
            }}
          >
            <div>
              <h3 style={{ margin: "0 0 8px 0", fontSize: 18 }}>
                <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
              </h3>
              <p
                style={{
                  whiteSpace: "pre-wrap",
                  fontSize: 14,
                  color: "#444",
                  marginBottom: 8,
                  minHeight: "3.5em",
                }}
              >
                {shorten(novel.description, 120) || "説明がありません。"}
              </p>
            </div>

            <div style={{ fontSize: 12, color: "#666", marginBottom: 8 }}>
              <div>作者: demo</div>
              <div>作成日時: {formatDateTime(novel.created_at)}</div>
            </div>

            <div style={{ textAlign: "right" }}>
              <Link
                to={`/novels/${novel.id}`}
                className="btn btn-border"
              >
                続きを読む
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
