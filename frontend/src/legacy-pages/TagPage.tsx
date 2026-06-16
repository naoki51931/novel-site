import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import NovelCard from "../components/NovelCard";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";
import { filterR18Novels, useShowR18ByDisplaySetting } from "../lib/r18Display";
import { applySeoMeta, buildSeoDescription } from "../lib/seoMeta";

const API_BASE = getApiBase();

type TagRecord = {
  id?: number | string | null;
  name?: string | null;
  novel_count?: number | null;
  description?: string | null;
  seo_title?: string | null;
  seo_description?: string | null;
  seo_lead?: string | null;
  seo_body?: string | null;
  seo_keywords?: string[] | null;
  seo_r18_title?: string | null;
  seo_r18_description?: string | null;
  seo_r18_lead?: string | null;
  seo_r18_body?: string | null;
  seo_r18_keywords?: string[] | null;
  follower_count?: number | null;
  r18_priority_score?: number | null;
  popular_novels?: unknown[];
  recent_novels?: unknown[];
};

type RelatedTag = {
  id?: number | string | null;
  name?: string | null;
  co_occurrence_count?: number | null;
  r18_priority_score?: number | null;
};

type TagFollowState = {
  isFollowing: boolean;
  followerCount: number;
};

const safeDecode = (value: string | undefined) => {
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

const READ_TIME_OPTIONS = [
  { key: "all", ja: "すべて", en: "All" },
  { key: "3", ja: "3分で読める", en: "Up to 3 min" },
  { key: "5", ja: "5分で読める", en: "Up to 5 min" },
];

export default function TagPage() {
  const { slug } = useParams();
  const location = useLocation();
  const { t, lang } = useI18n();
  const showR18 = useShowR18ByDisplaySetting();
  const tagName = useMemo(() => safeDecode(slug).trim(), [slug]);
  const isTagIndex = !tagName;
  const currentAgeLimit = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return (params.get("age_limit") ?? "").trim().toLowerCase();
  }, [location.search]);
  const urlForcesR18 = currentAgeLimit === "r18";
  const effectiveShowR18 = showR18 || urlForcesR18;
  const tagLinkSuffix = urlForcesR18 ? "?age_limit=r18" : "";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sort, setSort] = useState("popular");
  const [readTimeFilter, setReadTimeFilter] = useState("all");
  const [tagList, setTagList] = useState<TagRecord[]>([]);
  const [tagDetail, setTagDetail] = useState<TagRecord | null>(null);
  const [relatedTags, setRelatedTags] = useState<RelatedTag[]>([]);
  const [novels, setNovels] = useState<any[]>([]);
  const [tagFollowState, setTagFollowState] = useState<TagFollowState>({
    isFollowing: false,
    followerCount: 0,
  });
  const [tagFollowLoading, setTagFollowLoading] = useState(false);
  const [tagFollowError, setTagFollowError] = useState("");

  useEffect(() => {
    if (typeof document === "undefined") return undefined;

    const resolvedTitle =
      !isTagIndex && urlForcesR18 && tagDetail?.seo_r18_title
        ? String(tagDetail.seo_r18_title)
        : !isTagIndex && tagDetail?.seo_title
          ? String(tagDetail.seo_title)
          : isTagIndex
            ? t({ ja: "タグ一覧｜小説投稿サイトLexis", en: "Tag List | Lexis" })
            : urlForcesR18
              ? t({
                  ja: `${tagName}のエロ小説・R18小説一覧｜小説投稿サイトLexis`,
                  en: `R18 novels tagged "${tagName}" | Lexis`,
                })
              : t({
                  ja: `${tagName}小説一覧｜小説投稿サイトLexis`,
                  en: `Novels tagged "${tagName}" | Lexis`,
                });
    const resolvedDescription =
      !isTagIndex && urlForcesR18 && tagDetail?.seo_r18_description
        ? String(tagDetail.seo_r18_description)
        : !isTagIndex && tagDetail?.seo_description
          ? String(tagDetail.seo_description)
          : isTagIndex
            ? t({
                ja: "人気タグから小説を探せます。タグ経由で新しい作品と作者に出会えます。",
                en: "Browse novels by popular tags and discover new works and authors.",
              })
            : urlForcesR18
              ? t({
                  ja: `「${tagName}」タグのR18小説・エロ小説一覧です。${tagName}の成人向け作品を人気順・新着順で探せます。`,
                  en: `Explore R18 novels tagged "${tagName}" by popularity and recency.`,
                })
              : t({
                  ja: `「${tagName}」タグの作品一覧です。人気順・新着順で探せます。`,
                  en: `Explore novels tagged "${tagName}" by popularity and recency.`,
                });
    const nextTitle = isTagIndex
      ? resolvedTitle
      : resolvedTitle;
    const nextDescription = resolvedDescription;
    const canonicalPath = isTagIndex
      ? "/tags"
      : `/tags/${encodeURIComponent(tagName)}${urlForcesR18 ? "?age_limit=r18" : ""}`;
    const apiKeywords = urlForcesR18 ? tagDetail?.seo_r18_keywords : tagDetail?.seo_keywords;
    const keywords = isTagIndex
      ? ["タグ一覧", "小説タグ", "r18", "エロ"]
      : Array.isArray(apiKeywords) && apiKeywords.length > 0
        ? apiKeywords.map((value) => String(value || "").trim()).filter(Boolean)
        : urlForcesR18
          ? [tagName, `${tagName} エロ小説`, `エロ小説 ${tagName}`, `${tagName} R18小説`, `R18小説 ${tagName}`, "エロ小説", "R18小説"]
          : [tagName, `${tagName} 小説`, `${tagName} タグ`, "小説", "Web小説"];
    return applySeoMeta({
      title: nextTitle,
      description: buildSeoDescription(nextDescription),
      keywords,
      canonicalPath,
      ogType: "website",
    });
  }, [isTagIndex, tagName, tagDetail, t, lang, urlForcesR18]);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError("");
        if (isTagIndex) {
          const tagParams = new URLSearchParams();
          if (currentAgeLimit) tagParams.set("age_limit", currentAgeLimit);
          const res = await fetch(`${API_BASE}/api/tags${tagParams.toString() ? `?${tagParams.toString()}` : ""}`);
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
        const novelsParams = new URLSearchParams({ sort });
        if (currentAgeLimit) novelsParams.set("age_limit", currentAgeLimit);
        const requests = [
          fetch(`${API_BASE}/api/tags/${encodedTag}`),
          fetch(`${API_BASE}/api/tags/${encodedTag}/related?${novelsParams.toString()}`),
          fetch(`${API_BASE}/api/tags/${encodedTag}/novels?${novelsParams.toString()}`),
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
        setError(getErrorMessage(e, t({ ja: "エラーが発生しました。", en: "An error occurred." })));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [currentAgeLimit, isTagIndex, sort, tagName, t]);

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;
  if (error) return <p style={{ color: "red" }}>{error}</p>;

  const filterByAgeLimit = (items: any[]) => {
    const list = Array.isArray(items) ? items : [];
    if (currentAgeLimit === "r18") {
      return list.filter((item) => String(item?.age_limit || "all").toLowerCase() === "r18");
    }
    if (currentAgeLimit === "r15") {
      return list.filter((item) => String(item?.age_limit || "all").toLowerCase() === "r15");
    }
    if (currentAgeLimit === "all") {
      return list.filter((item) => String(item?.age_limit || "all").toLowerCase() === "all");
    }
    return list;
  };
  const canFollowTag =
    typeof window !== "undefined" && !!localStorage.getItem("token") && !isTagIndex;
  const tagSearchParams = new URLSearchParams({ q: tagName });
  if (currentAgeLimit) tagSearchParams.set("age_limit", currentAgeLimit);
  const tagSearchUrl = `/?${tagSearchParams.toString()}`;
  const popularNovelsVisible = filterR18Novels(filterByAgeLimit(tagDetail?.popular_novels as any[]), effectiveShowR18);
  const recentNovelsVisible = filterR18Novels(filterByAgeLimit(tagDetail?.recent_novels as any[]), effectiveShowR18);
  const novelsVisible = filterR18Novels(filterByAgeLimit(novels), effectiveShowR18).filter((novel: any) => {
    const limit = Number(readTimeFilter);
    if (!Number.isFinite(limit) || limit <= 0) {
      return true;
    }
    const minutes = Number(novel?.estimated_read_minutes || 0);
    return minutes > 0 && minutes <= limit;
  });

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
        getErrorMessage(
          e,
          t({
            ja: "タグのフォロー更新に失敗しました。",
            en: "Failed to update tag follow status.",
          })
        )
      );
    } finally {
      setTagFollowLoading(false);
    }
  };

  if (isTagIndex) {
    return (
      <div>
        <h1 style={{ marginBottom: 12 }}>{urlForcesR18 ? t({ ja: "R18タグ一覧", en: "R18 Tag List" }) : t({ ja: "タグ一覧", en: "Tag List" })}</h1>
        {urlForcesR18 ? (
          <p style={{ color: "var(--muted-text)", marginTop: 0 }}>
            {t({
              ja: "R18作品に結び付くタグを、性癖・成人向けテーマに近いものから優先して表示しています。",
              en: "Tags connected to R18 works are prioritized by adult-theme relevance.",
            })}
          </p>
        ) : null}
        {tagList.length === 0 ? (
          <p>{t({ ja: "タグがありません。", en: "No tags found." })}</p>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {tagList.map((tag) => (
              <Link
                key={tag.id ?? tag.name}
                to={`/tags/${encodeURIComponent(String(tag.name ?? ""))}${tagLinkSuffix}`}
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
        {(urlForcesR18 ? tagDetail?.seo_r18_lead : tagDetail?.seo_lead) ||
          tagDetail?.description ||
          t({ ja: "このタグに関連する作品一覧です。", en: "A list of novels for this tag." })}{" "}
        ({t({ ja: "作品数", en: "Novels" })}: {tagDetail?.novel_count ?? novels.length})
      </p>
      {(urlForcesR18 ? tagDetail?.seo_r18_body : tagDetail?.seo_body) ? (
        <section
          style={{
            marginBottom: 16,
            padding: "14px 16px",
            border: "1px solid rgba(15, 23, 42, 0.08)",
            borderRadius: 12,
            background: "linear-gradient(180deg, rgba(255,255,255,0.96), rgba(248,250,252,0.96))",
          }}
        >
          <h2 style={{ marginTop: 0, marginBottom: 8, fontSize: "1rem" }}>
            {t({ ja: "タグの見どころ", en: "About this tag" })}
          </h2>
          <p style={{ margin: 0, lineHeight: 1.8 }}>{urlForcesR18 ? tagDetail?.seo_r18_body : tagDetail?.seo_body}</p>
        </section>
      ) : null}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <span style={{ color: "var(--muted-text)", fontSize: 13 }}>
          {t({ ja: "フォロワー", en: "Followers" })}: {tagFollowState.followerCount}
        </span>
        <Link
          to={`/tags/${encodeURIComponent(tagName)}`}
          className="btn btn-border"
          style={!currentAgeLimit ? { opacity: 0.7 } : undefined}
        >
          {t({ ja: "全年齢表示", en: "All ages" })}
        </Link>
        <Link
          to={`/tags/${encodeURIComponent(tagName)}?age_limit=r18`}
          className="btn btn-border"
          style={urlForcesR18 ? { opacity: 0.7 } : undefined}
        >
          {t({ ja: "R18表示URL", en: "R18 URL" })}
        </Link>
        <Link to={tagSearchUrl} className="btn btn-border">
          {t({ ja: "タグ名で検索", en: "Search this tag name" })}
        </Link>
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
      <p style={{ color: "var(--muted-text)", fontSize: 13, marginTop: -4, marginBottom: 16 }}>
        {t({
          ja: "Weaviateを使っているので、普通の検索よりも広い検索ができます。",
          en: "Because search uses Weaviate, it can search more broadly than regular exact matching.",
        })}
      </p>
      {tagFollowError && <p style={{ color: "red", marginTop: 0 }}>{tagFollowError}</p>}

      {popularNovelsVisible.length > 0 && (
        <section style={{ marginBottom: 20 }}>
          <h3>{t({ ja: "人気作品", en: "Top Works" })}</h3>
          <div className="novel-grid">
            {popularNovelsVisible.map((novel) => (
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

      {recentNovelsVisible.length > 0 && (
        <section style={{ marginBottom: 20 }}>
          <h3>{t({ ja: "新着作品", en: "New Works" })}</h3>
          <div className="novel-grid">
            {recentNovelsVisible.map((novel: any) => (
              <NovelCard
                key={`tag-recent-${novel.id}`}
                novel={novel}
                t={t}
                apiBase={API_BASE}
                descriptionMax={100}
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
          <h3>{urlForcesR18 ? t({ ja: "関連R18タグ・性癖タグ", en: "Related R18 Tags" }) : t({ ja: "関連タグ", en: "Related Tags" })}</h3>
          <div className="tag-chip-row">
            {relatedTags.map((tag) => (
              <Link
                key={tag.id ?? tag.name}
                to={`/tags/${encodeURIComponent(String(tag.name ?? ""))}${tagLinkSuffix}`}
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
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {READ_TIME_OPTIONS.map((option) => (
            <button
              key={option.key}
              type="button"
              className="btn btn-border"
              onClick={() => setReadTimeFilter(option.key)}
              disabled={readTimeFilter === option.key}
              style={readTimeFilter === option.key ? { opacity: 0.7 } : undefined}
            >
              {lang === "en" ? option.en : option.ja}
            </button>
          ))}
        </div>

        {novelsVisible.length === 0 ? (
          <p>{t({ ja: "作品がありません。", en: "No novels found." })}</p>
        ) : (
          <div className="novel-grid">
            {novelsVisible.map((novel) => (
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
