// frontend/src/pages/Home.jsx
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import TagChipLink from "../components/TagChipLink.jsx";
import { useI18n } from "../lib/i18n";

const API_BASE = import.meta.env.VITE_BACKEND_ORIGIN || "https://shosetsu-toukou-site.org";

export default function Home({
  query = "",
  excludeQuery = "",
  tag = "",
  showRanking = true,
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const { t, lang } = useI18n();
  const [novels, setNovels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ranking, setRanking] = useState([]);
  const [rankingSort, setRankingSort] = useState("likes");
  const [rankingLoading, setRankingLoading] = useState(true);
  const [rankingError, setRankingError] = useState("");
  const [rankingEnabled, setRankingEnabled] = useState(false);
  const [isPremium, setIsPremium] = useState(false);
  const [premiumChecked, setPremiumChecked] = useState(false);
  const [recommendedNovels, setRecommendedNovels] = useState([]);
  const [recommendedLoading, setRecommendedLoading] = useState(false);
  const [recommendedError, setRecommendedError] = useState("");

  useEffect(() => {
    const fetchNovels = async () => {
      try {
        setLoading(true);
        setError("");

        const params = new URLSearchParams(location.search);
        const urlQuery = (params.get("q") ?? "").trim();
        const urlExclude = (params.get("exclude") ?? "").trim();
        const urlTag = (params.get("tag") ?? "").trim();
        const effectiveTag = urlTag || (tag ?? "").trim();
        const effectiveQuery = urlQuery || (query ?? "").trim();
        const effectiveExclude = urlExclude || (excludeQuery ?? "").trim();

        let url = `${API_BASE}/api/public/novels`;
        const apiParams = new URLSearchParams();
        if (effectiveQuery) apiParams.set("q", effectiveQuery);
        if (effectiveExclude) apiParams.set("exclude", effectiveExclude);
        if (effectiveTag) apiParams.set("tag", effectiveTag);
        const qs = apiParams.toString();
        if (qs) url += `?${qs}`;

        const token =
          localStorage.getItem("token") ||
          localStorage.getItem("access_token");
        const headers = token ? { Authorization: "Bearer " + token } : undefined;
        const res = await fetch(
          url,
          headers ? { headers, cache: "no-store" } : { cache: "no-store" }
        );
        if (!res.ok) {
          throw new Error(
            t({ ja: "小説一覧の取得に失敗しました", en: "Failed to load novels." })
          );
        }

        const data = await res.json();

        const sorted = (data || []).slice().sort((a, b) => {
          const ad = a.created_at ? new Date(a.created_at).getTime() : 0;
          const bd = b.created_at ? new Date(b.created_at).getTime() : 0;
          return bd - ad;
        });

        setNovels(sorted);
      } catch (err) {
        console.error(err);
        setError(err.message || t({ ja: "エラーが発生しました", en: "An error occurred." }));
      } finally {
        setLoading(false);
      }
    };

    fetchNovels();
  }, [query, excludeQuery, tag, location.search]); // ← 検索語 or URL が変わるたびに再取得

  useEffect(() => {
    if (!showRanking) {
      setRanking([]);
      setRankingLoading(false);
      setRankingError("");
      return;
    }
    const fetchRanking = async () => {
      if (!isPremium || !rankingEnabled) {
        setRanking([]);
        setRankingLoading(false);
        return;
      }

      try {
        setRankingLoading(true);
        setRankingError("");

        const params = new URLSearchParams(location.search);
        const urlQuery = (params.get("q") ?? "").trim();
        const urlExclude = (params.get("exclude") ?? "").trim();
        const urlTag = (params.get("tag") ?? "").trim();
        const effectiveTag = urlTag || (tag ?? "").trim();
        const effectiveQuery = urlQuery || (query ?? "").trim();
        const effectiveExclude = urlExclude || (excludeQuery ?? "").trim();

        const token =
          localStorage.getItem("token") ||
          localStorage.getItem("access_token");
        const headers = token ? { Authorization: "Bearer " + token } : undefined;

        const apiParams = new URLSearchParams();
        apiParams.set("sort", rankingSort);
        if (effectiveQuery) apiParams.set("q", effectiveQuery);
        if (effectiveExclude) apiParams.set("exclude", effectiveExclude);
        if (effectiveTag) apiParams.set("tag", effectiveTag);
        const qs = apiParams.toString();
        let url = `${API_BASE}/api/public/novels/ranking`;
        if (qs) url += `?${qs}`;

        const res = await fetch(
          url,
          headers ? { headers, cache: "no-store" } : { cache: "no-store" }
        );
        if (!res.ok) {
          throw new Error(
            t({ ja: "ランキングの取得に失敗しました", en: "Failed to load ranking." })
          );
        }
        const data = await res.json().catch(() => []);
        setRanking(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error(err);
        setRankingError(
          err.message || t({ ja: "ランキングの取得に失敗しました", en: "Failed to load ranking." })
        );
      } finally {
        setRankingLoading(false);
      }
    };

    fetchRanking();
  }, [
    rankingSort,
    isPremium,
    rankingEnabled,
    location.search,
    query,
    excludeQuery,
    tag,
    showRanking,
  ]);

  useEffect(() => {
    const fetchPremium = async () => {
      const token =
        localStorage.getItem("token") || localStorage.getItem("access_token");
      if (!token) {
        setIsPremium(false);
        setPremiumChecked(true);
        return;
      }

      try {
        const res = await fetch(`${API_BASE}/api/users/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          setIsPremium(false);
          setPremiumChecked(true);
          return;
        }
        const data = await res.json().catch(() => ({}));
        setIsPremium(!!data.is_premium);
      } catch (err) {
        console.error(err);
        setIsPremium(false);
      } finally {
        setPremiumChecked(true);
      }
    };

    fetchPremium();
  }, [location.pathname]);

  useEffect(() => {
    const fetchRecommended = async () => {
      const token =
        localStorage.getItem("token") || localStorage.getItem("access_token");
      if (!token) {
        setRecommendedNovels([]);
        setRecommendedLoading(false);
        setRecommendedError("");
        return;
      }

      const params = new URLSearchParams(location.search);
      const urlQuery = (params.get("q") ?? "").trim();
      const urlExclude = (params.get("exclude") ?? "").trim();
      const urlTag = (params.get("tag") ?? "").trim();
      const effectiveTag = urlTag || (tag ?? "").trim();
      const effectiveQuery = urlQuery || (query ?? "").trim();
      const effectiveExclude = urlExclude || (excludeQuery ?? "").trim();
      const isTopFeed = !effectiveTag && !effectiveQuery && !effectiveExclude;
      if (!isTopFeed) {
        setRecommendedNovels([]);
        setRecommendedLoading(false);
        setRecommendedError("");
        return;
      }

      try {
        setRecommendedLoading(true);
        setRecommendedError("");
        const res = await fetch(`${API_BASE}/api/public/novels/recommended?limit=8`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        });
        if (res.status === 401) {
          setRecommendedNovels([]);
          setRecommendedLoading(false);
          return;
        }
        if (!res.ok) {
          throw new Error(
            t({ ja: "おすすめの取得に失敗しました", en: "Failed to load recommendations." })
          );
        }
        const data = await res.json().catch(() => []);
        setRecommendedNovels(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error(err);
        setRecommendedError(
          err.message ||
            t({ ja: "おすすめの取得に失敗しました", en: "Failed to load recommendations." })
        );
      } finally {
        setRecommendedLoading(false);
      }
    };

    fetchRecommended();
  }, [location.search, query, excludeQuery, tag, t]);

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString(lang === "en" ? "en-US" : "ja-JP", {
      timeZone: "Asia/Tokyo",
    });
  };

  const shorten = (text, max = 120) => {
    if (!text) return "";
    if (text.length <= max) return text;
    return text.slice(0, max) + "…";
  };

  const currentParams = new URLSearchParams(location.search);
  const currentUrlQuery = (currentParams.get("q") ?? "").trim();
  const currentUrlExclude = (currentParams.get("exclude") ?? "").trim();
  const currentUrlTag = (currentParams.get("tag") ?? "").trim();
  const currentEffectiveTag = currentUrlTag || (tag ?? "").trim();
  const currentEffectiveQuery = currentUrlQuery || (query ?? "").trim();
  const currentEffectiveExclude = currentUrlExclude || (excludeQuery ?? "").trim();
  const hasAuthToken = !!(
    localStorage.getItem("token") || localStorage.getItem("access_token")
  );
  const showRecommendedSection =
    hasAuthToken &&
    !currentEffectiveTag &&
    !currentEffectiveQuery &&
    !currentEffectiveExclude;

  const applyNovelUpdate = (novelId, updater) => {
    setNovels((prev) =>
      prev.map((item) => (item.id === novelId ? updater(item) : item))
    );
    setRanking((prev) =>
      prev.map((item) => (item.id === novelId ? updater(item) : item))
    );
    setRecommendedNovels((prev) =>
      prev.map((item) => (item.id === novelId ? updater(item) : item))
    );
  };

  const requireToken = () => {
    const token =
      localStorage.getItem("token") || localStorage.getItem("access_token");
    if (!token) {
      alert(t({ ja: "ログインが必要です。", en: "Login required." }));
      navigate("/login");
      return null;
    }
    return token;
  };

  const toggleLike = async (novel) => {
    const token = requireToken();
    if (!token) return;

    const prevLiked = !!novel.is_liked;
    const method = prevLiked ? "DELETE" : "POST";

    try {
      const res = await fetch(`${API_BASE}/api/novels/${novel.id}/like`, {
        method,
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "いいね操作に失敗しました", en: "Failed to like." }));
      }

      applyNovelUpdate(novel.id, (item) => {
        const nextLiked =
          typeof data.liked === "boolean" ? data.liked : !prevLiked;
        const delta =
          nextLiked === prevLiked ? 0 : nextLiked ? 1 : -1;
        const nextLikeCount =
          typeof data.like_count === "number"
            ? data.like_count
            : Math.max(0, (item.like_count ?? 0) + delta);
        return { ...item, is_liked: nextLiked, like_count: nextLikeCount };
      });
    } catch (err) {
      console.error(err);
      alert(
        err.message || t({ ja: "いいね操作中にエラーが発生しました", en: "An error occurred while liking." })
      );
    }
  };

  const toggleFavorite = async (novel) => {
    const token = requireToken();
    if (!token) return;

    const prevFavorited = !!novel.is_favorited;
    const method = prevFavorited ? "DELETE" : "POST";

    try {
      const res = await fetch(`${API_BASE}/api/novels/${novel.id}/favorite`, {
        method,
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data.detail || t({ ja: "ブックマーク操作に失敗しました", en: "Failed to bookmark." })
        );
      }

      applyNovelUpdate(novel.id, (item) => {
        const nextFavorited =
          typeof data.favorited === "boolean" ? data.favorited : !prevFavorited;
        const delta =
          nextFavorited === prevFavorited ? 0 : nextFavorited ? 1 : -1;
        const nextFavoriteCount = Math.max(
          0,
          (item.favorite_count ?? 0) + delta
        );
        return {
          ...item,
          is_favorited: nextFavorited,
          favorite_count: nextFavoriteCount,
        };
      });
    } catch (err) {
      console.error(err);
      alert(
        err.message ||
          t({ ja: "ブックマーク操作中にエラーが発生しました", en: "An error occurred while bookmarking." })
      );
    }
  };

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  return (
    <div>
      {error && (
        <p style={{ color: "red", marginTop: 8, marginBottom: 8 }}>{error}</p>
      )}

      {showRanking && (
        <section style={{ marginBottom: 24 }}>
          <h3
            style={{
              borderBottom: "1px solid var(--border)",
              paddingBottom: 6,
              display: "flex",
              alignItems: "center",
              gap: 8,
              flexWrap: "wrap",
            }}
          >
            {t({ ja: "ランキング", en: "Ranking" })}
            <span
              style={{
                display: "inline-block",
                padding: "2px 8px",
                borderRadius: 999,
                backgroundColor: "var(--header-bg)",
                color: "var(--header-text)",
                fontSize: 12,
                letterSpacing: "0.04em",
              }}
            >
              PREMIUM
            </span>
            <label
              style={{
                marginLeft: "auto",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: 12,
                color: "var(--muted-text)",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={rankingEnabled}
                onChange={(e) => setRankingEnabled(e.target.checked)}
              />
              {t({ ja: "ランキング表示", en: "Show ranking" })}
            </label>
          </h3>
          <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
            {[
              { key: "likes", label: t({ ja: "いいね", en: "Likes" }) },
              { key: "favorites", label: t({ ja: "ブックマーク", en: "Bookmarks" }) },
              { key: "views", label: t({ ja: "閲覧", en: "Views" }) },
            ].map((option) => (
              <button
                key={option.key}
                type="button"
                className="btn btn-border"
                onClick={() => setRankingSort(option.key)}
                disabled={!rankingEnabled}
                style={
                  rankingSort === option.key
                    ? { borderColor: "var(--cta)", color: "var(--cta)" }
                    : undefined
                }
              >
                {option.label}
              </button>
            ))}
          </div>

          {!premiumChecked ? (
            <p style={{ marginTop: 10 }}>
              {t({ ja: "プレミアム状態を確認中...", en: "Checking premium status..." })}
            </p>
          ) : !isPremium ? (
            <div
              style={{
                marginTop: 12,
                padding: 12,
                border: "1px dashed var(--border)",
                borderRadius: 8,
                color: "var(--muted-text)",
              }}
            >
              {t({ ja: "ランキングはプレミアム会員限定の機能です。", en: "Ranking is a premium-only feature." })}
            </div>
          ) : !rankingEnabled ? (
            <div
              style={{
                marginTop: 12,
                padding: 12,
                border: "1px dashed var(--border)",
                borderRadius: 8,
                color: "var(--muted-text)",
              }}
            >
              {t({ ja: "トグルをオンにするとランキングが表示されます。", en: "Turn on the toggle to show rankings." })}
            </div>
          ) : (
            <>
              {rankingError && (
                <p style={{ color: "red", marginTop: 8 }}>{rankingError}</p>
              )}

              {rankingLoading ? (
                <p style={{ marginTop: 10 }}>
                  {t({ ja: "ランキングを読み込み中...", en: "Loading ranking..." })}
                </p>
              ) : ranking.length === 0 ? (
                <p style={{ marginTop: 10 }}>
                  {t({ ja: "ランキングデータがありません。", en: "No ranking data available." })}
                </p>
              ) : (
                <ol style={{ listStyle: "none", padding: 0, marginTop: 12 }}>
                  {ranking.map((novel) => (
                    <li
                      key={novel.id}
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 8,
                        border: "1px solid var(--novel-card-border)",
                        borderRadius: 8,
                        padding: 12,
                        marginBottom: 12,
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
                          }}
                        />
                      )}
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span
                          style={{
                            fontWeight: "bold",
                            minWidth: 48,
                            color: "var(--novel-card-meta)",
                          }}
                        >
                          #{novel.rank}
                        </span>
                        <Link to={`/novels/${novel.id}`} style={{ fontWeight: "bold" }}>
                          {novel.title}
                        </Link>
                        {novel.author_username && (
                          <span style={{ marginLeft: "auto", fontSize: 12 }}>
                            {t({ ja: "作者", en: "Author" })}:{" "}
                            <Link
                              className="user-link"
                              to={`/users/${encodeURIComponent(novel.author_username)}`}
                            >
                              {novel.author_username}
                            </Link>
                          </span>
                        )}
                      </div>

                      <div
                        style={{
                          display: "flex",
                          flexWrap: "wrap",
                          gap: 10,
                          fontSize: 12,
                          color: "var(--novel-card-meta)",
                        }}
                      >
                        <span>{t({ ja: "閲覧", en: "Views" })}: {novel.view_count ?? 0}</span>
                        <span>{t({ ja: "LIKE", en: "Likes" })}: {novel.like_count ?? 0}</span>
                        <span>{t({ ja: "ブックマーク", en: "Bookmarks" })}: {novel.favorite_count ?? 0}</span>
                        <span>{t({ ja: "文字数", en: "Chars" })}: {novel.total_char_count ?? 0}</span>
                      </div>

                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <button
                          type="button"
                          className="btn btn-border"
                          onClick={() => toggleLike(novel)}
                        >
                          {novel.is_liked
                            ? t({ ja: "♥ いいね済み", en: "♥ Liked" })
                            : t({ ja: "♡ いいね", en: "♡ Like" })}
                        </button>
                        <button
                          type="button"
                          className="btn btn-border"
                          onClick={() => toggleFavorite(novel)}
                        >
                          {novel.is_favorited
                            ? t({ ja: "★ ブックマーク済み", en: "★ Bookmarked" })
                            : t({ ja: "☆ ブックマーク", en: "☆ Bookmark" })}
                        </button>
                      </div>
                    </li>
                  ))}
              </ol>
            )}
          </>
        )}
        </section>
      )}

      {showRecommendedSection && (
      <section style={{ marginBottom: 24 }}>
        <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
          {t({ ja: "あなたへのおすすめ", en: "Recommended for You" })}
        </h3>
        {recommendedError && (
          <p style={{ color: "red", marginTop: 8 }}>{recommendedError}</p>
        )}
        {recommendedLoading ? (
          <p style={{ marginTop: 10 }}>
            {t({ ja: "おすすめを読み込み中...", en: "Loading recommendations..." })}
          </p>
        ) : recommendedNovels.length === 0 ? (
          <p style={{ marginTop: 10, color: "var(--muted-text)" }}>
            {t({
              ja: "ログイン中のブックマーク傾向に基づくおすすめはまだありません。",
              en: "No bookmark-based recommendations yet.",
            })}
          </p>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
              gap: "16px",
              marginTop: 12,
            }}
          >
            {recommendedNovels.map((novel) => (
              <div
                key={`recommended-${novel.id}`}
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
                <h3 style={{ margin: "0 0 8px 0", fontSize: 18 }}>
                  <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
                </h3>
                <p
                  style={{
                    whiteSpace: "pre-wrap",
                    fontSize: 14,
                    color: "var(--novel-card-desc)",
                    marginBottom: 8,
                    minHeight: "3.5em",
                  }}
                >
                  {shorten(novel.description, 120) ||
                    t({ ja: "説明がありません。", en: "No description." })}
                </p>
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
                  <span>{t({ ja: "ブックマーク", en: "Bookmarks" })}: {novel.favorite_count ?? 0}</span>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                  <button
                    type="button"
                    className="btn btn-border"
                    onClick={() => toggleLike(novel)}
                  >
                    {novel.is_liked
                      ? t({ ja: "♥ いいね済み", en: "♥ Liked" })
                      : t({ ja: "♡ いいね", en: "♡ Like" })}
                  </button>
                  <button
                    type="button"
                    className="btn btn-border"
                    onClick={() => toggleFavorite(novel)}
                  >
                    {novel.is_favorited
                      ? t({ ja: "★ ブックマーク済み", en: "★ Bookmarked" })
                      : t({ ja: "☆ ブックマーク", en: "☆ Bookmark" })}
                  </button>
                </div>
                <div style={{ textAlign: "right" }}>
                  <Link to={`/novels/${novel.id}`} className="btn btn-border">
                    {t({ ja: "続きを読む", en: "Read more" })}
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
      )}

      {novels.length === 0 && (
        <p>{t({ ja: "小説が見つかりません。", en: "No novels found." })}</p>
      )}

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
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                flexWrap: "wrap",
                margin: "0 0 8px 0",
              }}
            >
              <h3 style={{ margin: 0, fontSize: 18 }}>
                <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
              </h3>
              {novel.age_limit === "r18" && (
                <span className="age-chip age-chip-r18">R18</span>
              )}
            </div>

            <p
              style={{
                whiteSpace: "pre-wrap",
                fontSize: 14,
                color: "var(--novel-card-desc)",
                marginBottom: 8,
                minHeight: "3.5em",
              }}
            >
              {shorten(novel.description, 120) ||
                t({ ja: "説明がありません。", en: "No description." })}
            </p>

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
              <span>{t({ ja: "ブックマーク", en: "Bookmarks" })}: {novel.favorite_count ?? 0}</span>
              <span>{t({ ja: "文字数", en: "Chars" })}: {novel.total_char_count ?? 0}</span>
            </div>

            <div style={{ fontSize: 12, color: "var(--novel-card-meta)", marginBottom: 8 }}>
              <div>
                {t({ ja: "作者", en: "Author" })}:{" "}
                {novel.author_username ? (
                  <Link
                    className="user-link"
                    to={`/users/${encodeURIComponent(novel.author_username)}`}
                  >
                    {novel.author_username}
                  </Link>
                )
                  : novel.author_id
                  ? t({ ja: "ユーザーID: {{id}}", en: "User ID: {{id}}" }, { id: novel.author_id })
                  : t({ ja: "不明", en: "Unknown" })}
              </div>
              <div>
                {t({ ja: "作成日時", en: "Created" })}: {formatDateTime(novel.created_at)}
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
              <button
                type="button"
                className="btn btn-border"
                onClick={() => toggleLike(novel)}
              >
                {novel.is_liked
                  ? t({ ja: "♥ いいね済み", en: "♥ Liked" })
                  : t({ ja: "♡ いいね", en: "♡ Like" })}
              </button>
              <button
                type="button"
                className="btn btn-border"
                onClick={() => toggleFavorite(novel)}
              >
                {novel.is_favorited
                  ? t({ ja: "★ ブックマーク済み", en: "★ Bookmarked" })
                  : t({ ja: "☆ ブックマーク", en: "☆ Bookmark" })}
              </button>
            </div>

            <div
              className="tag-chip-row tag-chip-row-reserve-2lines"
              style={{ marginBottom: 10 }}
            >
              {Array.isArray(novel.tag_names) &&
                novel.tag_names.length > 0 &&
                novel.tag_names.map((name) => (
                  <TagChipLink key={name} name={name} />
                ))}
            </div>

            <div style={{ textAlign: "right" }}>
              <Link to={`/novels/${novel.id}`} className="btn btn-border">
                {t({ ja: "続きを読む", en: "Read more" })}
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
