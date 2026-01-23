import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import TagChipLink from "../components/TagChipLink.jsx";
import SupportPanel from "../components/SupportPanel.jsx";
import { useI18n } from "../lib/i18n";

const API_BASE = import.meta.env.VITE_BACKEND_ORIGIN || "https://shosetsu-toukou-site.org";

export default function UserPage() {
  const { username: usernameParam } = useParams();
  const username = useMemo(() => (usernameParam ?? "").trim(), [usernameParam]);
  const { t } = useI18n();

  const [profile, setProfile] = useState(null);
  const [novels, setNovels] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dmError, setDmError] = useState("");
  const [dmLoading, setDmLoading] = useState(false);
  const navigate = useNavigate();

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
          throw new Error(
            profileData.detail || t({ ja: "ユーザー情報の取得に失敗しました", en: "Failed to load user info." })
          );
        }
        if (!resNovels.ok) {
          throw new Error(
            novelsData.detail || t({ ja: "小説一覧の取得に失敗しました", en: "Failed to load novels." })
          );
        }
        if (!resFavorites.ok) {
          throw new Error(
            favoritesData.detail || t({ ja: "お気に入りの取得に失敗しました", en: "Failed to load favorites." })
          );
        }

        setProfile(profileData);
        setNovels(Array.isArray(novelsData) ? novelsData : []);
        setFavorites(Array.isArray(favoritesData) ? favoritesData : []);
      } catch (e) {
        console.error(e);
        setError(e.message || t({ ja: "エラーが発生しました", en: "An error occurred." }));
      } finally {
        setLoading(false);
      }
    };

    if (!username) {
      setError(t({ ja: "ユーザー名が指定されていません", en: "No username specified." }));
      setLoading(false);
      return;
    }

    fetchAll();
  }, [username]);

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  if (error) {
    return (
      <div style={{ maxWidth: 800, margin: "0 auto" }}>
        <div style={{ marginBottom: 12 }}>
          <Link to="/">{t({ ja: "← トップに戻る", en: "← Back to Home" })}</Link>
        </div>
        <p style={{ color: "red" }}>{error}</p>
      </div>
    );
  }

  const displayName = profile?.username || username;
  const isPremium = !!profile?.is_premium;
  const currentUsername =
    typeof window !== "undefined" ? localStorage.getItem("username") : null;
  const trimmedCurrentUsername = (currentUsername ?? "").trim();
  const trimmedDisplayName = (displayName ?? "").trim();
  const canStartDm =
    trimmedCurrentUsername !== "" && trimmedCurrentUsername !== trimmedDisplayName;

  const handleCreateDm = async () => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      setDmError(t({ ja: "ログインが必要です", en: "Login required." }));
      return;
    }
    if (!trimmedDisplayName) {
      setDmError(t({ ja: "送信先ユーザーが見つかりません", en: "Recipient user not found." }));
      return;
    }

    try {
      setDmLoading(true);
      setDmError("");
      const res = await fetch(`${API_BASE}/api/dms`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ target_username: trimmedDisplayName }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "DMの作成に失敗しました", en: "Failed to create DM." }));
      }
      navigate(`/dms/${data.id}`);
    } catch (e) {
      console.error(e);
      setDmError(e.message || t({ ja: "エラーが発生しました", en: "An error occurred." }));
    } finally {
      setDmLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">{t({ ja: "← トップに戻る", en: "← Back to Home" })}</Link>
      </div>

      <h2
        style={{
          marginBottom: "0.75rem",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          flexWrap: "wrap",
        }}
      >
        {t({ ja: "{{name}} さんのページ", en: "{{name}}'s page" }, { name: displayName })}
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
        {canStartDm && (
          <button
            type="button"
            onClick={handleCreateDm}
            disabled={dmLoading}
            title={t({ ja: "DMを送る", en: "Send DM" })}
            className="dm-icon-button"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 28,
              height: 28,
              borderRadius: 999,
              padding: 0,
            }}
            aria-label={t({ ja: "DMを送る", en: "Send DM" })}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" />
              <path d="m22 6-10 7L2 6" />
            </svg>
          </button>
        )}
      </h2>
      {dmError && <p style={{ color: "red", marginBottom: 8 }}>{dmError}</p>}

      {profile?.id && (
        <SupportPanel
          authorUserId={profile.id}
          authorName={displayName || t({ ja: "作者", en: "Author" })}
        />
      )}

      <section style={{ marginTop: "1.5rem" }}>
        <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
          {t({ ja: "公開中の小説", en: "Published novels" })}
        </h3>

        {novels.length === 0 ? (
          <p style={{ marginTop: 10 }}>
            {t({ ja: "公開中の小説がありません。", en: "No published novels." })}
          </p>
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
                {novel.cover_image_url && (
                  <img
                    src={
                      novel.cover_image_url.startsWith("http")
                        ? novel.cover_image_url
                        : API_BASE + novel.cover_image_url
                    }
                    alt={t({ ja: "表紙画像", en: "Cover image" })}
                    style={{
                      width: "100%",
                      maxHeight: 220,
                      objectFit: "cover",
                      borderRadius: 6,
                      boxShadow: "0 1px 4px var(--shadow)",
                      marginBottom: 10,
                    }}
                  />
                )}
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
                  <span>{t({ ja: "閲覧", en: "Views" })}: {novel.view_count ?? 0}</span>
                  <span>{t({ ja: "LIKE", en: "Likes" })}: {novel.like_count ?? 0}</span>
                  <span>{t({ ja: "お気に入り", en: "Favorites" })}: {novel.favorite_count ?? 0}</span>
                  <span>{t({ ja: "文字数", en: "Chars" })}: {novel.total_char_count ?? 0}</span>
                  <span className="tag-chip-row">
                    {Array.isArray(novel.tags) && novel.tags.length > 0 ? (
                      novel.tags.map((t) => (
                        <TagChipLink key={t.id ?? t.name} name={t.name} />
                      ))
                    ) : (
                      <span style={{ color: "var(--muted-text)" }}>
                        {t({ ja: "タグ: なし", en: "Tags: none" })}
                      </span>
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
          {t({ ja: "お気に入り小説", en: "Favorite novels" })}
        </h3>

        {favorites.length === 0 ? (
          <p style={{ marginTop: 10 }}>
            {t({ ja: "お気に入りはまだありません。", en: "No favorites yet." })}
          </p>
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
                {novel.cover_image_url && (
                  <img
                    src={
                      novel.cover_image_url.startsWith("http")
                        ? novel.cover_image_url
                        : API_BASE + novel.cover_image_url
                    }
                    alt={t({ ja: "表紙画像", en: "Cover image" })}
                    style={{
                      width: "100%",
                      maxHeight: 220,
                      objectFit: "cover",
                      borderRadius: 6,
                      boxShadow: "0 1px 4px var(--shadow)",
                      marginBottom: 10,
                    }}
                  />
                )}
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
                  <span>{t({ ja: "閲覧", en: "Views" })}: {novel.view_count ?? 0}</span>
                  <span>{t({ ja: "LIKE", en: "Likes" })}: {novel.like_count ?? 0}</span>
                  <span>{t({ ja: "お気に入り", en: "Favorites" })}: {novel.favorite_count ?? 0}</span>
                  <span>{t({ ja: "文字数", en: "Chars" })}: {novel.total_char_count ?? 0}</span>
                  <span className="tag-chip-row">
                    {Array.isArray(novel.tags) && novel.tags.length > 0 ? (
                      novel.tags.map((t) => (
                        <TagChipLink key={t.id ?? t.name} name={t.name} />
                      ))
                    ) : (
                      <span style={{ color: "var(--muted-text)" }}>
                        {t({ ja: "タグ: なし", en: "Tags: none" })}
                      </span>
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
