import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const API_BASE = "";

export default function Mypage() {
  const [novels, setNovels] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const token = localStorage.getItem("token");

  useEffect(() => {
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
  }, [navigate, token]);

  useEffect(() => {
    if (!token) return;

    const fetchFavorites = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/me/favorites`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!res.ok) {
          console.error("failed to fetch favorites");
          return;
        }

        const data = await res.json();
        setFavorites(data);
      } catch (e) {
        console.error(e);
      }
    };

    fetchFavorites();
  }, [token]);

  if (loading) return <p>読み込み中...</p>;

  const username = localStorage.getItem("username") || "ユーザー";

  return (
  <div style={{ maxWidth: 800, margin: "0 auto" }}>
    <div style={{ marginBottom: 12 }}>
      <Link to="/">← トップに戻る</Link>
    </div>

    <h2 style={{ marginBottom: "1rem" }}>{username} さんのマイページ</h2>

    {/* ================================ */}
    {/* お気に入り小説 */}
    {/* ================================ */}
    <section style={{ marginTop: "2.5rem" }}>
      <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
        お気に入り小説
      </h3>

      {favorites.length === 0 ? (
        <p style={{ marginTop: 10 }}>お気に入りはまだありません。</p>
      ) : (
        <ul style={{ marginTop: 10, paddingLeft: 20 }}>
          {favorites.map((novel) => (
            <li key={novel.id} style={{ marginBottom: 8 }}>
              <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
            </li>
          ))}
        </ul>
      )}
    </section>

    {/* ================================ */}
    {/* マイページ設定 */}
    {/* ================================ */}
    <section style={{ marginTop: "2.5rem" }}>
      <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
        マイページ設定
      </h3>

      <div style={{ marginTop: 12 }}>
        <Link className="btn btn-border" to="/mypage/settings">
          設定を開く
        </Link>
      </div>
    </section>

    {/* ================================ */}
    {/* 作成した小説 */}
    {/* ================================ */}
    <section style={{ marginTop: "3rem" }}>
      <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
        作成した小説
      </h3>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {novels.length === 0 && (
        <p style={{ marginTop: 10 }}>まだ作成した小説がありません。</p>
      )}

      <div style={{ display: "grid", gap: 20, marginTop: 20 }}>
        {novels.map((novel) => (
          <div
            key={novel.id}
            style={{
              border: "1px solid #ddd",
              borderRadius: 6,
              padding: 14,
              background: "#fafafa",
            }}
          >
            <h4 style={{ marginBottom: 6 }}>
              <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
            </h4>

            <p
              style={{
                fontSize: 14,
                marginTop: 6,
                marginBottom: 12,
                whiteSpace: "pre-wrap",
              }}
            >
              {novel.description || ""}
            </p>

            <div style={{ display: "flex", gap: 10 }}>
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
    </section>
  </div>
);


}

