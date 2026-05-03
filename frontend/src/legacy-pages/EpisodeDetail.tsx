import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import TagChipLink from "../components/TagChipLink";
import SupportPanel from "../components/SupportPanel";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { isGoogleCrawler } from "../lib/seo";
import { getApiBase } from "../lib/apiBase";
import { applySeoMeta, buildSeoDescription } from "../lib/seoMeta";

const API_BASE = getApiBase();
const FREE_READING_SCHEDULE = {
  ja: "無料開放時間: 平日17:00-19:00 / 土日祝14:00-19:00（JST）",
  en: "Free reading hours: Weekdays 17:00-19:00 / Weekends & holidays 14:00-19:00 (JST)",
};
const TRANSLATABLE_LANGS = new Set(["en", "zh-cn", "zh-tw", "ko"]);

type TagItem = {
  id?: number | string | null;
  name?: string | null;
};

type IllustItem = {
  id?: number | string | null;
  illust_tag?: string | null;
  image_url?: string | null;
  caption?: string | null;
};

type EpisodeNav = {
  id?: number | string | null;
  episode_number?: number | null;
  number?: number | null;
  title?: string | null;
};

type EpisodeComment = {
  id: number | string;
  user_id?: number | string | null;
  body?: string | null;
  created_at?: string | null;
  username?: string | null;
};

type EpisodeData = {
  id?: number | string | null;
  title?: string | null;
  body?: string | null;
  novel_id?: number | string | null;
  novel_title?: string | null;
  novel_description?: string | null;
  novel_tags?: TagItem[] | null;
  tags?: TagItem[] | null;
  author_username?: string | null;
  author_id?: number | string | null;
  created_at?: string | null;
  view_count?: number | null;
  like_count?: number | null;
  is_liked?: boolean | null;
  is_public?: boolean | null;
  status?: string | null;
  novel_age_limit?: string | null;
  age_confirmation_required?: boolean | null;
  is_premium_user?: boolean | null;
  is_free_reading_time?: boolean | null;
  is_free_public?: boolean | null;
  cover_image_url?: string | null;
  illusts?: IllustItem[] | null;
  prev_episode?: EpisodeNav | null;
  next_episode?: EpisodeNav | null;
  episode_number?: number | null;
  number?: number | null;
};

export default function EpisodeDetail() {
  const { id } = useParams(); // episode_id
  const navigate = useNavigate();
  const { t, lang } = useI18n();

  const isXInAppBrowser =
    typeof navigator !== "undefined" && /Twitter/i.test(navigator.userAgent);

  const [episode, setEpisode] = useState<EpisodeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [comments, setComments] = useState<EpisodeComment[]>([]);
  const [commentBody, setCommentBody] = useState("");
  const [myUserId, setMyUserId] = useState<number | string | null>(null);
  const [ageConfirmRequired, setAgeConfirmRequired] = useState(false);
  const [ageConfirmed, setAgeConfirmed] = useState(false);

  // ★ いいね / 閲覧数
  const [likeCount, setLikeCount] = useState(0);
  const [isLiked, setIsLiked] = useState(false);

  const countChars = (value: string | null | undefined) => (value || "").length;
  const summarizeText = (text: string | null | undefined, limit = 200) => {
    const clean = (text || "").trim();
    if (!clean) return "";
    if (clean.length <= limit) return clean;
    return `${clean.slice(0, limit)}...`;
  };

  useEffect(() => {
    if (typeof window === "undefined" || comments.length === 0) return;
    const match = String(window.location.hash || "").match(/^#comment-(\d+)$/);
    if (!match) return;
    const el = document.getElementById(`comment-${match[1]}`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [comments]);

  useEffect(() => {
    if (!episode) return undefined;
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const episodeNo = episode.episode_number ?? episode.number;
    const displayEpisodeTitle = formatEpisodeDisplayTitle(episodeNo, episode.title) || t({
      ja: "エピソード",
      en: "Episode",
    });
    const pageTitle = t({
      ja: `${episode.novel_title || "作品"}｜${displayEpisodeTitle}｜小説投稿サイトLexis`,
      en: `${episode.novel_title || "Novel"} | ${displayEpisodeTitle} | Lexis`,
    });
    const pageDescription = buildSeoDescription(
      summarizeText(episode.body, 140),
      episode.novel_description,
      t({ ja: "公開中のエピソードページです。", en: "Public episode page." })
    );
    const safeEpisodeId = encodeURIComponent(String(id || episode.id || ""));
    const canonicalPath = `/episodes/${safeEpisodeId}`;
    const canonicalUrl = `${origin}${canonicalPath}`;
    const novelUrl = episode?.novel_id ? `${origin}/novels/${episode.novel_id}` : `${origin}/`;
    const robots =
      episode?.is_public === true &&
      String(episode?.status || "public") === "public" &&
      String(episode?.novel_age_limit || "all") !== "r18"
        ? "index,follow"
        : "noindex,follow";
    const authorName = String(episode?.author_username || "").trim();
    const authorUrl = authorName ? `${origin}/users/${encodeURIComponent(authorName)}` : "";
    const jsonLd: Array<Record<string, unknown>> = [
      {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: displayEpisodeTitle,
        description: pageDescription,
        mainEntityOfPage: canonicalUrl,
        url: canonicalUrl,
        articleBody: summarizeText(episode?.body, 3000),
        author: authorName
          ? { "@type": "Person", name: authorName, url: authorUrl }
          : undefined,
      },
      {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: `${origin}/` },
          { "@type": "ListItem", position: 2, name: episode?.novel_title || "Novel", item: novelUrl },
          { "@type": "ListItem", position: 3, name: displayEpisodeTitle, item: canonicalUrl },
        ],
      },
    ];
    if (authorName) {
      jsonLd.push({
        "@context": "https://schema.org",
        "@type": "Person",
        name: authorName,
        url: authorUrl,
      });
    }
    return applySeoMeta({
      title: pageTitle,
      description: pageDescription,
      canonicalPath,
      ogType: "article",
      imageUrl: episode?.cover_image_url || "/ogp.png",
      robots,
      jsonLd,
    });
  }, [episode, id, t, lang]);

  // ★ 画像モーダル
  const [modalImageUrl, setModalImageUrl] = useState("");
  const isPremiumUser = !!episode?.is_premium_user;
  const isFreeReadingTime = !!episode?.is_free_reading_time;
  const isFreePublic = !!episode?.is_free_public;
  const handleBackToNovel = () => {
    if (episode?.novel_id != null) {
      navigate(`/novels/${episode.novel_id}`);
      return;
    }
    navigate("/");
  };

  const handleShareToX = () => {
    if (!episode?.id) return;

    const origin = window.location.origin;
    const shareUrl = `${origin}/share/episodes/${episode.id}`;
    const displayTitle = formatEpisodeDisplayTitle(
      episode.number || episode.episode_number,
      episode.title
    );
    const text = displayTitle
      ? `${displayTitle}`
      : t({ ja: "エピソードを読みました", en: "I read this episode" });
    const intentUrl = `https://x.com/intent/tweet?url=${encodeURIComponent(
      shareUrl
    )}&text=${encodeURIComponent(text)}`;
    window.open(intentUrl, "_blank", "noopener,noreferrer");
  };

  const handleShareToInstagram = async () => {
    if (!episode?.id) return;

    const origin = window.location.origin;
    const shareUrl = `${origin}/share/episodes/${episode.id}`;
    const displayTitle = formatEpisodeDisplayTitle(
      episode.number || episode.episode_number,
      episode.title
    );
    const text = displayTitle
      ? `${displayTitle}`
      : t({ ja: "エピソードを読みました", en: "I read this episode" });
    const baseShareData = { title: displayTitle || "Episode", text, url: shareUrl };

    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        let shareData: ShareData = baseShareData;
        if (episode.cover_image_url) {
          const imageUrl = API_BASE + episode.cover_image_url;
          const res = await fetch(imageUrl);
          if (res.ok) {
            const blob = await res.blob();
            const file = new File([blob], "cover.png", {
              type: blob.type || "image/png",
            });
            if (navigator.canShare?.({ ...baseShareData, files: [file] })) {
              shareData = { ...baseShareData, files: [file] };
            }
          }
        }
        await navigator.share(shareData);
        return;
      } catch (err) {
        if (!(err instanceof DOMException && err.name === "AbortError")) {
          console.error(err);
        }
      }
    }

    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(shareUrl);
        alert(
          t({
            ja: "リンクをコピーしました。Instagramで共有してください。",
            en: "Link copied. Share it on Instagram.",
          })
        );
      } catch (err) {
        console.error(err);
      }
    }
    window.open("https://www.instagram.com/", "_blank", "noopener,noreferrer");
  };

  const handleSubscribe = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      alert(t({ ja: "ログインしてください。ログインページへ移動します。", en: "Please log in. Redirecting to login page." }));
      navigate("/login");
      return;
    }
    try {
      const res = await fetch(API_BASE + "/api/stripe/create-checkout-session", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({}),
      });
      if (res.status === 401) {
        alert(
          t({ ja: "ログインしてください。ログインページへ移動します。", en: "Please log in. Redirecting to login page." })
        );
        navigate("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(
          t({ ja: "決済セッションの作成に失敗しました", en: "Failed to create checkout session." })
        );
      }
      const data = await res.json();
      if (data.url) {
        const returnTo = window.location.pathname + window.location.search;
        sessionStorage.setItem("stripe_return_to", returnTo);
        window.location.href = data.url;
      } else {
        alert(t({ ja: "決済URLを取得できませんでした。", en: "Could not get checkout URL." }));
      }
    } catch (e) {
      console.error(e);
      alert(t({ ja: "決済処理中にエラーが発生しました", en: "An error occurred during payment." }));
    }
  };

  useEffect(() => {
    const fetchEpisode = async () => {
      try {
        setLoading(true);
        setError("");

        const token = localStorage.getItem("token");
        const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
        const res = await fetch(API_BASE + "/api/episodes/" + id, { headers: authHeaders });
        if (!res.ok) {
          throw new Error(
            t(
              { ja: "エピソードの取得に失敗しました ({{status}})", en: "Failed to load episode ({{status}})" },
              { status: res.status }
            )
          );
        }

        let data = await res.json();

        // For non-Japanese UI, try translated title/body (and novel meta) when available.
        if (TRANSLATABLE_LANGS.has(lang) && data?.id) {
          const fetchJson = async (path: string) => {
            const r = await fetch(`${API_BASE}${path}`, { headers: authHeaders });
            if (!r.ok) return null;
            return await r.json().catch(() => null);
          };

          const [epTr, novelTr] = await Promise.all([
            fetchJson(`/api/episodes/${data.id}/translations/${encodeURIComponent(lang)}`),
            data?.novel_id
              ? fetchJson(`/api/novels/${data.novel_id}/translations/${encodeURIComponent(lang)}`)
              : Promise.resolve(null),
          ]);

          if (epTr?.title) data = { ...data, title: epTr.title };
          if (typeof epTr?.body === "string") data = { ...data, body: epTr.body };
          if (Array.isArray(epTr?.tags)) {
            data = { ...data, tags: epTr.tags.map((name: string) => ({ name })) };
          }

          if (novelTr) {
            data = {
              ...data,
              novel_title: novelTr.title || data.novel_title,
              novel_description: novelTr.description ?? data.novel_description,
              novel_tags: Array.isArray(novelTr.tags) ? novelTr.tags.map((name: string) => ({ name })) : data.novel_tags,
            };
          }
        }

        const needsConfirm = !!data.age_confirmation_required;
        const ageConfirmKey = `age_confirmed_novel_${data.novel_id}`;
        const alreadyConfirmed =
          isGoogleCrawler() ||
          (typeof sessionStorage !== "undefined" &&
            sessionStorage.getItem(ageConfirmKey) === "yes");
        if (needsConfirm && !alreadyConfirmed) {
          const target = data.novel_id ? `/novels/${data.novel_id}` : "/";
          navigate(target, { replace: true });
          return;
        }

        setEpisode(data);
        setAgeConfirmRequired(needsConfirm);
        if (needsConfirm) {
          setAgeConfirmed(alreadyConfirmed);
        } else {
          setAgeConfirmed(false);
        }

        // ★ いいね / 閲覧数
        if (typeof data.like_count === "number") {
          setLikeCount(data.like_count);
        }
        if (typeof data.is_liked === "boolean") {
          setIsLiked(data.is_liked);
        }
      } catch (err) {
        console.error(err);
        setError(
          getErrorMessage(
            err,
            t({ ja: "エピソードの取得中にエラーが発生しました", en: "An error occurred while loading the episode." })
          )
        );
      } finally {
        setLoading(false);
      }
    };

    fetchEpisode();
    fetch(`${API_BASE}/api/episodes/${id}/comments`)
      .then((res) => res.json())
      .then((data) => setComments(Array.isArray(data) ? data : []));
  }, [id, lang, navigate]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/users/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        setMyUserId(data.id);
      } catch (e) {
        console.error(e);
      }
    })();
  }, []);

  const handlePostComment = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      alert(t({ ja: "コメントするにはログインが必要です。", en: "Login required to comment." }));
      return;
    }
    const body = (commentBody || "").trim();
    if (!body) {
      alert(t({ ja: "コメントを入力してください。", en: "Please enter a comment." }));
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/episodes/${id}/comments`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ body }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || t({ ja: "コメント投稿に失敗しました", en: "Failed to post comment." }));
      }
      setCommentBody("");
      const listRes = await fetch(`${API_BASE}/api/episodes/${id}/comments`);
      const listData = await listRes.json().catch(() => []);
      setComments(Array.isArray(listData) ? listData : []);
    } catch (e) {
      console.error(e);
      alert(getErrorMessage(e, t({ ja: "コメント投稿中にエラーが発生しました", en: "An error occurred while posting comment." })));
    }
  };

  const handleDeleteComment = async (commentId: EpisodeComment["id"]) => {
    const token = localStorage.getItem("token");
    if (!token) {
      alert(t({ ja: "コメントを削除するにはログインが必要です。", en: "Login required to delete comments." }));
      return;
    }
    if (!window.confirm(t({ ja: "このコメントを削除します。よろしいですか？", en: "Delete this comment?" }))) {
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE}/api/episodes/${id}/comments/${commentId}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "コメントの削除に失敗しました", en: "Failed to delete comment." }));
      }
      setComments((prev) => prev.filter((c) => c.id !== commentId));
    } catch (e) {
      console.error(e);
      alert(getErrorMessage(e, t({ ja: "コメント削除中にエラーが発生しました", en: "An error occurred while deleting comment." })));
    }
  };

  // ★ いいねトグル
  const handleToggleLike = async () => {
    const token =
      localStorage.getItem("token") || localStorage.getItem("access_token");
    if (!token) {
      alert(t({ ja: "いいねするにはログインが必要です。", en: "Login required to like." }));
      navigate("/login");
      return;
    }

    const method = isLiked ? "DELETE" : "POST";
    const endpoint = `/api/episodes/${id}/like`;

    try {
      const res = await fetch(API_BASE + endpoint, {
        method,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "いいね操作に失敗しました", en: "Failed to like." }));
      }

      if (typeof data.like_count === "number") {
        setLikeCount(data.like_count);
      } else {
        const nextLiked =
          typeof data.liked === "boolean" ? data.liked : !isLiked;
        const delta = nextLiked === isLiked ? 0 : nextLiked ? 1 : -1;
        setLikeCount((prev) => Math.max(0, prev + delta));
      }
      if (typeof data.liked === "boolean") {
        setIsLiked(data.liked);
      } else {
        setIsLiked((prev) => !prev);
      }
    } catch (e) {
      console.error(e);
      alert(getErrorMessage(e, t({ ja: "いいね操作中にエラーが発生しました", en: "An error occurred while liking." })));
    }
  };

  if (loading) {
    return <div>{t({ ja: "読み込み中...", en: "Loading..." })}</div>;
  }

  if (error) {
    return (
      <div>
        <p style={{ color: "red" }}>{error}</p>
        <button className="btn btn-border" onClick={handleBackToNovel}>
          {t({ ja: "戻る", en: "Back" })}
        </button>
      </div>
    );
  }

  if (!episode) {
    return (
      <div>
        <p>{t({ ja: "エピソードが見つかりませんでした。", en: "Episode not found." })}</p>
        <button className="btn btn-border" onClick={handleBackToNovel}>
          {t({ ja: "戻る", en: "Back" })}
        </button>
      </div>
    );
  }
  if (ageConfirmRequired && !ageConfirmed) {
    const summary = summarizeText(episode.novel_description, 200);
    const tags = Array.isArray(episode.novel_tags)
      ? episode.novel_tags
      : Array.isArray(episode.tags)
        ? episode.tags
        : [];
    const headlineTitle = episode.novel_title || episode.title;
    return (
      <div style={{ padding: 16 }}>
        <h2 style={{ marginTop: 0 }}>
          {t({ ja: "18歳以上ですか？", en: "Are you 18 or older?" })}
        </h2>
        <p style={{ color: "#666" }}>
          {t({
            ja: "この小説は18歳未満の方は閲覧できません。",
            en: "This novel is not available to users under 18.",
          })}
        </p>
        <div style={{ marginTop: 16 }}>
          {headlineTitle && <h3 style={{ margin: "0 0 6px" }}>{headlineTitle}</h3>}
          {episode.author_username && (
            <div style={{ marginBottom: 6, color: "#666" }}>
              {t({ ja: "作者", en: "Author" })}:{" "}
              <Link
                className="user-link"
                to={`/users/${encodeURIComponent(episode.author_username)}`}
              >
                {episode.author_username}
              </Link>
            </div>
          )}
          {tags.length > 0 && (
            <div className="tag-chip-row" style={{ marginBottom: 8 }}>
              {tags.map((tag: TagItem) => (
                <TagChipLink key={tag.id ?? tag.name} name={tag.name} />
              ))}
            </div>
          )}
          {summary && <p style={{ margin: "0 0 6px" }}>{summary}</p>}
          <p style={{ margin: 0, color: "#666" }}>
            {t({
              ja: "年齢制限により本文は非表示です。",
              en: "The full text is hidden due to age restrictions.",
            })}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="btn btn-border"
            onClick={() => {
              const key = `age_confirmed_novel_${episode.novel_id}`;
              sessionStorage.setItem(key, "yes");
              setAgeConfirmed(true);
            }}
          >
            {t({ ja: "はい", en: "Yes" })}
          </button>
          <button className="btn btn-border" onClick={() => navigate("/")}>
            {t({ ja: "いいえ", en: "No" })}
          </button>
        </div>
      </div>
    );
  }

  const tags = Array.isArray(episode.tags) ? episode.tags : [];
  const illusts = Array.isArray(episode.illusts) ? episode.illusts : [];
  const canDeleteComment = (commentUserId: number | string | null | undefined) => {
    if (!myUserId) return false;
    if (commentUserId && commentUserId === myUserId) return true;
    return episode?.author_id === myUserId;
  };

  const formatDateTime = (isoString: string | null | undefined) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString(lang === "en" ? "en-US" : "ja-JP", {
      timeZone: "Asia/Tokyo",
    });
  };

  const titleStartsWithEpisodePrefix = (title: string | null | undefined) => {
    if (typeof title !== "string") return false;
    return /^\s*第\s*(?:[0-9０-９]+|[一二三四五六七八九十百千万]+)\s*話/.test(title);
  };

  const formatEpisodeDisplayTitle = (episodeNumber: string | number | null | undefined, title: string | null | undefined) => {
    const cleanTitle = typeof title === "string" ? title.trim() : "";
    if (cleanTitle && titleStartsWithEpisodePrefix(cleanTitle)) return cleanTitle;
    if (episodeNumber == null || episodeNumber === "") return cleanTitle;
    if (lang === "en") {
      return cleanTitle ? `Episode ${episodeNumber}: ${cleanTitle}` : `Episode ${episodeNumber}`;
    }
    return cleanTitle ? `第${episodeNumber}話 ${cleanTitle}` : `第${episodeNumber}話`;
  };

  const openModal = (url: string | null | undefined) => {
    if (!url) return;
    setModalImageUrl(url);
  };

  const closeModal = () => {
    setModalImageUrl("");
  };

  const buildBodySegments = (text: string | null | undefined, illustList: IllustItem[]) => {
    const safeText = text || "";
    const segments: Array<{ type: "text"; text: string } | { type: "illust"; tag: string; illust?: IllustItem }> = [];
    const tagToIllust = new Map<string, IllustItem>();
    const usedTags = new Set<string>();
    for (const ill of illustList) {
      if (ill.illust_tag) {
        tagToIllust.set(ill.illust_tag, ill);
      }
    }

    const regex = /\[\[illust:(\d{8})\]\]/g;
    let lastIndex = 0;
    let match;
    while ((match = regex.exec(safeText)) !== null) {
      if (match.index > lastIndex) {
        segments.push({ type: "text", text: safeText.slice(lastIndex, match.index) });
      }
      const tag = `illust:${match[1]}`;
      const illust = tagToIllust.get(tag);
      if (illust) {
        usedTags.add(tag);
      }
      segments.push({ type: "illust", tag, illust });
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < safeText.length) {
      segments.push({ type: "text", text: safeText.slice(lastIndex) });
    }
    return { segments, usedTags };
  };

  const { segments: bodySegments } = buildBodySegments(
    episode.body || "",
    illusts
  );
  const prevEpisode = episode?.prev_episode || null;
  const nextEpisode = episode?.next_episode || null;
  const prevEpisodeTitle = prevEpisode
    ? formatEpisodeDisplayTitle(
        prevEpisode.episode_number ?? prevEpisode.number,
        prevEpisode.title
      )
    : "";
  const nextEpisodeTitle = nextEpisode
    ? formatEpisodeDisplayTitle(
        nextEpisode.episode_number ?? nextEpisode.number,
        nextEpisode.title
      )
    : "";
  const prevEpisodeLabel = prevEpisodeTitle
    ? t({ ja: "前のエピソードへ：{{title}}", en: "Previous episode: {{title}}" }, { title: prevEpisodeTitle })
    : t({ ja: "前のエピソードへ", en: "Previous episode" });
  const nextEpisodeLabel = nextEpisodeTitle
    ? t({ ja: "次のエピソードへ：{{title}}", en: "Next episode: {{title}}" }, { title: nextEpisodeTitle })
    : t({ ja: "次のエピソードへ", en: "Next episode" });

  return (
    <div>
      <button className="btn btn-border" onClick={handleBackToNovel}>
        {t({ ja: "← 戻る", en: "← Back" })}
      </button>

      <h2 style={{ marginTop: 12 }}>
        {formatEpisodeDisplayTitle(
          episode.number || episode.episode_number,
          episode.title
        )}
      </h2>

      {/* タグ */}
      {tags.length > 0 && (
        <div className="tag-chip-row" style={{ marginBottom: 8 }}>
              {tags.map((t: TagItem) => (
            <TagChipLink key={t.id ?? t.name} name={t.name} />
          ))}
        </div>
      )}

      {/* メタ情報 + いいね */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          alignItems: "center",
          marginBottom: 8,
          fontSize: "0.9rem",
          color: "#666",
        }}
      >
        {episode.author_username ? (
          <span>
            {t({ ja: "作者", en: "Author" })}:{" "}
            <Link
              className="user-link"
              to={`/users/${encodeURIComponent(episode.author_username)}`}
            >
              {episode.author_username}
            </Link>
          </span>
        ) : (
          <span>{t({ ja: "小説ID", en: "Novel ID" })}: {episode.novel_id}</span>
        )}
        {episode.created_at && (
          <span>{t({ ja: "作成日時", en: "Created" })}: {formatDateTime(episode.created_at)}</span>
        )}
        {typeof episode.view_count === "number" && (
          <span>{t({ ja: "閲覧数", en: "Views" })}: {episode.view_count}</span>
        )}
        <span>{t({ ja: "文字数", en: "Chars" })}: {countChars(episode.body)}</span>
	<Link
          to={`/ai-novel?episode_id=${episode.id}`}
          className="btn btn-border"
        >
          {t({ ja: "AIで続きを生成", en: "Generate continuation with AI" })}
        </Link>

        <button
          type="button"
          className="btn btn-border"
          onClick={handleShareToX}
        >
          {t({ ja: "Xで共有", en: "Share on X" })}
        </button>
        <button
          type="button"
          className="btn btn-border"
          onClick={handleShareToInstagram}
        >
          {t({ ja: "Instagramで共有", en: "Share on Instagram" })}
        </button>

        <button
          type="button"
          className="btn btn-border"
          onClick={handleToggleLike}
          style={{ marginLeft: "auto" }}
        >
          {isLiked
            ? t({ ja: "♥ いいね済み", en: "♥ Liked" })
            : t({ ja: "♡ いいね", en: "♡ Like" })} ({likeCount})
        </button>
      </div>

      {episode?.author_id && (
        <SupportPanel
          authorUserId={episode.author_id}
          novelId={episode.novel_id}
          episodeId={episode.id}
          authorName={episode.author_username || t({ ja: "作者", en: "Author" })}
        />
      )}

      {/* 表紙画像 */}
      {episode.cover_image_url && (
        <div className="episode-cover-wrap" style={{ margin: "12px 0" }}>
          <p style={{ marginBottom: 4 }}>{t({ ja: "表紙:", en: "Cover:" })}</p>
          <img
            className="episode-cover-image"
            src={API_BASE + episode.cover_image_url}
            alt={t({ ja: "表紙画像", en: "Cover image" })}
            style={{
              maxWidth: "260px",
              ...(isXInAppBrowser ? { maxHeight: "45vh", objectFit: "contain" } : {}),
              borderRadius: 8,
              cursor: "pointer",
              boxShadow: "0 2px 6px rgba(0,0,0,0.2)",
            }}
            onClick={() => openModal(API_BASE + episode.cover_image_url)}
          />
        </div>
      )}

      <hr />

      {/* 本文 */}
      <div
        style={{
          whiteSpace: "pre-wrap",
          lineHeight: 1.8,
          marginTop: 12,
        }}
      >
        {bodySegments.map((segment, index) => {
          if (segment.type === "text") {
            return <span key={`text-${index}`}>{segment.text}</span>;
          }
          if (!segment.illust) {
            return (
                <span
                  key={`missing-${segment.tag}-${index}`}
                  style={{ color: "#888" }}
                >
                  {`[[${segment.tag}]]`}
              </span>
            );
          }
          const illust = segment.illust;
          if (!illust) return null;
          return (
            <div
              key={`illust-${illust.id ?? segment.tag}-${index}`}
              style={{
                margin: "12px 0",
                textAlign: "center",
              }}
            >
              <img
                src={API_BASE + illust.image_url}
                alt={illust.caption || t({ ja: "挿絵", en: "Illustration" })}
                style={{
                  maxWidth: "100%",
                  maxHeight: "70vh",
                  objectFit: "contain",
                  borderRadius: 6,
                  cursor: "pointer",
                  boxShadow: "0 2px 6px rgba(0,0,0,0.2)",
                }}
                onClick={() =>
                  openModal(API_BASE + illust.image_url)
                }
              />
              {illust.caption && (
                <div
                  style={{
                    marginTop: 6,
                    fontSize: 12,
                    color: "#555",
                    wordBreak: "break-word",
                  }}
                >
                  {illust.caption}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 課金ブロック */}
      {isPremiumUser ? (
        <div
          style={{
            marginTop: 16,
            padding: 12,
            border: "1px solid var(--premium-border)",
            background: "var(--premium-bg)",
            borderRadius: 6,
          }}
        >
          <p
            style={{
              marginBottom: 0,
              color: "var(--premium-text)",
              fontWeight: "bold",
            }}
          >
            {t({ ja: "★ あなたは課金済みユーザーです（PREMIUM）", en: "★ You are a paid user (PREMIUM)" })}
          </p>
          <p style={{ marginTop: 6, fontSize: 12, color: "var(--premium-text)" }}>
            {t(FREE_READING_SCHEDULE)}
          </p>
        </div>
      ) : isFreePublic ? (
        <div
          style={{
            marginTop: 16,
            padding: 12,
            border: "1px solid #0a6",
            background: "#e8fff5",
            borderRadius: 6,
          }}
        >
          <p style={{ marginBottom: 6, fontWeight: "bold", color: "#0a6" }}>
            {t({
              ja: "★ このエピソードは無料公開中のため、誰でも全文を読めます",
              en: "★ This episode is free public, so everyone can read the full text.",
            })}
          </p>
        </div>
      ) : isFreeReadingTime ? (
        <div
          style={{
            marginTop: 16,
            padding: 12,
            border: "1px solid #0a6",
            background: "#e8fff5",
            borderRadius: 6,
          }}
        >
          <p style={{ marginBottom: 6, fontWeight: "bold", color: "#0a6" }}>
            {t({ ja: "★ 今は無料開放時間のため全文を読めます", en: "★ It's free reading time, so you can read the full text" })}
          </p>
          <p style={{ margin: 0, fontSize: 12, color: "#0a6" }}>
            {t(FREE_READING_SCHEDULE)}
          </p>
        </div>
      ) : (
        <div
          style={{
            marginTop: 16,
            padding: 12,
            border: "1px dashed #f0a",
            borderRadius: 6,
          }}
        >
          <p style={{ marginBottom: 8 }}>
            {t({ ja: "全文を読むには月額1000円のプレミアム購読が必要です。", en: "A ¥1000/month premium subscription is required to read the full text." })}
          </p>
          <p style={{ marginBottom: 8, fontSize: 12, color: "#666" }}>
            {t(FREE_READING_SCHEDULE)}
          </p>
          <button className="btn btn-border" onClick={handleSubscribe}>
            {t({ ja: "課金して続きを読む", en: "Subscribe to read full" })}
          </button>
        </div>
      )}

      {(prevEpisode?.id || nextEpisode?.id) && (
        <div style={{ marginTop: 16, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {prevEpisode?.id && (
            <Link to={`/episodes/${prevEpisode.id}`} className="btn btn-border">
              {prevEpisodeLabel}
            </Link>
          )}
          {nextEpisode?.id && (
            <Link to={`/episodes/${nextEpisode.id}`} className="btn btn-border">
              {nextEpisodeLabel}
            </Link>
          )}
        </div>
      )}

      <div style={{ marginTop: "2rem" }}>
        <h3>{t({ ja: "コメント", en: "Comments" })}</h3>

        {comments.length === 0 ? (
          <p style={{ fontSize: "0.9rem", color: "#666" }}>
            {t({
              ja: "まだコメントはありません。最初の感想を書いてみましょう。",
              en: "No comments yet. Share the first impression.",
            })}
          </p>
        ) : (
          <div>
            {comments.map((c) => (
              <div
                key={c.id}
                id={`comment-${c.id}`}
                style={{
                  borderBottom: "1px solid #ddd",
                  padding: "6px 0",
                  marginBottom: 4,
                  fontSize: "0.9rem",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 8,
                  }}
                >
                  <strong>
                    {c.username || t({ ja: "匿名", en: "Anonymous" })}
                    {myUserId && c.user_id === myUserId ? t({ ja: "（あなた）", en: " (you)" }) : ""}
                  </strong>

                  {canDeleteComment(c.user_id) && (
                    <button
                      type="button"
                      className="btn btn-border"
                      style={{
                        borderColor: "#c00",
                        color: "#c00",
                        fontSize: "0.8rem",
                      }}
                      onClick={() => handleDeleteComment(c.id)}
                    >
                      {t({ ja: "削除", en: "Delete" })}
                    </button>
                  )}
                </div>
                <div style={{ whiteSpace: "pre-wrap", marginTop: 2 }}>
                  {c.body}
                </div>
              </div>
            ))}
          </div>
        )}

        <div style={{ marginTop: 8 }}>
          <textarea
            value={commentBody}
            onChange={(e) => setCommentBody(e.target.value)}
            placeholder={t({ ja: "感想や一言コメントを書いてください", en: "Write your thoughts or a short comment" })}
            style={{
              width: "100%",
              height: "70px",
              marginTop: "8px",
              padding: 8,
              fontSize: "0.9rem",
            }}
          />
          <button
            className="btn btn-border"
            style={{ marginTop: 8 }}
            onClick={handlePostComment}
          >
            {t({ ja: "コメント投稿", en: "Post comment" })}
          </button>
        </div>
      </div>

      <div style={{ marginTop: 24 }}>
        <Link to={"/novels/" + episode.novel_id} className="btn btn-border">
          {t({ ja: "小説詳細へ戻る", en: "Back to novel" })}
        </Link>
      </div>

      {/* 画像ポップアップモーダル */}
      {modalImageUrl && (
        <div
          onClick={closeModal}
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.7)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              maxWidth: "90vw",
              maxHeight: "90vh",
              background: "#111",
              padding: 8,
              borderRadius: 8,
            }}
          >
            <img
              src={modalImageUrl}
              alt={t({ ja: "拡大画像", en: "Zoomed image" })}
              style={{
                maxWidth: "100%",
                maxHeight: isXInAppBrowser ? "70vh" : "80vh",
                objectFit: "contain",
                display: "block",
                margin: "0 auto",
              }}
            />
            <button
              type="button"
              className="btn btn-border"
              onClick={closeModal}
              style={{
                marginTop: 8,
                display: "block",
                marginLeft: "auto",
              }}
            >
              {t({ ja: "閉じる", en: "Close" })}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
