import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import TagChipLink from "../components/TagChipLink.jsx";

const API_BASE = "";

export default function UserPage() {
  const { username: usernameParam } = useParams();
  const username = useMemo(() => (usernameParam ?? "").trim(), [usernameParam]);

  const [profile, setProfile] = useState(null);
  const [novels, setNovels] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchAll = async () => {
      try {
        setLoading(true);
        setError("");

        const token =
          typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const headers = token ? { Authorization: `Bearer ${token}` } : {};

        const safeUsername = encodeURIComponent(username);
        const [resProfile, resNovels, resFavorites] = await Promise.all([
          fetch(`${API_BASE}/api/public/users/${safeUsername}`, { headers }),
          fetch(`${API_BASE}/api/public/users/${safeUsername}/novels`, { headers }),
          fetch(`${API_BASE}/api/public/users/${safeUsername}/favorites`, { headers }),
        ]);

        const profileData = await resProfile.json().catch(() => ({}));
        const novelsData = await resNovels.json().catch(() => []);
        const favoritesData = await resFavorites.json().catch(() => []);

        if (!resProfile.ok) {
          throw new Error(profileData.detail || "ユーザー情報の取得に失敗しました");
        }
        if (!resNovels.ok) {
          throw new Error(novelsData.detail || "小説一覧の取得に失敗しました");
        }
        if (!resFavorites.ok) {
          throw new Error(favoritesData.detail || "お気に入りの取得に失敗しました");
        }

        setProfile(profileData);
        setNovels(Array.isArray(novelsData) ? novelsData : []);
        setFavorites(Array.isArray(favoritesData) ? favoritesData : []);
      } catch (e) {
        console.error(e);
        setError(e.message || "エラーが発生しました");
      } finally {
        setLoading(false);
      }
    };

    if (!username) {
      setError("ユーザー名が指定されていません");
      setLoading(false);
      return;
    }

    fetchAll();
  }, [username]);

  if (loading) return <p>読み込み中...</p>;

  if (error) {
    return (
      <div style={{ maxWidth: 800, margin: "0 auto" }}>
        <div style={{ marginBottom: 12 }}>
          <Link to="/">← トップに戻る</Link>
        </div>
        <p style={{ color: "red" }}>{error}</p>
      </div>
    );
  }

  const displayName = profile?.username || username;
  const isPremium = !!profile?.is_premium;

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
        {displayName} さんのページ
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

      <section style={{ marginTop: "1.5rem" }}>
        <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
          公開中の小説
        </h3>

        {novels.length === 0 ? (
          <p style={{ marginTop: 10 }}>公開中の小説がありません。</p>
        ) : (
          <div style={{ display: "grid", gap: 20, marginTop: 20 }}>
            {novels.map((novel) => (
              <div
                key={novel.id}
                style={{
                  border: "1px solid var(--novel-card-border)",
                  borderRadius: 8,
                  padding: 12,
                  boxShadow: "0 2px 4px var(--shadow)",
                  backgroundColor: "var(--novel-card-bg)",
                  color: "var(--text)",
                }}
              >
                <h4 style={{ marginBottom: 6 }}>
                  <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
                </h4>

                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 10,
                    fontSize: 12,
                    color: "var(--novel-card-meta)",
                    marginBottom: 8,
                  }}
                >
                  <span>閲覧: {novel.view_count ?? 0}</span>
                  <span>LIKE: {novel.like_count ?? 0}</span>
                  <span>お気に入り: {novel.favorite_count ?? 0}</span>
                  <span className="tag-chip-row">
                    {Array.isArray(novel.tags) && novel.tags.length > 0 ? (
                      novel.tags.map((t) => (
                        <TagChipLink key={t.id ?? t.name} name={t.name} />
                      ))
                    ) : (
                      <span style={{ color: "var(--muted-text)" }}>タグ: なし</span>
                    )}
                  </span>
                </div>

                <p style={{ fontSize: 14, whiteSpace: "pre-wrap", margin: 0 }}>
                  {novel.description || ""}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section style={{ marginTop: "3rem" }}>
        <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
          お気に入り小説
        </h3>

        {favorites.length === 0 ? (
          <p style={{ marginTop: 10 }}>お気に入りはまだありません。</p>
        ) : (
          <div style={{ display: "grid", gap: 20, marginTop: 20 }}>
            {favorites.map((novel) => (
              <div
                key={novel.id}
                style={{
                  border: "1px solid var(--novel-card-border)",
                  borderRadius: 8,
                  padding: 12,
                  boxShadow: "0 2px 4px var(--shadow)",
                  backgroundColor: "var(--novel-card-bg)",
                  color: "var(--text)",
                }}
              >
                <h4 style={{ marginBottom: 6 }}>
                  <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
                </h4>

                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 10,
                    fontSize: 12,
                    color: "var(--novel-card-meta)",
                    marginBottom: 8,
                  }}
                >
                  <span>閲覧: {novel.view_count ?? 0}</span>
                  <span>LIKE: {novel.like_count ?? 0}</span>
                  <span>お気に入り: {novel.favorite_count ?? 0}</span>
                  <span className="tag-chip-row">
                    {Array.isArray(novel.tags) && novel.tags.length > 0 ? (
                      novel.tags.map((t) => (
                        <TagChipLink key={t.id ?? t.name} name={t.name} />
                      ))
                    ) : (
                      <span style={{ color: "var(--muted-text)" }}>タグ: なし</span>
                    )}
                  </span>
                </div>

                <p style={{ fontSize: 14, whiteSpace: "pre-wrap", margin: 0 }}>
                  {novel.description || ""}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
