// frontend/src/pages/Home.jsx
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import NovelCard from "../components/NovelCard";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";
import { filterR18Novels, useShowR18ByDisplaySetting } from "../lib/r18Display";
import { hasRecentEpisodeActivity } from "../lib/freshness";

const API_BASE = getApiBase();

type HomeProps = {
  query?: string;
  excludeQuery?: string;
  tag?: string;
  sort?: string;
  ageLimit?: string;
  creativeType?: string;
  showRanking?: boolean;
  rankingOnly?: boolean;
};

type TagItem = {
  id?: number | string | null;
  name?: string | null;
  novel_count?: number | null;
};

type RecommendationReason = {
  key?: string | null;
  value?: number | null;
};

type HomeNovelTag = NonNullable<HomeNovel["tags"]>[number];

type HomeNovel = {
  id: number | string;
  title?: string | null;
  description?: string | null;
  created_at?: string | null;
  cover_image_url?: string | null;
  author_username?: string | null;
  creative_type?: string | null;
  age_limit?: string | null;
  view_count?: number | null;
  like_count?: number | null;
  favorite_count?: number | null;
  comment_count?: number | null;
  total_char_count?: number | null;
  rank?: number | null;
  ranking_score?: number | null;
  period_likes?: number | null;
  period_favorites?: number | null;
  period_comments?: number | null;
  is_liked?: boolean | null;
  is_favorited?: boolean | null;
  tags?:
    | Array<string | { id?: number | string | null; name?: string | null } | null | undefined>
    | null;
  recommendation_reasons?: RecommendationReason[] | null;
  recommendation_score?: number | null;
  latest_episode_activity_at?: string | null;
  latest_episode_created_at?: string | null;
};

export default function Home({
  query = "",
  excludeQuery = "",
  tag = "",
  sort = "new",
  ageLimit = "",
  creativeType = "",
  showRanking = true,
  rankingOnly = false,
}: HomeProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { t, lang } = useI18n();
  const showR18 = useShowR18ByDisplaySetting();
  const [novels, setNovels] = useState<HomeNovel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ranking, setRanking] = useState<HomeNovel[]>([]);
  const [rankingSort, setRankingSort] = useState("likes");
  const [rankingPeriod, setRankingPeriod] = useState("weekly");
  const [rankingCreativeType, setRankingCreativeType] = useState("");
  const [rankingLoading, setRankingLoading] = useState(true);
  const [rankingError, setRankingError] = useState("");
  const [rankingEnabled, setRankingEnabled] = useState(!!rankingOnly);
  const [rankingAccessDenied, setRankingAccessDenied] = useState(false);
  const [premiumChecked, setPremiumChecked] = useState(false);
  const [recommendedNovels, setRecommendedNovels] = useState<HomeNovel[]>([]);
  const [recommendedLoading, setRecommendedLoading] = useState(false);
  const [recommendedError, setRecommendedError] = useState("");
  const [followingFeedNovels, setFollowingFeedNovels] = useState<HomeNovel[]>([]);
  const [followingFeedLoading, setFollowingFeedLoading] = useState(false);
  const [followingFeedError, setFollowingFeedError] = useState("");
  const [followingTagsFeedNovels, setFollowingTagsFeedNovels] = useState<HomeNovel[]>([]);
  const [followingTagsFeedLoading, setFollowingTagsFeedLoading] = useState(false);
  const [followingTagsFeedError, setFollowingTagsFeedError] = useState("");
  const [newFeedNovels, setNewFeedNovels] = useState<HomeNovel[]>([]);
  const [newFeedLoading, setNewFeedLoading] = useState(false);
  const [newFeedError, setNewFeedError] = useState("");
  const [trendingFeedNovels, setTrendingFeedNovels] = useState<HomeNovel[]>([]);
  const [trendingFeedLoading, setTrendingFeedLoading] = useState(false);
  const [trendingFeedError, setTrendingFeedError] = useState("");
  const [historyFeedNovels, setHistoryFeedNovels] = useState<HomeNovel[]>([]);
  const [historyFeedLoading, setHistoryFeedLoading] = useState(false);
  const [historyFeedError, setHistoryFeedError] = useState("");
  const [pickupFeedNovels, setPickupFeedNovels] = useState<HomeNovel[]>([]);
  const [pickupFeedLoading, setPickupFeedLoading] = useState(false);
  const [pickupFeedError, setPickupFeedError] = useState("");
  const [trendingTags, setTrendingTags] = useState<TagItem[]>([]);
  const [trendingTagsLoading, setTrendingTagsLoading] = useState(false);
  const [trendingTagsError, setTrendingTagsError] = useState("");
  const [quickEpisodeCreating, setQuickEpisodeCreating] = useState(false);
  const [rankingShareMessage, setRankingShareMessage] = useState("");
  const rankingSortOptions = new Set(["score", "rising", "likes", "favorites", "views", "comments"]);
  const rankingPeriodOptions = new Set(["daily", "weekly", "monthly"]);
  const rankingCreativeTypeOptions = new Set(["", "original", "fanfic"]);
  useEffect(() => {
    if (!rankingOnly || typeof document === "undefined") return undefined;
    const previousTitle = document.title;
    const metaDescription = document.querySelector('meta[name="description"]');
    const previousDescription = metaDescription?.getAttribute("content");
    const nextTitle = t({ ja: "小説ランキング｜小説投稿サイトLexis", en: "Novel Ranking | Lexis" });
    const nextDescription = t({
      ja: "日間・週間・月間のランキングをタグ別やoriginal/fanfic別で見られます。",
      en: "Browse daily, weekly, and monthly rankings by tag and by original/fanfic.",
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
  }, [rankingOnly, t, lang]);

  useEffect(() => {
    if (!rankingOnly || typeof document === "undefined" || typeof window === "undefined") {
      return undefined;
    }
    const head = document.head;
    const absoluteUrl = `${window.location.origin}${location.pathname}${location.search}`;

    let canonical = document.querySelector('link[rel="canonical"]');
    const hadCanonical = !!canonical;
    if (!canonical) {
      canonical = document.createElement("link");
      canonical.setAttribute("rel", "canonical");
      head.appendChild(canonical);
    }
    const prevCanonicalHref = canonical.getAttribute("href");
    canonical.setAttribute("href", absoluteUrl);

    let ogUrl = document.querySelector('meta[property="og:url"]');
    const hadOgUrl = !!ogUrl;
    if (!ogUrl) {
      ogUrl = document.createElement("meta");
      ogUrl.setAttribute("property", "og:url");
      head.appendChild(ogUrl);
    }
    const prevOgUrlContent = ogUrl.getAttribute("content");
    ogUrl.setAttribute("content", absoluteUrl);

    return () => {
      if (canonical) {
        if (!hadCanonical) canonical.remove();
        else if (prevCanonicalHref == null) canonical.removeAttribute("href");
        else canonical.setAttribute("href", prevCanonicalHref);
      }
      if (ogUrl) {
        if (!hadOgUrl) ogUrl.remove();
        else if (prevOgUrlContent == null) ogUrl.removeAttribute("content");
        else ogUrl.setAttribute("content", prevOgUrlContent);
      }
    };
  }, [rankingOnly, location.pathname, location.search]);

  useEffect(() => {
    const fetchNovels = async () => {
      if (rankingOnly) {
        setNovels([]);
        setLoading(false);
        setError("");
        return;
      }
      try {
        setLoading(true);
        setError("");

        const params = new URLSearchParams(location.search);
        const urlQuery = (params.get("q") ?? "").trim();
        const urlExclude = (params.get("exclude") ?? "").trim();
        const urlTag = (params.get("tag") ?? "").trim();
        const urlSort = (params.get("sort") ?? "").trim();
        const urlAgeLimit = (params.get("age_limit") ?? "").trim();
        const urlCreativeType = (params.get("creative_type") ?? "").trim();
        const effectiveTag = urlTag || (tag ?? "").trim();
        const effectiveQuery = urlQuery || (query ?? "").trim();
        const effectiveExclude = urlExclude || (excludeQuery ?? "").trim();
        const effectiveSort = urlSort || (sort ?? "new").trim() || "new";
        const effectiveAgeLimit = urlAgeLimit || (ageLimit ?? "").trim();
        const effectiveCreativeType = urlCreativeType || (creativeType ?? "").trim();

        let url = `${API_BASE}/api/public/novels`;
        const apiParams = new URLSearchParams();
        if (effectiveQuery) apiParams.set("q", effectiveQuery);
        if (effectiveExclude) apiParams.set("exclude", effectiveExclude);
        if (effectiveTag) apiParams.set("tag", effectiveTag);
        if (effectiveSort) apiParams.set("sort", effectiveSort);
        if (effectiveAgeLimit) apiParams.set("age_limit", effectiveAgeLimit);
        if (effectiveCreativeType) apiParams.set("creative_type", effectiveCreativeType);
        if (["en", "zh-cn", "zh-tw", "ko"].includes(lang)) apiParams.set("lang", lang);
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
          let detail = "";
          try {
            const body = await res.json();
            detail = String(body?.detail || "").trim();
          } catch {
            detail = "";
          }
          throw new Error(
            detail || t({ ja: "小説一覧の取得に失敗しました", en: "Failed to load novels." })
          );
        }

        const data = await res.json();
        const items = Array.isArray(data) ? data : [];

        if (effectiveSort === "new") {
          const sorted = items.slice().sort((a: HomeNovel, b: HomeNovel) => {
            const ad = a.created_at ? new Date(a.created_at).getTime() : 0;
            const bd = b.created_at ? new Date(b.created_at).getTime() : 0;
            return bd - ad;
          });
          setNovels(sorted);
        } else {
          setNovels(items);
        }
      } catch (err) {
        console.error(err);
        setError(getErrorMessage(err, t({ ja: "エラーが発生しました", en: "An error occurred." })));
      } finally {
        setLoading(false);
      }
    };

    fetchNovels();
  }, [query, excludeQuery, tag, sort, ageLimit, creativeType, location.search, lang, rankingOnly]); // ← 検索語 or URL が変わるたびに再取得

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const sortParam = (params.get("ranking_sort") ?? "").trim().toLowerCase();
    const periodParam = (params.get("ranking_period") ?? "").trim().toLowerCase();
    const ctParam = (params.get("ranking_creative_type") ?? "").trim().toLowerCase();
    if (rankingSortOptions.has(sortParam) && sortParam && sortParam !== rankingSort) {
      setRankingSort(sortParam);
    }
    if (rankingPeriodOptions.has(periodParam) && periodParam && periodParam !== rankingPeriod) {
      setRankingPeriod(periodParam);
    }
    if (rankingCreativeTypeOptions.has(ctParam) && ctParam !== rankingCreativeType) {
      setRankingCreativeType(ctParam);
    }
  }, [location.search]);

  useEffect(() => {
    if (!showRanking) {
      setRanking([]);
      setRankingLoading(false);
      setRankingError("");
      setRankingAccessDenied(false);
      return;
    }
    const fetchRanking = async () => {
      if (!rankingEnabled) {
        setRanking([]);
        setRankingLoading(false);
        setRankingError("");
        setRankingAccessDenied(false);
        return;
      }

      try {
        setRankingLoading(true);
        setRankingError("");
        setRankingAccessDenied(false);

        const params = new URLSearchParams(location.search);
        const urlQuery = (params.get("q") ?? "").trim();
        const urlExclude = (params.get("exclude") ?? "").trim();
        const urlTag = (params.get("tag") ?? "").trim();
        const urlSort = (params.get("sort") ?? "").trim();
        const urlAgeLimit = (params.get("age_limit") ?? "").trim();
        const urlCreativeType = (params.get("creative_type") ?? "").trim();
        const effectiveTag = urlTag || (tag ?? "").trim();
        const effectiveQuery = urlQuery || (query ?? "").trim();
        const effectiveExclude = urlExclude || (excludeQuery ?? "").trim();
        const effectiveSort = urlSort || (sort ?? "new").trim() || "new";
        const effectiveAgeLimit = urlAgeLimit || (ageLimit ?? "").trim();
        const effectiveCreativeType = urlCreativeType || (creativeType ?? "").trim();

        const token =
          localStorage.getItem("token") ||
          localStorage.getItem("access_token");
        const headers = token ? { Authorization: "Bearer " + token } : undefined;

        const apiParams = new URLSearchParams();
        apiParams.set("sort", rankingSort);
        apiParams.set("period", rankingPeriod);
        if (effectiveQuery) apiParams.set("q", effectiveQuery);
        if (effectiveExclude) apiParams.set("exclude", effectiveExclude);
        if (effectiveTag) apiParams.set("tag", effectiveTag);
        if (rankingCreativeType) apiParams.set("creative_type", rankingCreativeType);
        if (effectiveAgeLimit) apiParams.set("age_limit", effectiveAgeLimit);
        else if (effectiveCreativeType) apiParams.set("creative_type", effectiveCreativeType);
        if (["en", "zh-cn", "zh-tw", "ko"].includes(lang)) apiParams.set("lang", lang);
        const qs = apiParams.toString();
        let url = `${API_BASE}/api/public/novels/ranking`;
        if (qs) url += `?${qs}`;

        const res = await fetch(
          url,
          headers ? { headers, cache: "no-store" } : { cache: "no-store" }
        );
        if (res.status === 403) {
          setRanking([]);
          setRankingError("");
          setRankingAccessDenied(true);
          return;
        }
        if (!res.ok) {
          throw new Error(
            t({ ja: "ランキングの取得に失敗しました", en: "Failed to load ranking." })
          );
        }
        const data = await res.json().catch(() => []);
        setRankingAccessDenied(false);
        setRanking(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error(err);
        setRankingError(
          getErrorMessage(err, t({ ja: "ランキングの取得に失敗しました", en: "Failed to load ranking." }))
        );
      } finally {
        setRankingLoading(false);
      }
    };

    fetchRanking();
  }, [
    rankingSort,
    rankingPeriod,
    rankingCreativeType,
    rankingEnabled,
    location.search,
    query,
    excludeQuery,
    tag,
    sort,
    ageLimit,
    creativeType,
    showRanking,
    lang,
  ]);

  const applyRankingStateToUrl = (
    next: { sort?: string; period?: string; creativeType?: string } = {}
  ) => {
    const params = new URLSearchParams(location.search);
    const nextSort = String(next.sort ?? rankingSort).trim();
    const nextPeriod = String(next.period ?? rankingPeriod).trim();
    const nextCreativeType = String(next.creativeType ?? rankingCreativeType).trim();
    params.set("ranking_sort", nextSort);
    params.set("ranking_period", nextPeriod);
    if (nextCreativeType) params.set("ranking_creative_type", nextCreativeType);
    else params.delete("ranking_creative_type");
    const search = params.toString();
    navigate(
      {
        pathname: location.pathname,
        search: search ? `?${search}` : "",
      },
      { replace: false }
    );
  };
  const buildRankingPresetSearch = ({
    sort: nextSort,
    period: nextPeriod,
    creativeType: nextCreativeType,
  }: {
    sort?: string;
    period?: string;
    creativeType?: string;
  }) => {
    const params = new URLSearchParams(location.search);
    params.set("ranking_sort", String(nextSort || "likes"));
    params.set("ranking_period", String(nextPeriod || "weekly"));
    if (String(nextCreativeType || "").trim()) {
      params.set("ranking_creative_type", String(nextCreativeType).trim());
    } else {
      params.delete("ranking_creative_type");
    }
    return `?${params.toString()}`;
  };

  useEffect(() => {
    const fetchPremium = async () => {
      const token =
        localStorage.getItem("token") || localStorage.getItem("access_token");
      if (!token) {
        setPremiumChecked(true);
        return;
      }

      try {
        const res = await fetch(`${API_BASE}/api/users/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          setPremiumChecked(true);
          return;
        }
        await res.json().catch(() => ({}));
      } catch (err) {
        console.error(err);
      } finally {
        setPremiumChecked(true);
      }
    };

    fetchPremium();
  }, [location.pathname]);

  useEffect(() => {
    const fetchFollowingFeed = async () => {
      const token =
        localStorage.getItem("token") || localStorage.getItem("access_token");
      if (!token) {
        setFollowingFeedNovels([]);
        setFollowingFeedLoading(false);
        setFollowingFeedError("");
        return;
      }

      const params = new URLSearchParams(location.search);
      const urlQuery = (params.get("q") ?? "").trim();
      const urlExclude = (params.get("exclude") ?? "").trim();
      const urlTag = (params.get("tag") ?? "").trim();
      const urlSort = (params.get("sort") ?? "").trim();
      const urlAgeLimit = (params.get("age_limit") ?? "").trim();
      const urlCreativeType = (params.get("creative_type") ?? "").trim();
      const effectiveTag = urlTag || (tag ?? "").trim();
      const effectiveQuery = urlQuery || (query ?? "").trim();
      const effectiveExclude = urlExclude || (excludeQuery ?? "").trim();
      const effectiveSort = urlSort || (sort ?? "new").trim() || "new";
      const effectiveAgeLimit = urlAgeLimit || (ageLimit ?? "").trim();
      const effectiveCreativeType = urlCreativeType || (creativeType ?? "").trim();
      const isTopFeed =
        !effectiveTag &&
        !effectiveQuery &&
        !effectiveExclude &&
        !effectiveAgeLimit &&
        !effectiveCreativeType &&
        effectiveSort === "new";
      if (!isTopFeed) {
        setFollowingFeedNovels([]);
        setFollowingFeedLoading(false);
        setFollowingFeedError("");
        return;
      }

      try {
        setFollowingFeedLoading(true);
        setFollowingFeedError("");
        const feedParams = new URLSearchParams();
        feedParams.set("limit", "8");
        if (["en", "zh-cn", "zh-tw", "ko"].includes(lang)) feedParams.set("lang", lang);
        const res = await fetch(`${API_BASE}/api/feed/following?${feedParams.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        });
        if (res.status === 401) {
          setFollowingFeedNovels([]);
          setFollowingFeedLoading(false);
          return;
        }
        if (!res.ok) {
          throw new Error(
            t({ ja: "フォロー中フィードの取得に失敗しました", en: "Failed to load following feed." })
          );
        }
        const data = await res.json().catch(() => []);
        setFollowingFeedNovels(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error(err);
        setFollowingFeedError(
          getErrorMessage(err, t({ ja: "フォロー中フィードの取得に失敗しました", en: "Failed to load following feed." }))
        );
      } finally {
        setFollowingFeedLoading(false);
      }
    };

    fetchFollowingFeed();
  }, [location.search, query, excludeQuery, tag, sort, ageLimit, creativeType, t, lang]);

  useEffect(() => {
    const fetchFollowingTagsFeed = async () => {
      const token =
        localStorage.getItem("token") || localStorage.getItem("access_token");
      if (!token) {
        setFollowingTagsFeedNovels([]);
        setFollowingTagsFeedLoading(false);
        setFollowingTagsFeedError("");
        return;
      }

      const params = new URLSearchParams(location.search);
      const urlQuery = (params.get("q") ?? "").trim();
      const urlExclude = (params.get("exclude") ?? "").trim();
      const urlTag = (params.get("tag") ?? "").trim();
      const urlSort = (params.get("sort") ?? "").trim();
      const urlAgeLimit = (params.get("age_limit") ?? "").trim();
      const urlCreativeType = (params.get("creative_type") ?? "").trim();
      const effectiveTag = urlTag || (tag ?? "").trim();
      const effectiveQuery = urlQuery || (query ?? "").trim();
      const effectiveExclude = urlExclude || (excludeQuery ?? "").trim();
      const effectiveSort = urlSort || (sort ?? "new").trim() || "new";
      const effectiveAgeLimit = urlAgeLimit || (ageLimit ?? "").trim();
      const effectiveCreativeType = urlCreativeType || (creativeType ?? "").trim();
      const isTopFeed =
        !effectiveTag &&
        !effectiveQuery &&
        !effectiveExclude &&
        !effectiveAgeLimit &&
        !effectiveCreativeType &&
        effectiveSort === "new";
      if (!isTopFeed) {
        setFollowingTagsFeedNovels([]);
        setFollowingTagsFeedLoading(false);
        setFollowingTagsFeedError("");
        return;
      }
      try {
        setFollowingTagsFeedLoading(true);
        setFollowingTagsFeedError("");
        const feedParams = new URLSearchParams();
        feedParams.set("limit", "8");
        if (["en", "zh-cn", "zh-tw", "ko"].includes(lang)) feedParams.set("lang", lang);
        const res = await fetch(`${API_BASE}/api/feed/following-tags?${feedParams.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        });
        if (res.status === 401) {
          setFollowingTagsFeedNovels([]);
          setFollowingTagsFeedLoading(false);
          return;
        }
        if (!res.ok) {
          throw new Error(
            t({ ja: "フォロー中タグフィードの取得に失敗しました", en: "Failed to load followed tags feed." })
          );
        }
        const data = await res.json().catch(() => []);
        setFollowingTagsFeedNovels(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error(err);
        setFollowingTagsFeedError(
          getErrorMessage(err, t({ ja: "フォロー中タグフィードの取得に失敗しました", en: "Failed to load followed tags feed." }))
        );
      } finally {
        setFollowingTagsFeedLoading(false);
      }
    };
    fetchFollowingTagsFeed();
  }, [location.search, query, excludeQuery, tag, sort, ageLimit, creativeType, t, lang]);

  useEffect(() => {
    const fetchNewAndTrendingFeed = async () => {
      const token =
        localStorage.getItem("token") || localStorage.getItem("access_token");
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;

      const params = new URLSearchParams(location.search);
      const urlQuery = (params.get("q") ?? "").trim();
      const urlExclude = (params.get("exclude") ?? "").trim();
      const urlTag = (params.get("tag") ?? "").trim();
      const urlSort = (params.get("sort") ?? "").trim();
      const urlAgeLimit = (params.get("age_limit") ?? "").trim();
      const urlCreativeType = (params.get("creative_type") ?? "").trim();
      const effectiveTag = urlTag || (tag ?? "").trim();
      const effectiveQuery = urlQuery || (query ?? "").trim();
      const effectiveExclude = urlExclude || (excludeQuery ?? "").trim();
      const effectiveSort = urlSort || (sort ?? "new").trim() || "new";
      const effectiveAgeLimit = urlAgeLimit || (ageLimit ?? "").trim();
      const effectiveCreativeType = urlCreativeType || (creativeType ?? "").trim();
      const isTopFeed =
        !effectiveTag &&
        !effectiveQuery &&
        !effectiveExclude &&
        !effectiveAgeLimit &&
        !effectiveCreativeType &&
        effectiveSort === "new";
      if (!isTopFeed) {
        setNewFeedNovels([]);
        setTrendingFeedNovels([]);
        setNewFeedLoading(false);
        setTrendingFeedLoading(false);
        setNewFeedError("");
        setTrendingFeedError("");
        return;
      }

      try {
        setNewFeedLoading(true);
        setTrendingFeedLoading(true);
        setNewFeedError("");
        setTrendingFeedError("");
        const feedParams = new URLSearchParams();
        feedParams.set("limit", "8");
        if (["en", "zh-cn", "zh-tw", "ko"].includes(lang)) feedParams.set("lang", lang);
        const [resNew, resTrending] = await Promise.all([
          fetch(`${API_BASE}/api/feed/new?${feedParams.toString()}`, {
            headers,
            cache: "no-store",
          }),
          fetch(`${API_BASE}/api/feed/trending?${feedParams.toString()}`, {
            headers,
            cache: "no-store",
          }),
        ]);
        if (resNew.ok) {
          const newData = await resNew.json().catch(() => []);
          setNewFeedNovels(Array.isArray(newData) ? newData : []);
          setNewFeedError("");
        } else {
          setNewFeedNovels([]);
          setNewFeedError(
            t({ ja: "新着フィードの取得に失敗しました", en: "Failed to load new feed." })
          );
        }
        if (resTrending.ok) {
          const trendingData = await resTrending.json().catch(() => []);
          setTrendingFeedNovels(Array.isArray(trendingData) ? trendingData : []);
          setTrendingFeedError("");
        } else {
          setTrendingFeedNovels([]);
          setTrendingFeedError(
            t({ ja: "急上昇フィードの取得に失敗しました", en: "Failed to load trending feed." })
          );
        }
      } catch (err) {
        console.error(err);
        setNewFeedError(t({ ja: "新着フィードの取得に失敗しました", en: "Failed to load new feed." }));
        setTrendingFeedError(t({ ja: "急上昇フィードの取得に失敗しました", en: "Failed to load trending feed." }));
      } finally {
        setNewFeedLoading(false);
        setTrendingFeedLoading(false);
      }
    };

    fetchNewAndTrendingFeed();
  }, [location.search, query, excludeQuery, tag, sort, ageLimit, creativeType, t, lang]);

  useEffect(() => {
    const fetchExtraFeeds = async () => {
      const token =
        localStorage.getItem("token") || localStorage.getItem("access_token");
      if (!token) {
        setHistoryFeedNovels([]);
        setPickupFeedNovels([]);
        setTrendingTags([]);
        setHistoryFeedLoading(false);
        setPickupFeedLoading(false);
        setTrendingTagsLoading(false);
        setHistoryFeedError("");
        setPickupFeedError("");
        setTrendingTagsError("");
        return;
      }
      const params = new URLSearchParams(location.search);
      const urlQuery = (params.get("q") ?? "").trim();
      const urlExclude = (params.get("exclude") ?? "").trim();
      const urlTag = (params.get("tag") ?? "").trim();
      const urlSort = (params.get("sort") ?? "").trim();
      const urlAgeLimit = (params.get("age_limit") ?? "").trim();
      const urlCreativeType = (params.get("creative_type") ?? "").trim();
      const effectiveTag = urlTag || (tag ?? "").trim();
      const effectiveQuery = urlQuery || (query ?? "").trim();
      const effectiveExclude = urlExclude || (excludeQuery ?? "").trim();
      const effectiveSort = urlSort || (sort ?? "new").trim() || "new";
      const effectiveAgeLimit = urlAgeLimit || (ageLimit ?? "").trim();
      const effectiveCreativeType = urlCreativeType || (creativeType ?? "").trim();
      const isTopFeed =
        !effectiveTag &&
        !effectiveQuery &&
        !effectiveExclude &&
        !effectiveAgeLimit &&
        !effectiveCreativeType &&
        effectiveSort === "new";
      if (!isTopFeed) {
        setHistoryFeedNovels([]);
        setPickupFeedNovels([]);
        setTrendingTags([]);
        setHistoryFeedLoading(false);
        setPickupFeedLoading(false);
        setTrendingTagsLoading(false);
        setHistoryFeedError("");
        setPickupFeedError("");
        setTrendingTagsError("");
        return;
      }
      try {
        setHistoryFeedLoading(true);
        setPickupFeedLoading(true);
        setTrendingTagsLoading(true);
        setHistoryFeedError("");
        setPickupFeedError("");
        setTrendingTagsError("");
        const feedParams = new URLSearchParams();
        feedParams.set("limit", "8");
        if (["en", "zh-cn", "zh-tw", "ko"].includes(lang)) feedParams.set("lang", lang);
        const [resHistory, resPickups, resTrendingTags] = await Promise.all([
          fetch(`${API_BASE}/api/feed/history?${feedParams.toString()}`, {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
          }),
          fetch(`${API_BASE}/api/feed/pickups?${feedParams.toString()}`, {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
          }),
          fetch(`${API_BASE}/api/trending-tags?days=7&limit=14`, { cache: "no-store" }),
        ]);
        if (resHistory.status === 401) {
          setHistoryFeedNovels([]);
          setHistoryFeedError("");
        } else if (resHistory.ok) {
          const historyData = await resHistory.json().catch(() => []);
          setHistoryFeedNovels(Array.isArray(historyData) ? historyData : []);
          setHistoryFeedError("");
        } else {
          setHistoryFeedNovels([]);
          setHistoryFeedError(
            t({ ja: "閲覧履歴の取得に失敗しました", en: "Failed to load view history." })
          );
        }

        if (resPickups.status === 401) {
          setPickupFeedNovels([]);
          setPickupFeedError("");
        } else if (resPickups.ok) {
          const pickupData = await resPickups.json().catch(() => []);
          setPickupFeedNovels(Array.isArray(pickupData) ? pickupData : []);
          setPickupFeedError("");
        } else {
          setPickupFeedNovels([]);
          setPickupFeedError(
            t({ ja: "ピックアップの取得に失敗しました", en: "Failed to load pickups." })
          );
        }

        if (resTrendingTags.ok) {
          const trendingTagData = await resTrendingTags.json().catch(() => []);
          setTrendingTags(Array.isArray(trendingTagData) ? trendingTagData : []);
          setTrendingTagsError("");
        } else {
          setTrendingTags([]);
          setTrendingTagsError(
            t({ ja: "トレンドタグの取得に失敗しました", en: "Failed to load trending tags." })
          );
        }
      } catch (err) {
        console.error(err);
        setHistoryFeedError(
          t({ ja: "閲覧履歴の取得に失敗しました", en: "Failed to load view history." })
        );
        setPickupFeedError(
          t({ ja: "ピックアップの取得に失敗しました", en: "Failed to load pickups." })
        );
        setTrendingTagsError(
          t({ ja: "トレンドタグの取得に失敗しました", en: "Failed to load trending tags." })
        );
      } finally {
        setHistoryFeedLoading(false);
        setPickupFeedLoading(false);
        setTrendingTagsLoading(false);
      }
    };
    fetchExtraFeeds();
  }, [location.search, query, excludeQuery, tag, sort, ageLimit, creativeType, t, lang]);

  useEffect(() => {
    const fetchRecommended = async () => {
      const token =
        localStorage.getItem("token") || localStorage.getItem("access_token");
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;

      const params = new URLSearchParams(location.search);
      const urlQuery = (params.get("q") ?? "").trim();
      const urlExclude = (params.get("exclude") ?? "").trim();
      const urlTag = (params.get("tag") ?? "").trim();
      const urlSort = (params.get("sort") ?? "").trim();
      const urlAgeLimit = (params.get("age_limit") ?? "").trim();
      const urlCreativeType = (params.get("creative_type") ?? "").trim();
      const effectiveTag = urlTag || (tag ?? "").trim();
      const effectiveQuery = urlQuery || (query ?? "").trim();
      const effectiveExclude = urlExclude || (excludeQuery ?? "").trim();
      const effectiveSort = urlSort || (sort ?? "new").trim() || "new";
      const effectiveAgeLimit = urlAgeLimit || (ageLimit ?? "").trim();
      const effectiveCreativeType = urlCreativeType || (creativeType ?? "").trim();
      const isTopFeed =
        !effectiveTag &&
        !effectiveQuery &&
        !effectiveExclude &&
        !effectiveAgeLimit &&
        !effectiveCreativeType &&
        effectiveSort === "new";
      if (!isTopFeed) {
        setRecommendedNovels([]);
        setRecommendedLoading(false);
        setRecommendedError("");
        return;
      }

      try {
        setRecommendedLoading(true);
        setRecommendedError("");
        const recParams = new URLSearchParams();
        recParams.set("limit", "8");
        if (["en", "zh-cn", "zh-tw", "ko"].includes(lang)) recParams.set("lang", lang);
        const res = await fetch(`${API_BASE}/api/feed/recommended?${recParams.toString()}`, {
          headers,
          cache: "no-store",
        });
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
          getErrorMessage(
            err,
            t({ ja: "おすすめの取得に失敗しました", en: "Failed to load recommendations." })
          )
        );
      } finally {
        setRecommendedLoading(false);
      }
    };

    fetchRecommended();
  }, [location.search, query, excludeQuery, tag, sort, ageLimit, creativeType, t, lang]);

  const shorten = (text: string | null | undefined, max = 120) => {
    if (!text) return "";
    if (text.length <= max) return text;
    return text.slice(0, max) + "…";
  };
  const creativeTypeLabel = (value: string | null | undefined) => {
    if (value === "fanfic") return "fanfic";
    return "original";
  };
  const renderNovelBadges = (novel: HomeNovel) => (
    <>
      {novel.age_limit === "r18" && <span className="age-chip age-chip-r18">R18</span>}
      {novel.age_limit === "r15" && <span className="age-chip">R15</span>}
      {hasRecentEpisodeActivity(novel, 7) && <span className="age-chip novel-fresh-chip">{t({ ja: "新着", en: "New" })}</span>}
      <span
        className="age-chip"
        style={{
          borderColor: "var(--accent)",
          color: "var(--accent)",
          background: "var(--accent-soft)",
        }}
      >
        {creativeTypeLabel(novel.creative_type)}
      </span>
    </>
  );
  const renderNovelAuthorMeta = (novel: HomeNovel) => (
    <div style={{ fontSize: 12, color: "var(--novel-card-meta)", marginBottom: 8 }}>
      <span>
        {t({ ja: "作者", en: "Author" })}:{" "}
        {novel.author_username ? (
          <Link className="user-link" to={`/users/${encodeURIComponent(novel.author_username)}`}>
            @{novel.author_username}
          </Link>
        ) : (
          t({ ja: "不明", en: "Unknown" })
        )}
      </span>
      <span style={{ marginLeft: 8 }}>{renderNovelBadges(novel)}</span>
    </div>
  );
  const renderNovelStats = (novel: HomeNovel, { withChars = true }: { withChars?: boolean } = {}) => (
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
      {typeof novel.comment_count === "number" ? (
        <span>{t({ ja: "コメント", en: "Comments" })}: {novel.comment_count ?? 0}</span>
      ) : null}
      {withChars ? (
        <span>
          {t({ ja: "文字数", en: "Chars" })}: {novel.total_char_count ?? 0}
        </span>
      ) : null}
    </div>
  );
  const formatRecommendationReasonLabel = (key: string) => {
    if (key === "tag_overlap") return t({ ja: "タグ一致", en: "Tag overlap" });
    if (key === "recent_interest_overlap") return t({ ja: "最近の閲覧傾向", en: "Recent interest" });
    if (key === "recency_boost") return t({ ja: "新着補正", en: "Recency boost" });
    if (key === "followed_author_boost") return t({ ja: "フォロー作者補正", en: "Followed author boost" });
    if (key === "creative_boost") return t({ ja: "創作区分補正", en: "Type preference" });
    return key;
  };

  const currentParams = new URLSearchParams(location.search);
  const currentUrlQuery = (currentParams.get("q") ?? "").trim();
  const currentUrlExclude = (currentParams.get("exclude") ?? "").trim();
  const currentUrlTag = (currentParams.get("tag") ?? "").trim();
  const currentUrlSort = (currentParams.get("sort") ?? "").trim();
  const currentUrlAgeLimit = (currentParams.get("age_limit") ?? "").trim();
  const currentUrlCreativeType = (currentParams.get("creative_type") ?? "").trim();
  const currentEffectiveTag = currentUrlTag || (tag ?? "").trim();
  const currentEffectiveQuery = currentUrlQuery || (query ?? "").trim();
  const currentEffectiveExclude = currentUrlExclude || (excludeQuery ?? "").trim();
  const currentEffectiveSort = currentUrlSort || (sort ?? "new").trim() || "new";
  const currentEffectiveAgeLimit = currentUrlAgeLimit || (ageLimit ?? "").trim();
  const currentEffectiveCreativeType = currentUrlCreativeType || (creativeType ?? "").trim();
  const hasAuthToken = !!(
    localStorage.getItem("token") || localStorage.getItem("access_token")
  );
  const showFeedHubSection =
    !rankingOnly &&
    !currentEffectiveTag &&
    !currentEffectiveQuery &&
    !currentEffectiveExclude &&
    !currentEffectiveAgeLimit &&
    !currentEffectiveCreativeType &&
    currentEffectiveSort === "new";
  const showPersonalizedFeedSections = showFeedHubSection && hasAuthToken;
  const novelsVisible = filterR18Novels(novels, showR18);
  const rankingVisible = filterR18Novels(ranking, showR18);
  const recommendedNovelsVisible = filterR18Novels(recommendedNovels, showR18);
  const followingFeedNovelsVisible = filterR18Novels(followingFeedNovels, showR18);
  const followingTagsFeedNovelsVisible = filterR18Novels(followingTagsFeedNovels, showR18);
  const newFeedNovelsVisible = filterR18Novels(newFeedNovels, showR18);
  const trendingFeedNovelsVisible = filterR18Novels(trendingFeedNovels, showR18);
  const historyFeedNovelsVisible = filterR18Novels(historyFeedNovels, showR18);
  const pickupFeedNovelsVisible = filterR18Novels(pickupFeedNovels, showR18);
  const renderSectionHeader = (title: string, moreTo?: string) => (
    <div className="section-heading-row">
      <h3 className="section-heading-title">{title}</h3>
      {moreTo ? (
        <Link to={moreTo} className="section-heading-more">
          {t({ ja: "もっと見る", en: "See more" })}
        </Link>
      ) : null}
    </div>
  );
  const sortLabelMap = {
    new: t({ ja: "新着順", en: "Newest" }),
    popular: t({ ja: "人気順", en: "Popular" }),
    likes: t({ ja: "いいね順", en: "Likes" }),
    comments: t({ ja: "コメント順", en: "Comments" }),
  };
  const activeFilterChips: Array<{ key: string; text: string }> = [];
  if (currentEffectiveQuery) {
    activeFilterChips.push({
      key: "q",
      text: t({ ja: "検索: {{value}}", en: "Query: {{value}}" }, { value: shorten(currentEffectiveQuery, 24) }),
    });
  }
  if (currentEffectiveExclude) {
    activeFilterChips.push({
      key: "exclude",
      text: t({ ja: "除外: {{value}}", en: "Exclude: {{value}}" }, { value: shorten(currentEffectiveExclude, 24) }),
    });
  }
  if (currentEffectiveTag) {
    activeFilterChips.push({
      key: "tag",
      text: t({ ja: "タグ: {{value}}", en: "Tag: {{value}}" }, { value: currentEffectiveTag }),
    });
  }
  if (currentEffectiveAgeLimit) {
    activeFilterChips.push({
      key: "age",
      text: t({ ja: "年齢: {{value}}", en: "Age: {{value}}" }, { value: currentEffectiveAgeLimit }),
    });
  }
  if (currentEffectiveCreativeType) {
    activeFilterChips.push({
      key: "creative",
      text: t(
        { ja: "区分: {{value}}", en: "Type: {{value}}" },
        { value: currentEffectiveCreativeType }
      ),
    });
  }
  if (currentEffectiveSort !== "new") {
    activeFilterChips.push({
      key: "sort",
      text: t(
        { ja: "並び: {{value}}", en: "Sort: {{value}}" },
        {
          value:
            sortLabelMap[currentEffectiveSort as keyof typeof sortLabelMap] || currentEffectiveSort,
        }
      ),
    });
  }

  const applyNovelUpdate = (novelId: number | string, updater: (item: HomeNovel) => HomeNovel) => {
    setNovels((prev) =>
      prev.map((item) => (item.id === novelId ? updater(item) : item))
    );
    setRanking((prev) =>
      prev.map((item) => (item.id === novelId ? updater(item) : item))
    );
    setRecommendedNovels((prev) =>
      prev.map((item) => (item.id === novelId ? updater(item) : item))
    );
    setFollowingFeedNovels((prev) =>
      prev.map((item) => (item.id === novelId ? updater(item) : item))
    );
    setFollowingTagsFeedNovels((prev) =>
      prev.map((item) => (item.id === novelId ? updater(item) : item))
    );
    setNewFeedNovels((prev) =>
      prev.map((item) => (item.id === novelId ? updater(item) : item))
    );
    setTrendingFeedNovels((prev) =>
      prev.map((item) => (item.id === novelId ? updater(item) : item))
    );
    setHistoryFeedNovels((prev) =>
      prev.map((item) => (item.id === novelId ? updater(item) : item))
    );
    setPickupFeedNovels((prev) =>
      prev.map((item) => (item.id === novelId ? updater(item) : item))
    );
  };

  const applyRankingTagFilter = (tagName: string) => {
    const normalized = String(tagName || "").trim();
    const nextParams = new URLSearchParams(location.search);
    if (normalized) nextParams.set("tag", normalized);
    else nextParams.delete("tag");
    const nextSearch = nextParams.toString();
    navigate({
      pathname: location.pathname,
      search: nextSearch ? `?${nextSearch}` : "",
    });
    setRankingEnabled(true);
  };

  const applyRankingPreset = ({
    sort: nextSort,
    period: nextPeriod,
    creativeType: nextCreativeType,
  }: {
    sort: string;
    period: string;
    creativeType: string;
  }) => {
    setRankingSort(nextSort);
    setRankingPeriod(nextPeriod);
    setRankingCreativeType(nextCreativeType);
    applyRankingStateToUrl({
      sort: nextSort,
      period: nextPeriod,
      creativeType: nextCreativeType,
    });
    setRankingEnabled(true);
  };

  const copyCurrentRankingUrl = async () => {
    const shareUrl = `${window.location.origin}${location.pathname}${location.search}`;
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(shareUrl);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = shareUrl;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setRankingShareMessage(t({ ja: "URLをコピーしました", en: "Copied URL" }));
    } catch (e) {
      console.error(e);
      setRankingShareMessage(t({ ja: "コピーに失敗しました", en: "Failed to copy URL" }));
    }
    window.setTimeout(() => setRankingShareMessage(""), 1500);
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

  const toggleLike = async (novel: HomeNovel) => {
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
        getErrorMessage(err, t({ ja: "いいね操作中にエラーが発生しました", en: "An error occurred while liking." }))
      );
    }
  };

  const toggleFavorite = async (novel: HomeNovel) => {
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
        getErrorMessage(err, t({ ja: "ブックマーク操作中にエラーが発生しました", en: "An error occurred while bookmarking." }))
      );
    }
  };

  const handleQuickEpisodePost = async () => {
    const token = requireToken();
    if (!token || quickEpisodeCreating) return;

    try {
      setQuickEpisodeCreating(true);
      const stamp = new Date().toLocaleString("ja-JP", {
        timeZone: "Asia/Tokyo",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
      const payload = {
        title: t({ ja: `新規エピソード用 ${stamp}`, en: `Novel for New Episode ${stamp}` }),
        description: t({ ja: "トップページのエピソード投稿ボタンから自動作成", en: "Auto-created from top episode post button" }),
        is_public: false,
      };
      const res = await fetch(`${API_BASE}/api/novels`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.id) {
        throw new Error(
          data.detail ||
            t({ ja: "小説の自動作成に失敗しました。", en: "Failed to auto-create a novel." })
        );
      }
      navigate(`/novels/${data.id}/episodes/new`);
    } catch (err) {
      console.error(err);
      alert(
        getErrorMessage(err, t({ ja: "エピソード投稿の準備に失敗しました。", en: "Failed to prepare episode posting." }))
      );
    } finally {
      setQuickEpisodeCreating(false);
    }
  };

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  return (
    <div>
      {error && (
        <p style={{ color: "red", marginTop: 8, marginBottom: 8 }}>{error}</p>
      )}
      {activeFilterChips.length > 0 && (
        <section
          style={{
            marginBottom: 12,
            border: "1px solid var(--border)",
            borderRadius: 10,
            padding: 10,
            background: "var(--surface)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <strong style={{ fontSize: 13 }}>
              {t({ ja: "現在の検索条件", en: "Active filters" })}
            </strong>
            <button
              type="button"
              className="btn btn-border"
              style={{ marginLeft: "auto" }}
              onClick={() => navigate(rankingOnly ? "/ranking" : "/")}
            >
              {t({ ja: "条件をクリア", en: "Clear filters" })}
            </button>
          </div>
          <div className="tag-chip-row" style={{ marginTop: 8 }}>
            {activeFilterChips.map((chip) => (
              <span key={`active-filter-${chip.key}`} className="tag-chip">
                {chip.text}
              </span>
            ))}
          </div>
        </section>
      )}

      {!rankingOnly && (
      <section className="home-post-cta">
        <Link className="home-post-cta-btn home-post-cta-primary" to="/novels/new">
          <span className="home-post-cta-title">
            {t({ ja: "新規小説を作成", en: "Create New Novel" })}
          </span>
          <span className="home-post-cta-sub">
            {t({ ja: "0から新しい作品を書く", en: "Start a brand-new story" })}
          </span>
        </Link>
        <button
          type="button"
          className="home-post-cta-btn home-post-cta-secondary"
          onClick={handleQuickEpisodePost}
          disabled={quickEpisodeCreating}
        >
          <span className="home-post-cta-title">
            {quickEpisodeCreating
              ? t({ ja: "小説を作成中...", en: "Creating novel..." })
              : t({ ja: "エピソードを投稿", en: "Post Episode" })}
          </span>
          <span className="home-post-cta-sub">
            {t({ ja: "小説を自動作成して投稿画面へ進む", en: "Auto-create a novel and open episode editor" })}
          </span>
        </button>
      </section>
      )}

      {showRanking && (
        <section style={{ marginBottom: 24 }}>
          {rankingOnly && (
            <p style={{ margin: "0 0 8px 0", color: "var(--muted-text)", fontSize: 14 }}>
              {t({
                ja: "ランキング専用ページです。条件付きURLを共有して同じ結果を再現できます。",
                en: "This is a ranking-only page. Share the URL to reproduce the same filters.",
              })}
            </p>
          )}
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
          <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn btn-border"
              onClick={copyCurrentRankingUrl}
            >
              {t({ ja: "共有URLをコピー", en: "Copy share URL" })}
            </button>
            {rankingShareMessage ? (
              <span style={{ fontSize: 12, color: "var(--muted-text)" }}>{rankingShareMessage}</span>
            ) : null}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
            {[
              {
                key: "preset-daily-rising-all",
                label: t({ ja: "日間急上昇", en: "Daily rising" }),
                sort: "rising",
                period: "daily",
                creativeType: "",
              },
              {
                key: "preset-daily-rising-fanfic",
                label: t({ ja: "fanfic日間急上昇", en: "Fanfic daily rising" }),
                sort: "rising",
                period: "daily",
                creativeType: "fanfic",
              },
              {
                key: "preset-weekly-score-original",
                label: t({ ja: "original週間総合", en: "Original weekly score" }),
                sort: "score",
                period: "weekly",
                creativeType: "original",
              },
            ].map((preset) => (
              <button
                key={preset.key}
                type="button"
                className="btn btn-border"
                onClick={() => applyRankingPreset(preset)}
              >
                {preset.label}
              </button>
            ))}
          </div>
          {rankingOnly && (
            <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
              {[
                {
                  key: "preset-link-daily-rising-all",
                  label: t({ ja: "URL: 日間急上昇", en: "URL: Daily rising" }),
                  sort: "rising",
                  period: "daily",
                  creativeType: "",
                },
                {
                  key: "preset-link-daily-rising-fanfic",
                  label: t({ ja: "URL: fanfic日間急上昇", en: "URL: Fanfic daily rising" }),
                  sort: "rising",
                  period: "daily",
                  creativeType: "fanfic",
                },
                {
                  key: "preset-link-weekly-score-original",
                  label: t({ ja: "URL: original週間総合", en: "URL: Original weekly score" }),
                  sort: "score",
                  period: "weekly",
                  creativeType: "original",
                },
              ].map((preset) => (
                <Link
                  key={preset.key}
                  className="btn btn-border"
                  to={`/ranking${buildRankingPresetSearch(preset)}`}
                >
                  {preset.label}
                </Link>
              ))}
            </div>
          )}
          <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
            {[
              { key: "score", label: t({ ja: "総合", en: "Score" }) },
              { key: "rising", label: t({ ja: "急上昇", en: "Rising" }) },
              { key: "likes", label: t({ ja: "いいね", en: "Likes" }) },
              { key: "favorites", label: t({ ja: "ブックマーク", en: "Bookmarks" }) },
              { key: "views", label: t({ ja: "閲覧", en: "Views" }) },
              { key: "comments", label: t({ ja: "コメント", en: "Comments" }) },
            ].map((option) => (
              <button
                key={option.key}
                type="button"
                className="btn btn-border"
                onClick={() => {
                  setRankingSort(option.key);
                  applyRankingStateToUrl({ sort: option.key });
                }}
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
          <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
            {[
              { key: "daily", label: t({ ja: "日間", en: "Daily" }) },
              { key: "weekly", label: t({ ja: "週間", en: "Weekly" }) },
              { key: "monthly", label: t({ ja: "月間", en: "Monthly" }) },
            ].map((option) => (
              <button
                key={option.key}
                type="button"
                className="btn btn-border"
                onClick={() => {
                  setRankingPeriod(option.key);
                  applyRankingStateToUrl({ period: option.key });
                }}
                disabled={!rankingEnabled}
                style={
                  rankingPeriod === option.key
                    ? { borderColor: "var(--cta)", color: "var(--cta)" }
                    : undefined
                }
              >
                {option.label}
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
            {[
              { key: "", label: t({ ja: "全カテゴリ", en: "All types" }) },
              { key: "original", label: "original" },
              { key: "fanfic", label: "fanfic" },
            ].map((option) => (
              <button
                key={`ranking-ct-${option.key || "all"}`}
                type="button"
                className="btn btn-border"
                onClick={() => {
                  setRankingCreativeType(option.key);
                  applyRankingStateToUrl({ creativeType: option.key });
                }}
                disabled={!rankingEnabled}
                style={
                  rankingCreativeType === option.key
                    ? { borderColor: "var(--cta)", color: "var(--cta)" }
                    : undefined
                }
              >
                {option.label}
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontSize: 12, color: "var(--muted-text)" }}>
              {t({ ja: "タグ別", en: "By tag" })}
            </span>
            {currentEffectiveTag ? (
              <>
                <span className="tag-chip">#{currentEffectiveTag}</span>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => applyRankingTagFilter("")}
                  disabled={!rankingEnabled}
                >
                  {t({ ja: "タグ解除", en: "Clear tag" })}
                </button>
              </>
            ) : (
              <span style={{ fontSize: 12, color: "var(--muted-text)" }}>
                {t({ ja: "作品タグをクリックすると絞り込みます", en: "Click tags in cards to filter" })}
              </span>
            )}
          </div>

          {!premiumChecked ? (
            <p style={{ marginTop: 10 }}>
              {t({ ja: "プレミアム状態を確認中...", en: "Checking premium status..." })}
            </p>
          ) : rankingAccessDenied ? (
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
              ) : rankingVisible.length === 0 ? (
                <p style={{ marginTop: 10 }}>
                  {t({ ja: "ランキングデータがありません。", en: "No ranking data available." })}
                </p>
              ) : (
                <ol style={{ listStyle: "none", padding: 0, marginTop: 12 }}>
                  {rankingVisible.map((novel) => (
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
                        <span>{t({ ja: "期間LIKE", en: "Period likes" })}: {novel.period_likes ?? 0}</span>
                        <span>{t({ ja: "期間ブクマ", en: "Period bookmarks" })}: {novel.period_favorites ?? 0}</span>
                        <span>{t({ ja: "期間コメント", en: "Period comments" })}: {novel.period_comments ?? 0}</span>
                        <span>{t({ ja: "文字数", en: "Chars" })}: {novel.total_char_count ?? 0}</span>
                        {(rankingSort === "score" || rankingSort === "rising") && (
                          <span>
                            {t({ ja: "ランキング値", en: "Ranking score" })}: {Number(novel.ranking_score || 0).toFixed(1)}
                          </span>
                        )}
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
                      {Array.isArray(novel.tags) && novel.tags.length > 0 && (
                        <div className="tag-chip-row">
                          {novel.tags.slice(0, 4).map((tagItem: HomeNovelTag) => {
                            const tagName =
                              typeof tagItem === "string"
                                ? tagItem.trim()
                                : String(tagItem?.name || "").trim();
                            if (!tagName) return null;
                            return (
                              <button
                                key={`ranking-tag-${novel.id}-${tagName}`}
                                type="button"
                                className="btn btn-border"
                                onClick={() => applyRankingTagFilter(tagName)}
                                style={{
                                  padding: "2px 10px",
                                  borderRadius: 999,
                                  fontSize: 12,
                                  lineHeight: 1.4,
                                }}
                              >
                                #{tagName}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </li>
                  ))}
              </ol>
            )}
          </>
        )}
        </section>
      )}

      {showFeedHubSection && (
      <section style={{ marginBottom: 24 }}>
        {renderSectionHeader(
          t({ ja: "あなたへのおすすめ", en: "Recommended for You" }),
          "/discover?mode=recommended"
        )}
        {recommendedError && (
          <p style={{ color: "red", marginTop: 8 }}>{recommendedError}</p>
        )}
        {recommendedLoading ? (
          <p style={{ marginTop: 10 }}>
            {t({ ja: "おすすめを読み込み中...", en: "Loading recommendations..." })}
          </p>
        ) : recommendedNovelsVisible.length === 0 ? (
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
            {recommendedNovelsVisible.map((novel) => (
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
                {renderNovelAuthorMeta(novel)}
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
                {renderNovelStats(novel)}
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

      {showFeedHubSection && (
      <section style={{ marginBottom: 24 }}>
        {renderSectionHeader(
          t({ ja: "急上昇作品", en: "Trending Works" }),
          "/ranking?ranking_sort=rising&ranking_period=daily"
        )}
        {trendingFeedError && (
          <p style={{ color: "red", marginTop: 8 }}>{trendingFeedError}</p>
        )}
        {trendingFeedLoading ? (
          <p style={{ marginTop: 10 }}>
            {t({ ja: "急上昇を読み込み中...", en: "Loading trending works..." })}
          </p>
        ) : trendingFeedNovelsVisible.length === 0 ? (
          <p style={{ marginTop: 10, color: "var(--muted-text)" }}>
            {t({ ja: "急上昇作品はまだありません。", en: "No trending works yet." })}
          </p>
        ) : (
          <div className="novel-grid" style={{ marginTop: 12 }}>
            {trendingFeedNovelsVisible.map((novel) => (
              <NovelCard
                key={`feed-trending-${novel.id}`}
                novel={novel}
                t={t}
                apiBase={API_BASE}
                descriptionMax={90}
                onLike={(novel) => {
                  void toggleLike(novel as HomeNovel);
                }}
                onFavorite={(novel) => {
                  void toggleFavorite(novel as HomeNovel);
                }}
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
      )}

      {showFeedHubSection && (
      <section style={{ marginBottom: 24 }}>
        {renderSectionHeader(t({ ja: "フォロー中タグの新着", en: "New from Followed Tags" }), "/tags")}
        {followingTagsFeedError && (
          <p style={{ color: "red", marginTop: 8 }}>{followingTagsFeedError}</p>
        )}
        {followingTagsFeedLoading ? (
          <p style={{ marginTop: 10 }}>
            {t({ ja: "タグフィードを読み込み中...", en: "Loading followed tags feed..." })}
          </p>
        ) : followingTagsFeedNovelsVisible.length === 0 ? (
          <p style={{ marginTop: 10, color: "var(--muted-text)" }}>
            {hasAuthToken
              ? t({
                  ja: "フォロー中タグの新着作品はまだありません。",
                  en: "No new works from followed tags yet.",
                })
              : t({
                  ja: "ログインするとフォロー中タグの新着が表示されます。",
                  en: "Log in to see new works from followed tags.",
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
            {followingTagsFeedNovelsVisible.map((novel) => (
              <div
                key={`following-tags-${novel.id}`}
                style={{
                  border: "1px solid var(--novel-card-border)",
                  borderRadius: 8,
                  padding: 12,
                  boxShadow: "0 2px 4px var(--shadow)",
                  backgroundColor: "var(--novel-card-bg)",
                  color: "var(--text)",
                }}
              >
                <h3 style={{ margin: "0 0 8px 0", fontSize: 18 }}>
                  <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
                </h3>
                {renderNovelAuthorMeta(novel)}
                <p style={{ whiteSpace: "pre-wrap", fontSize: 14, marginBottom: 8 }}>
                  {shorten(novel.description, 90)}
                </p>
                {renderNovelStats(novel)}
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
                  <button type="button" className="btn btn-border" onClick={() => toggleLike(novel)}>
                    {novel.is_liked ? t({ ja: "♥ いいね済み", en: "♥ Liked" }) : t({ ja: "♡ いいね", en: "♡ Like" })}
                  </button>
                  <button type="button" className="btn btn-border" onClick={() => toggleFavorite(novel)}>
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


      {showFeedHubSection && (
      <section style={{ marginBottom: 24 }}>
        {renderSectionHeader(t({ ja: "トレンドタグ", en: "Trending Tags" }), "/tags")}
        {trendingTagsError && <p style={{ color: "red", marginTop: 8 }}>{trendingTagsError}</p>}
        {trendingTagsLoading ? (
          <p style={{ marginTop: 10 }}>{t({ ja: "タグを読み込み中...", en: "Loading tags..." })}</p>
        ) : trendingTags.length === 0 ? (
          <p style={{ marginTop: 10, color: "var(--muted-text)" }}>
            {t({ ja: "トレンドタグはまだありません。", en: "No trending tags yet." })}
          </p>
        ) : (
          <div className="tag-chip-row" style={{ marginTop: 10 }}>
            {trendingTags.map((tagItem) => (
              <Link key={`trend-tag-${tagItem.id ?? tagItem.name}`} to={`/tags/${encodeURIComponent(tagItem.name || "")}`}>
                #{tagItem.name} ({tagItem.novel_count ?? 0})
              </Link>
            ))}
          </div>
        )}
      </section>
      )}

      {showPersonalizedFeedSections && (
      <section style={{ marginBottom: 24 }}>
        {renderSectionHeader(t({ ja: "フォロー中の新着", en: "New from Following" }), "/mypage")}
        {followingFeedError && (
          <p style={{ color: "red", marginTop: 8 }}>{followingFeedError}</p>
        )}
        {followingFeedLoading ? (
          <p style={{ marginTop: 10 }}>
            {t({ ja: "フォロー中フィードを読み込み中...", en: "Loading following feed..." })}
          </p>
        ) : followingFeedNovelsVisible.length === 0 ? (
          <p style={{ marginTop: 10, color: "var(--muted-text)" }}>
            {hasAuthToken
              ? t({
                  ja: "フォロー中の作者の公開作品はまだありません。",
                  en: "No new public works from followed authors yet.",
                })
              : t({
                  ja: "ログインするとフォロー中の新着が表示されます。",
                  en: "Log in to see new works from followed authors.",
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
            {followingFeedNovelsVisible.map((novel) => (
              <div
                key={`following-${novel.id}`}
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
                {renderNovelAuthorMeta(novel)}
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
                {renderNovelStats(novel)}
                {Array.isArray(novel.recommendation_reasons) && novel.recommendation_reasons.length > 0 ? (
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
                    {novel.recommendation_reasons
                      .filter((r: RecommendationReason) => Number(r?.value || 0) > 0)
                      .slice(0, 3)
                      .map((reason: RecommendationReason) => (
                        <span key={`rec-reason-${novel.id}-${reason.key}`} className="tag-chip">
                          {formatRecommendationReasonLabel(String(reason.key || ""))}: {Number(reason.value || 0).toFixed(1)}
                        </span>
                      ))}
                    {typeof novel.recommendation_score === "number" ? (
                      <span className="tag-chip">
                        {t({ ja: "総合", en: "Score" })}: {Number(novel.recommendation_score || 0).toFixed(1)}
                      </span>
                    ) : null}
                  </div>
                ) : null}
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

      {showPersonalizedFeedSections && (
      <section style={{ marginBottom: 24 }}>
        {renderSectionHeader(t({ ja: "あなたの閲覧履歴", en: "Your View History" }), "/mypage")}
        {historyFeedError && <p style={{ color: "red", marginTop: 8 }}>{historyFeedError}</p>}
        {historyFeedLoading ? (
          <p style={{ marginTop: 10 }}>{t({ ja: "履歴を読み込み中...", en: "Loading history..." })}</p>
        ) : historyFeedNovelsVisible.length === 0 ? (
          <p style={{ marginTop: 10, color: "var(--muted-text)" }}>
            {t({ ja: "閲覧履歴はまだありません。", en: "No view history yet." })}
          </p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12, marginTop: 12 }}>
            {historyFeedNovelsVisible.map((novel) => (
              <article key={`history-${novel.id}`} className="novel-card" style={{ padding: 10 }}>
                <h4 style={{ margin: "0 0 6px" }}>
                  <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
                </h4>
                <div style={{ fontSize: 12, color: "var(--muted-text)", marginBottom: 8 }}>
                  @{novel.author_username || "unknown"}
                </div>
                <button type="button" className="btn btn-border" onClick={() => navigate(`/novels/${novel.id}`)}>
                  {t({ ja: "続きから読む", en: "Continue reading" })}
                </button>
              </article>
            ))}
          </div>
        )}
      </section>
      )}

      {showPersonalizedFeedSections && (
      <section style={{ marginBottom: 24 }}>
        {renderSectionHeader(t({ ja: "ピックアップ特集", en: "Pickups" }), "/discover?mode=pickups")}
        {pickupFeedError && <p style={{ color: "red", marginTop: 8 }}>{pickupFeedError}</p>}
        {pickupFeedLoading ? (
          <p style={{ marginTop: 10 }}>{t({ ja: "ピックアップを読み込み中...", en: "Loading pickups..." })}</p>
        ) : pickupFeedNovelsVisible.length === 0 ? (
          <p style={{ marginTop: 10, color: "var(--muted-text)" }}>
            {t({ ja: "ピックアップはまだありません。", en: "No pickups yet." })}
          </p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16, marginTop: 12 }}>
            {pickupFeedNovelsVisible.map((novel) => (
              <div key={`pickup-${novel.id}`} className="novel-card" style={{ padding: 12 }}>
                <h4 style={{ margin: "0 0 6px" }}>
                  <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
                </h4>
                <p style={{ fontSize: 13, margin: "0 0 8px" }}>{shorten(novel.description, 80)}</p>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <button type="button" className="btn btn-border" onClick={() => toggleLike(novel)}>
                    {novel.is_liked ? t({ ja: "♥ いいね済み", en: "♥ Liked" }) : t({ ja: "♡ いいね", en: "♡ Like" })}
                  </button>
                  <button type="button" className="btn btn-border" onClick={() => toggleFavorite(novel)}>
                    {novel.is_favorited ? t({ ja: "★ ブックマーク済み", en: "★ Bookmarked" }) : t({ ja: "☆ ブックマーク", en: "☆ Bookmark" })}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
      )}

      {!rankingOnly && novelsVisible.length === 0 && (
        <p>{t({ ja: "小説が見つかりません。", en: "No novels found." })}</p>
      )}

      {!rankingOnly && (
        <section style={{ marginBottom: 24 }}>
          <h3 className="section-heading-title">{t({ ja: "新着作品", en: "New Works" })}</h3>
          <div className="novel-grid">
            {novelsVisible.map((novel) => (
              <NovelCard
                key={novel.id}
                novel={novel}
                t={t}
                apiBase={API_BASE}
                showCreatedAt
                onLike={toggleLike}
                onFavorite={toggleFavorite}
                footer={
                  <Link to={`/novels/${novel.id}`} className="btn btn-border">
                    {t({ ja: "続きを読む", en: "Read more" })}
                  </Link>
                }
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
