from pathlib import Path

path = Path("frontend/src/pages/Mypage.jsx")

new_code = r'''import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const API_BASE = "";

async function startStripeCheckout() {
  try {
    const token = localStorage.getItem("token");
    if (!token) {
      alert("ログインが必要です。");
      return;
    }

    const res = await fetch("/api/stripe/create-checkout-session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
      },
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      throw new Error(
        data.detail ||
          `決済セッションの作成に失敗しました (${res.status})`
      );
    }

    if (data.url) {
      window.location.href = data.url;
    } else {
      throw new Error("決済URLが取得できませんでした。");
    }
  } catch (err) {
    console.error(err);
    alert(err.message || "決済の開始に失敗しました。");
  }
}

export default function Mypage() {
  const [novels, setNovels] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [isPremium, setIsPremium] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

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

    const fetchFavoritesAndProfile = async () => {
      try {
        // お気に入り取得
        const resFav = await fetch(`${API_BASE}/api/me/favorites`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (resFav.ok) {
          const dataFav = await resFav.json();
          setFavorites(dataFav);
        } else {
          console.error("failed to fetch favorites");
        }

        // プロフィール取得 → プレミアム判定
        const resProfile = await fetch(`${API_BASE}/api/users/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (resProfile.ok) {
          const profile = await resProfile.json();
          setIsPremium(!!profile.is_premium);
        }
      } catch (e) {
        console.error(e);
      }
    };

    fetchFavoritesAndProfile();
  }, [token]);

  if (loading) return <p>読み込み中...</p>;

  const username =
    (typeof window !== "undefined" && localStorage.getItem("username")) ||
    "ユーザー";

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← トップに戻る</Link>
      </div>

      <h2
        style={{
          marginBottom: "1rem",
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        {username} さんのマイページ
        {isPremium && (
          <span
            style={{
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: "999px",
              backgroundColor: "#f0b400",
              color: "#fff",
              fontSize: 12,
            }}
          >
            PREMIUM
          </span>
        )}
      </h2>

      {/* プレミアム会員セクション */}
      <section style={{ marginBottom: 24 }}>
        <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
          プレミアム会員
        </h3>
        <p style={{ marginBottom: 8, lineHeight: 1.6 }}>
          長文の全文表示などの追加機能を利用するには、プレミアム登録が必要です。
        </p>

        {!isPremium && (
          <button
            type="button"
            className="btn btn-border"
            onClick={startStripeCheckout}
          >
            プレミアム会員になる（決済ページへ）
          </button>
        )}

        {isPremium && (
          <p style={{ marginTop: 8, color: "#0a0", fontWeight: "bold" }}>
            現在プレミアム会員中です。
          </p>
        )}
      </section>

      {/* お気に入り小説 */}
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

      {/* マイページ設定 */}
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

      {/* 作成した小説 */}
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
                <Link
                  className="btn btn-border"
                  to={`/novels/${novel.id}/edit`}
                >
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
'''

path.write_text(new_code, encoding="utf-8")
print("✅ frontend/src/pages/Mypage.jsx を上書きしました")
