import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import NovelCard from "../components/NovelCard.jsx";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";

const API_BASE = getApiBase();

const safeDecode = (value) => {
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

const SORT_OPTIONS = [
  { key: "popular", ja: "人気順", en: "Popular" },
  { key: "new", ja: "新着順", en: "Newest" },
  { key: "likes", ja: "いいね順", en: "Likes" },
  { key: "comments", ja: "コメント順", en: "Comments" },
];

export default function TagPage() {
  const { slug } = useParams();
  const { t, lang } = useI18n();
  const tagName = useMemo(() => safeDecode(slug).trim(), [slug]);
  const isTagIndex = !tagName;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sort, setSort] = useState("popular");
  const [tagList, setTagList] = useState([]);
  const [tagDetail, setTagDetail] = useState(null);
  const [relatedTags, setRelatedTags] = useState([]);
  const [novels, setNovels] = useState([]);
  const [tagFollowState, setTagFollowState] = useState({
    isFollowing: false,
    followerCount: 0,
  });
  const [tagFollowLoading, setTagFollowLoading] = useState(false);
  const [tagFollowError, setTagFollowError] = useState("");

  useEffect(() => {
    if (typeof document === "undefined") return undefined;

    const previousTitle = document.title;
    const metaDescription = document.querySelector('meta[name="description"]');
    const previousDescription = metaDescription?.getAttribute("content");

    const nextTitle = isTagIndex
      ? t({ ja: "タグ一覧｜小説投稿サイトLexis", en: "Tag List | Lexis" })
      : t({
          ja: `${tagName}小説一覧｜小説投稿サイトLexis`,
          en: `Novels tagged "${tagName}" | Lexis`,
        });
    const nextDescription = isTagIndex
      ? t({
          ja: "人気タグから小説を探せます。タグ経由で新しい作品と作者に出会えます。",
          en: "Browse novels by popular tags and discover new works and authors.",
        })
      : t({
          ja: `「${tagName}」タグの作品一覧です。人気順・新着順で探せます。`,
          en: `Explore novels tagged "${tagName}" by popularity and recency.`,
        });

    document.title = nextTitle;
    if (metaDescription) {
      metaDescription.setAttribute("content", nextDescription);
    }

    return () => {
      document.title = previousTitle;
      if (metaDescription) {
        if (previousDescription == null) metaDescription.removeAttribute("content");
        else metaDescription.setAttribute("content", previousDescription);
      }
    };
  }, [isTagIndex, tagName, t, lang]);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError("");
        if (isTagIndex) {
          const res = await fetch(`${API_BASE}/api/tags`);
          const data = await res.json().catch(() => []);
          if (!res.ok) {
            throw new Error(
              data?.detail || t({ ja: "タグ一覧の取得に失敗しました。", en: "Failed to load tags." })
            );
          }
          setTagList(Array.isArray(data) ? data : []);
          setTagDetail(null);
          setRelatedTags([]);
          setNovels([]);
          setTagFollowState({ isFollowing: false, followerCount: 0 });
          setTagFollowError("");
          return;
        }

        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const authHeaders = token ? { Authorization: `Bearer ${token}` } : undefined;
        const encodedTag = encodeURIComponent(tagName);
        const requests = [
          fetch(`${API_BASE}/api/tags/${encodedTag}`),
          fetch(`${API_BASE}/api/tags/${encodedTag}/related`),
          fetch(`${API_BASE}/api/tags/${encodedTag}/novels?sort=${encodeURIComponent(sort)}`),
        ];
        if (authHeaders) {
          requests.push(
            fetch(`${API_BASE}/api/tags/${encodedTag}/follow-status`, { headers: authHeaders })
          );
        }
        const responses = await Promise.all(requests);
        const [resDetail, resRelated, resNovels, resFollowStatus] = responses;
        const detailData = await resDetail.json().catch(() => ({}));
        const relatedData = await resRelated.json().catch(() => []);
        const novelsData = await resNovels.json().catch(() => []);
        const followStatusData = resFollowStatus
          ? await resFollowStatus.json().catch(() => ({}))
          : null;
        if (!resDetail.ok) {
          throw new Error(
            detailData?.detail || t({ ja: "タグ情報の取得に失敗しました。", en: "Failed to load tag." })
          );
        }
        if (!resRelated.ok) {
          throw new Error(
            relatedData?.detail ||
              t({ ja: "関連タグの取得に失敗しました。", en: "Failed to load related tags." })
          );
        }
        if (!resNovels.ok) {
          throw new Error(
            novelsData?.detail || t({ ja: "作品一覧の取得に失敗しました。", en: "Failed to load novels." })
          );
        }
        setTagDetail(detailData || null);
        setRelatedTags(Array.isArray(relatedData) ? relatedData : []);
        setNovels(Array.isArray(novelsData) ? novelsData : []);
        if (resFollowStatus && resFollowStatus.ok) {
          setTagFollowState({
            isFollowing: followStatusData?.is_following === true,
            followerCount:
              typeof followStatusData?.follower_count === "number"
                ? followStatusData.follower_count
                : Number(detailData?.follower_count || 0),
          });
        } else {
          setTagFollowState({
            isFollowing: false,
            followerCount: Number(detailData?.follower_count || 0),
          });
        }
      } catch (e) {
        console.error(e);
        setError(e.message || t({ ja: "エラーが発生しました。", en: "An error occurred." }));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [isTagIndex, sort, tagName, t]);

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;
  if (error) return <p style={{ color: "red" }}>{error}</p>;

  const canFollowTag =
    typeof window !== "undefined" && !!localStorage.getItem("token") && !isTagIndex;

  const handleToggleTagFollow = async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      setTagFollowError(t({ ja: "ログインが必要です。", en: "Login required." }));
      return;
    }
    try {
      setTagFollowLoading(true);
      setTagFollowError("");
      const encodedTag = encodeURIComponent(tagName);
      const shouldUnfollow = !!tagFollowState.isFollowing;
      const res = await fetch(`${API_BASE}/api/tags/${encodedTag}/follow`, {
        method: shouldUnfollow ? "DELETE" : "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({
              ja: "タグのフォロー更新に失敗しました。",
              en: "Failed to update tag follow status.",
            })
        );
      }
      setTagFollowState({
        isFollowing: data?.is_following === true,
        followerCount:
          typeof data?.follower_count === "number"
            ? data.follower_count
            : tagFollowState.followerCount,
      });
      setTagDetail((prev) =>
        prev
          ? {
              ...prev,
              follower_count:
                typeof data?.follower_count === "number"
                  ? data.follower_count
                  : prev.follower_count,
            }
          : prev
      );
    } catch (e) {
      console.error(e);
      setTagFollowError(
        e.message ||
          t({
            ja: "タグのフォロー更新に失敗しました。",
            en: "Failed to update tag follow status.",
          })
      );
    } finally {
      setTagFollowLoading(false);
    }
  };

  if (isTagIndex) {
    return (
      <div>
        <h1 style={{ marginBottom: 12 }}>{t({ ja: "タグ一覧", en: "Tag List" })}</h1>
        {tagList.length === 0 ? (
          <p>{t({ ja: "タグがありません。", en: "No tags found." })}</p>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {tagList.map((tag) => (
              <Link
                key={tag.id ?? tag.name}
                to={`/tags/${encodeURIComponent(tag.name)}`}
                className="novel-card"
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 8,
                  textDecoration: "none",
                }}
              >
                <span>#{tag.name}</span>
                <span style={{ color: "var(--muted-text)" }}>
                  {t({ ja: "{{count}} 件", en: "{{count}} novels" }, { count: tag.novel_count ?? 0 })}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ marginBottom: 8 }}>
        #{tagDetail?.name || tagName}
      </h1>
      <p style={{ color: "var(--muted-text)", marginTop: 0 }}>
        {tagDetail?.description ||
          t({ ja: "このタグに関連する作品一覧です。", en: "A list of novels for this tag." })}{" "}
        ({t({ ja: "作品数", en: "Novels" })}: {tagDetail?.novel_count ?? novels.length})
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <span style={{ color: "var(--muted-text)", fontSize: 13 }}>
          {t({ ja: "フォロワー", en: "Followers" })}: {tagFollowState.followerCount}
        </span>
        {canFollowTag ? (
          <button
            type="button"
            className="btn btn-border"
            onClick={handleToggleTagFollow}
            disabled={tagFollowLoading}
          >
            {tagFollowLoading
              ? t({ ja: "更新中...", en: "Updating..." })
              : tagFollowState.isFollowing
                ? t({ ja: "フォロー中", en: "Following" })
                : t({ ja: "フォロー", en: "Follow" })}
          </button>
        ) : (
          <span style={{ color: "var(--muted-text)", fontSize: 12 }}>
            {t({ ja: "フォローするにはログインしてください。", en: "Login to follow this tag." })}
          </span>
        )}
      </div>
      {tagFollowError && <p style={{ color: "red", marginTop: 0 }}>{tagFollowError}</p>}

      {Array.isArray(tagDetail?.popular_novels) && tagDetail.popular_novels.length > 0 && (
        <section style={{ marginBottom: 20 }}>
          <h3>{t({ ja: "人気作品", en: "Top Works" })}</h3>
          <div className="novel-grid">
            {tagDetail.popular_novels.map((novel) => (
              <NovelCard
                key={`tag-top-${novel.id}`}
                novel={novel}
                t={t}
                apiBase={API_BASE}
                descriptionMax={90}
                showDescription={false}
                maxTags={3}
                footer={
                  <Link to={`/novels/${novel.id}`} className="btn btn-border">
                    {t({ ja: "読む", en: "Read" })}
                  </Link>
                }
              />
            ))}
          </div>
        </section>
      )}

      {relatedTags.length > 0 && (
        <section style={{ marginBottom: 20 }}>
          <h3>{t({ ja: "関連タグ", en: "Related Tags" })}</h3>
          <div className="tag-chip-row">
            {relatedTags.map((tag) => (
              <Link
                key={tag.id ?? tag.name}
                to={`/tags/${encodeURIComponent(tag.name)}`}
                style={{ textDecoration: "none" }}
              >
                #{tag.name} ({tag.co_occurrence_count ?? 0})
              </Link>
            ))}
          </div>
        </section>
      )}

      <section>
        <h3>{t({ ja: "作品一覧", en: "Novels" })}</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {SORT_OPTIONS.map((option) => (
            <button
              key={option.key}
              type="button"
              className="btn btn-border"
              onClick={() => setSort(option.key)}
              disabled={sort === option.key}
              style={sort === option.key ? { opacity: 0.7 } : undefined}
            >
              {lang === "en" ? option.en : option.ja}
            </button>
          ))}
        </div>

        {novels.length === 0 ? (
          <p>{t({ ja: "作品がありません。", en: "No novels found." })}</p>
        ) : (
          <div className="novel-grid">
            {novels.map((novel) => (
              <NovelCard
                key={`tag-novel-${novel.id}`}
                novel={novel}
                t={t}
                apiBase={API_BASE}
                descriptionMax={140}
                maxTags={4}
                footer={
                  <Link to={`/novels/${novel.id}`} className="btn btn-border">
                    {t({ ja: "続きを読む", en: "Read more" })}
                  </Link>
                }
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
