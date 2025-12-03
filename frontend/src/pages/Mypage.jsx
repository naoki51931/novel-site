import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const API_BASE = "";

export default function Mypage() {
  const [novels, setNovels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      navigate("/login");
      return;
    }

    const fetchMine = async () => {
      try {
        setLoading(true);
        setError("");

        const res = await fetch(`${API_BASE}/api/novels?mine=true`, {
          headers: {
            Authorization: "Bearer " + token,
          },
        });

        const data = await res.json().catch(() => []);

        if (!res.ok) {
          throw new Error(data.detail || "マイページの取得に失敗しました");
        }

        setNovels(data);
      } catch (err) {
        console.error(err);
        setError(err.message || "マイページの取得中にエラーが発生しました");
      } finally {
        setLoading(false);
      }
    };

    fetchMine();
  }, [navigate]);

  if (loading) return <p>読み込み中...</p>;

  const username = localStorage.getItem("username") || "ユーザー";

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← トップに戻る</Link>
      </div>

      <h2>{username} さんのマイページ</h2>
      <div style={{ marginBottom: 12 }}><Link to="/mypage/settings">マイページ設定</Link></div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {novels.length === 0 && <p>まだ小説がありません。</p>}

      <div style={{ display: "grid", gap: 12 }}>
        {novels.map((novel) => (
          <div
            key={novel.id}
            style={{
              border: "1px solid #ddd",
              borderRadius: 6,
              padding: 10,
            }}
          >
            <h3 style={{ marginBottom: 4 }}>
              <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
            </h3>
            <p
              style={{
                fontSize: 14,
                marginTop: 6,
                marginBottom: 8,
                whiteSpace: "pre-wrap",
              }}
            >
              {novel.description || ""}
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <Link className="btn btn-border" to={`/novels/${novel.id}`}>
                詳細を見る
              </Link>
              <Link className="btn btn-border" to={`/novels/${novel.id}/edit`}>
                編集する
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
