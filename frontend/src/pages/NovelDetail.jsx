import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import TagChipLink from "../components/TagChipLink.jsx";
import SupportPanel from "../components/SupportPanel.jsx";
import { useI18n } from "../lib/i18n";
import { isGoogleCrawler } from "../lib/seo";
import { getApiBase } from "../lib/apiBase";
import {
  dismissGuideBubble,
  getDismissedGuideBubbles,
  isOnboardingGuideEligible,
} from "../lib/onboardingGuide";

const API_BASE = getApiBase();
const TRANSLATABLE_LANGS = new Set(["en", "zh-cn", "zh-tw", "ko"]);
const GUIDE_CREATED_NOVEL_ID_KEY = "onboarding_created_novel_id_v1";

export default function NovelDetail() {
  const { id } = useParams(); // novel_id
  const navigate = useNavigate();
  const { t, lang } = useI18n();

  const [novel, setNovel] = useState(null);
  const [comments, setComments] = useState([]);
  const [commentBody, setCommentBody] = useState("");
  const [myUserId, setMyUserId] = useState(null);
  const [ageConfirmRequired, setAgeConfirmRequired] = useState(false);
  const [ageConfirmed, setAgeConfirmed] = useState(false);

  const authorName = novel?.author_username;
  const [isFavorited, setIsFavorited] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dismissedBubbles, setDismissedBubbles] = useState(() => getDismissedGuideBubbles());
  const [expandedBubble, setExpandedBubble] = useState("");

  // ★ いいね / 閲覧数
  const [likeCount, setLikeCount] = useState(0);
  const [isLiked, setIsLiked] = useState(false);


  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString(lang === "en" ? "en-US" : "ja-JP", {
      timeZone: "Asia/Tokyo",
    });
  };

  const titleStartsWithEpisodePrefix = (title) => {
    if (typeof title !== "string") return false;
    return /^\s*第\s*(?:[0-9０-９]+|[一二三四五六七八九十百千万]+)\s*話/.test(title);
  };

  const countChars = (value) => (value || "").length;

  const summarizeText = (text, limit = 200) => {
    const clean = (text || "").trim();
    if (!clean) return "";
    if (clean.length <= limit) return clean;
    return `${clean.slice(0, limit)}...`;
  };

  const getNovelTags = (novelData, episodeList = []) => {
    const rawTags = Array.isArray(novelData?.tags) ? novelData.tags : [];
    if (rawTags.length) {
      return rawTags.map((tag) =>
        typeof tag === "string" ? { name: tag } : tag
      );
    }
    const rawNames = Array.isArray(novelData?.tag_names) ? novelData.tag_names : [];
    if (rawNames.length) {
      return rawNames.map((name) => ({ name }));
    }
    const episodeTags = [];
    for (const episode of episodeList) {
      const tags = Array.isArray(episode?.tags) ? episode.tags : [];
      for (const tag of tags) {
        if (typeof tag === "string") {
          episodeTags.push({ name: tag });
        } else if (tag?.name) {
          episodeTags.push({ name: tag.name });
        }
      }
    }
    const seen = new Set();
    return episodeTags.filter((tag) => {
      const key = (tag?.name || "").toLowerCase();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  };

  const formatEpisodeDisplayTitle = (episodeNumber, title) => {
    const cleanTitle = typeof title === "string" ? title.trim() : "";
    if (cleanTitle && titleStartsWithEpisodePrefix(cleanTitle)) return cleanTitle;
    if (episodeNumber == null || episodeNumber === "") return cleanTitle;
    if (lang === "en") {
      return cleanTitle ? `Episode ${episodeNumber}: ${cleanTitle}` : `Episode ${episodeNumber}`;
    }
    return cleanTitle ? `第${episodeNumber}話 ${cleanTitle}` : `第${episodeNumber}話`;
  };

  const AGE_LABELS = {
    all: t({ ja: "全年齢", en: "All ages" }),
    r15: "R15",
    r18: "R18",
  };

  const getAgeLabel = (ageLimit) => {
    if (!ageLimit) return t({ ja: "全年齢", en: "All ages" });
    return AGE_LABELS[ageLimit] ?? ageLimit;
  };

  const CREATIVE_TYPE_LABELS = {
    original: t({ ja: "オリジナル", en: "Original" }),
    fanfic: t({ ja: "二次創作", en: "Fanfiction" }),
  };

  const getCreativeTypeLabel = (creativeType) => {
    if (!creativeType) return t({ ja: "オリジナル", en: "Original" });
    return CREATIVE_TYPE_LABELS[creativeType] ?? creativeType;
  };


  const toggleFavorite = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      alert(t({ ja: "お気に入りにするにはログインが必要です。", en: "Login required to favorite." }));
      navigate("/login");
      return;
    }
    if (!novel) return;

    const method = isFavorited ? "DELETE" : "POST";

    try {
      const res = await fetch(API_BASE + "/api/novels/" + novel.id + "/favorite", {
        method,
        headers: {
          Authorization: "Bearer " + token,
        },
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(
          data.detail || t({ ja: "お気に入りの操作に失敗しました", en: "Failed to update favorite." })
        );
      }

      if (typeof data.favorited === "boolean") {
        setIsFavorited(data.favorited);
      } else {
        setIsFavorited((prev) => !prev);
      }
    } catch (e) {
      console.error(e);
      alert(
        e.message || t({ ja: "お気に入り操作中にエラーが発生しました", en: "An error occurred while updating favorite." })
      );
    }
  };

  useEffect(() => {
    const fetchNovel = async () => {
      try {
        setLoading(true);
        setError("");

        const token = localStorage.getItem("token");
        const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};
        const res = await fetch(`${API_BASE}/api/novels/${id}`, { headers: authHeaders });

        if (!res.ok) {
          throw new Error(
            t(
              { ja: "小説の取得に失敗しました ({{status}})", en: "Failed to load novel ({{status}})" },
              { status: res.status }
            )
          );
        }

        let data = await res.json();

        // Non-Japanese UI: show translated novel + episode fields when available.
        if (TRANSLATABLE_LANGS.has(lang) && data?.id) {
          const fetchJson = async (path) => {
            const r = await fetch(`${API_BASE}${path}`, { headers: authHeaders });
            if (!r.ok) return null;
            return await r.json().catch(() => null);
          };
          const tr = await fetchJson(
            `/api/novels/${data.id}/translations/${encodeURIComponent(lang)}`
          );
          if (tr) {
            data = {
              ...data,
              title: tr.title || data.title,
              description: tr.description ?? data.description,
              tags: Array.isArray(tr.tags) ? tr.tags.map((name) => ({ name })) : data.tags,
            };
          }
          if (Array.isArray(data?.episodes) && data.episodes.length > 0) {
            const translatedEpisodes = await Promise.all(
              data.episodes.map(async (ep) => {
                if (!ep?.id) return ep;
                const epTr = await fetchJson(
                  `/api/episodes/${ep.id}/translations/${encodeURIComponent(lang)}`
                );
                if (!epTr) return ep;
                return {
                  ...ep,
                  title: epTr.title || ep.title,
                  tags: Array.isArray(epTr.tags)
                    ? epTr.tags.map((name) => ({ name }))
                    : ep.tags,
                };
              })
            );
            data = { ...data, episodes: translatedEpisodes };
          }
        }
        console.log("NOVEL DATA:", data);
        setNovel(data);
        setIsFavorited(!!data.is_favorited);
        const needsConfirm = !!data.age_confirmation_required;
        setAgeConfirmRequired(needsConfirm);
        if (needsConfirm) {
          if (isGoogleCrawler()) {
            setAgeConfirmed(true);
          } else {
            const key = `age_confirmed_novel_${data.id}`;
            setAgeConfirmed(sessionStorage.getItem(key) === "yes");
          }
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
      } catch (e) {
        console.error(e);
        setError(
          e.message || t({ ja: "小説の取得中にエラーが発生しました", en: "An error occurred while loading the novel." })
        );
      } finally {
        setLoading(false);
      }
    };

    fetchNovel();
    fetch(`${API_BASE}/api/novels/${id}/comments`)
      .then((res) => res.json())
      .then((data) => setComments(Array.isArray(data) ? data : []));

  }, [id, lang]);

  // ★ 小説 いいねトグル
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
      const res = await fetch(`${API_BASE}/api/novels/${id}/comments`, {
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
      const listRes = await fetch(`${API_BASE}/api/novels/${id}/comments`);
      const listData = await listRes.json().catch(() => []);
      setComments(Array.isArray(listData) ? listData : []);
    } catch (e) {
      console.error(e);
      alert(
        e.message || t({ ja: "コメント投稿中にエラーが発生しました", en: "An error occurred while posting comment." })
      );
    }
  };


  const handleToggleLike = async () => {
    const token =
      localStorage.getItem("token") || localStorage.getItem("access_token");
    if (!token) {
      alert(t({ ja: "いいねするにはログインが必要です。", en: "Login required to like." }));
      navigate("/login");
      return;
    }

    const method = isLiked ? "DELETE" : "POST";
    const endpoint = `/api/novels/${id}/like`;

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

      const nextLiked =
        typeof data.liked === "boolean" ? data.liked : !isLiked;
      const delta = nextLiked === isLiked ? 0 : nextLiked ? 1 : -1;
      if (typeof data.like_count === "number") {
        setLikeCount(data.like_count);
      } else {
        setLikeCount((prev) => Math.max(0, prev + delta));
      }
      setIsLiked(nextLiked);
    } catch (e) {
      console.error(e);
      alert(
        e.message || t({ ja: "いいね操作中にエラーが発生しました", en: "An error occurred while liking." })
      );
    }
  };

  // ★ 小説編集ボタン
  const handleEditNovel = () => {
    navigate(`/novels/${id}/edit`);
  };

  // ★ 小説削除ボタン
  const handleDeleteNovel = async () => {
    if (!window.confirm(t({ ja: "この小説と全エピソードを削除します。よろしいですか？", en: "Delete this novel and all episodes?" }))) {
      return;
    }
    const token = localStorage.getItem("token");
    if (!token) {
      alert(t({ ja: "削除するにはログインが必要です。", en: "Login required to delete." }));
      navigate("/login");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/novels/${id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "小説の削除に失敗しました", en: "Failed to delete novel." }));
      }

      alert(t({ ja: "小説を削除しました。", en: "Novel deleted." }));
      navigate("/");
    } catch (e) {
      console.error(e);
      alert(e.message || t({ ja: "削除中にエラーが発生しました", en: "An error occurred while deleting." }));
    }
  };

    const handleDeleteComment = async (commentId) => {
    const token = localStorage.getItem("token");
    if (!token) {
      alert(t({ ja: "コメントを削除するにはログインが必要です。", en: "Login required to delete comments." }));
      navigate("/login");
      return;
    }
    if (!window.confirm(t({ ja: "このコメントを削除します。よろしいですか？", en: "Delete this comment?" }))) {
      return;
    }

    try {
      const res = await fetch(
        `${API_BASE}/api/novels/${id}/comments/${commentId}`,
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

      // ローカル状態からも削除
      setComments((prev) => prev.filter((c) => c.id !== commentId));
    } catch (e) {
      console.error(e);
      alert(
        e.message || t({ ja: "コメント削除中にエラーが発生しました", en: "An error occurred while deleting comment." })
      );
    }
  };


  // ★ エピソード編集ボタン
  const handleEditEpisode = (episodeId) => {
    navigate(`/episodes/${episodeId}/edit`);
  };

  // ★ エピソード削除ボタン
  // ★ 新規エピソード作成ボタン
  const handleCreateEpisode = () => {
    try {
      const guidedNovelId = localStorage.getItem(GUIDE_CREATED_NOVEL_ID_KEY);
      if (guidedNovelId && String(guidedNovelId) === String(id)) {
        localStorage.removeItem(GUIDE_CREATED_NOVEL_ID_KEY);
      }
    } catch {
      // ignore
    }
    navigate(`/novels/${id}/episodes/new`);
  };

  const handleDeleteEpisode = async (episodeId) => {
    if (!window.confirm(t({ ja: "このエピソードを削除します。よろしいですか？", en: "Delete this episode?" }))) {
      return;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      alert(t({ ja: "削除するにはログインが必要です。", en: "Login required to delete." }));
      navigate("/login");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/episodes/${episodeId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "エピソードの削除に失敗しました", en: "Failed to delete episode." }));
      }

      // ローカル状態からも削除
      setNovel((prev) => {
        if (!prev) return prev;
        const eps = Array.isArray(prev.episodes) ? prev.episodes : [];
        return {
          ...prev,
          episodes: eps.filter((ep) => ep.id !== episodeId),
        };
      });

      alert(t({ ja: "エピソードを削除しました。", en: "Episode deleted." }));
    } catch (e) {
      console.error(e);
      alert(
        e.message || t({ ja: "削除中にエラーが発生しました", en: "An error occurred while deleting." })
      );
    }
  };

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

  if (loading) {
    return <div>{t({ ja: "読み込み中...", en: "Loading..." })}</div>;
  }

  if (error) {
    return (
      <div>
        <p style={{ color: "red" }}>{error}</p>
        <button className="btn btn-border" onClick={() => navigate("/")}>
          {t({ ja: "戻る", en: "Back" })}
        </button>
      </div>
    );
  }

  if (!novel) {
    return (
      <div>
        <p>{t({ ja: "小説が見つかりませんでした。", en: "Novel not found." })}</p>
        <button className="btn btn-border" onClick={() => navigate("/")}>
          {t({ ja: "戻る", en: "Back" })}
        </button>
      </div>
    );
  }
  if (ageConfirmRequired && !ageConfirmed) {
    const fallbackEpisodes = Array.isArray(novel.episodes) ? novel.episodes : [];
    const tags = getNovelTags(novel, fallbackEpisodes);
    const summary = summarizeText(novel.description, 200);
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
          <h3 style={{ margin: "0 0 6px" }}>{novel.title}</h3>
          {authorName && (
            <div style={{ marginBottom: 6, color: "#666" }}>
              {t({ ja: "作者", en: "Author" })}:{" "}
              <Link
                className="user-link"
                to={`/users/${encodeURIComponent(authorName)}`}
              >
                {authorName}
              </Link>
            </div>
          )}
          {tags.length > 0 && (
            <div className="tag-chip-row" style={{ marginBottom: 8 }}>
              {tags.map((tag) => (
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
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button
            className="btn btn-border"
            onClick={() => {
              const key = `age_confirmed_novel_${novel.id}`;
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

  const episodes = Array.isArray(novel.episodes) ? novel.episodes : [];
  const tags = getNovelTags(novel, episodes);
  const canShowGuides = isOnboardingGuideEligible();
  const isBubbleVisible = (key) => !dismissedBubbles.has(String(key));
  const handleDismissBubble = (e, key) => {
    e.preventDefault();
    e.stopPropagation();
    dismissGuideBubble(key);
    setDismissedBubbles(getDismissedGuideBubbles());
    setExpandedBubble((prev) => (prev === key ? "" : prev));
  };
  const showEpisodeGuide = (() => {
    if (!canShowGuides) return false;
    if (!myUserId || myUserId !== novel?.author_id) return false;
    if (episodes.length > 0) return false;
    try {
      const guidedNovelId = localStorage.getItem(GUIDE_CREATED_NOVEL_ID_KEY);
      return (
        Boolean(guidedNovelId) &&
        String(guidedNovelId) === String(novel?.id) &&
        isBubbleVisible("noveldetail_episode")
      );
    } catch {
      return false;
    }
  })();
  const coverImageUrl =
    novel.cover_image_url ||
    episodes.find((ep) => ep.cover_image_url)?.cover_image_url ||
    "";

  return (
    <div>
      <button className="btn btn-border" onClick={() => navigate("/")}>
        {t({ ja: "← 一覧に戻る", en: "← Back to list" })}
      </button>

      <div
        style={{
          marginTop: 12,
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <h2 style={{ margin: 0 }}>{novel.title}</h2>

        {/* 小説編集・削除ボタン */}
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button
            type="button"
            className="btn btn-border"
            onClick={handleEditNovel}
          >
            {t({ ja: "小説を編集", en: "Edit novel" })}
          </button>
          <button
            type="button"
            className="btn btn-border"
            style={{ borderColor: "#c00", color: "#c00" }}
            onClick={handleDeleteNovel}
          >
            {t({ ja: "小説を削除", en: "Delete novel" })}
          </button>
        </div>
      </div>
            {/* 年齢区分 & AI創作バッジ */}
      <div
        style={{
          marginTop: 8,
          marginBottom: 4,
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
          alignItems: "center",
          fontSize: "0.85rem",
        }}
      >
        <span
          style={{
            display: "inline-block",
            padding: "2px 8px",
            borderRadius: 999,
            border: "1px solid #888",
          }}
        >
          {getAgeLabel(novel.age_limit)}
        </span>

        <span
          style={{
            display: "inline-block",
            padding: "2px 8px",
            borderRadius: 999,
            border: "1px solid #888",
          }}
        >
          {getCreativeTypeLabel(novel.creative_type)}
        </span>

        {novel.is_ai_generated && (
          <span
            style={{
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: 999,
              border: "1px solid #888",
            }}
          >
            {t({ ja: "AI創作", en: "AI-generated" })}
          </span>
        )}
      </div>

      {/* 著者 / 日付 / 閲覧数 / いいね */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          alignItems: "center",
          marginTop: 8,
          marginBottom: 8,
          fontSize: "0.9rem",
          color: "#666",
        }}
      >
          {authorName && (
            <span>
              {t({ ja: "作者", en: "Author" })}:{" "}
              <Link
                className="user-link"
                to={`/users/${encodeURIComponent(authorName)}`}
              >
                {authorName}
              </Link>
            </span>
          )}
	{novel.created_at && (
          <span>{t({ ja: "作成日時", en: "Created" })}: {formatDateTime(novel.created_at)}</span>
        )}
        {typeof novel.view_count === "number" && (
          <span>{t({ ja: "閲覧数", en: "Views" })}: {novel.view_count}</span>
        )}
        {typeof novel.total_char_count === "number" && (
          <span>{t({ ja: "総文字数", en: "Total chars" })}: {novel.total_char_count}</span>
        )}
        {/* お気に入りボタン */}
        <button
          type="button"
          className="btn btn-border"
          onClick={toggleFavorite}
        >
          {isFavorited
            ? t({ ja: "★ お気に入り済み", en: "★ Favorited" })
            : t({ ja: "☆ お気に入りに追加", en: "☆ Add to favorites" })}
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

      {coverImageUrl && (
        <div style={{ margin: "12px 0" }}>
          <p style={{ marginBottom: 4 }}>{t({ ja: "表紙:", en: "Cover:" })}</p>
          <img
            src={API_BASE + coverImageUrl}
            alt={t({ ja: "表紙画像", en: "Cover image" })}
            style={{
              maxWidth: "260px",
              borderRadius: 8,
              boxShadow: "0 2px 6px rgba(0,0,0,0.2)",
            }}
          />
        </div>
      )}

      {novel?.author_id && (
        <SupportPanel
          authorUserId={novel.author_id}
          novelId={novel.id}
          authorName={authorName || t({ ja: "作者", en: "Author" })}
        />
      )}

      {/* タグ */}
      {tags.length > 0 && (
        <div className="tag-chip-row" style={{ marginBottom: 12 }}>
          {tags.map((t) => (
            <TagChipLink key={t.id ?? t.name} name={t.name} />
          ))}
        </div>
      )}

      {/* 説明文 */}
      {novel.description && (
        <div
          style={{
            marginTop: 8,
            marginBottom: 16,
            whiteSpace: "pre-wrap",
            lineHeight: 1.6,
          }}
        >
          {novel.description}
        </div>
      )}
      <div style={{ fontSize: "0.85rem", color: "#777", marginBottom: 8 }}>
        {t({ ja: "概要の文字数", en: "Summary length" })}: {countChars(novel.description)}
      </div>

      <hr />
      

      {/* エピソード一覧 */}
      <h3 style={{ marginTop: 16 }}>{t({ ja: "エピソード一覧", en: "Episodes" })}</h3>

      {/* エピソード追加ボタン */}
      <div style={{ marginTop: 8, marginBottom: 8 }}>
        <button
          type="button"
          className={`btn btn-border ${showEpisodeGuide ? "onboarding-guide-anchor" : ""}`.trim()}
          onClick={handleCreateEpisode}
        >
          {showEpisodeGuide && (
            <span
              className={`onboarding-guide-pop ${expandedBubble === "noveldetail_episode" ? "is-expanded" : ""}`.trim()}
              role="note"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setExpandedBubble((prev) => (prev === "noveldetail_episode" ? "" : "noveldetail_episode"));
              }}
            >
              <span className="onboarding-guide-dismiss" role="button" tabIndex={0} onClick={(e) => handleDismissBubble(e, "noveldetail_episode")}>
                {t({ ja: "吹き出しを消す", en: "Dismiss bubble" })}
              </span>
              <span
                className="onboarding-guide-close"
                role="button"
                tabIndex={0}
                onClick={(e) => handleDismissBubble(e, "noveldetail_episode")}
              >
                ×
              </span>
              <span>{t({ ja: "次はエピソード作成", en: "Next: create episode" })}</span>
            </span>
          )}
          {t({ ja: "＋ エピソードを追加", en: "+ Add episode" })}
        </button>
      </div>

      {episodes.length === 0 ? (
        <p>{t({ ja: "まだエピソードがありません。", en: "No episodes yet." })}</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, marginTop: 8 }}>
          {episodes.map((ep) => (
            <li
              key={ep.id}
              style={{
                padding: "8px 0",
                borderBottom: "1px solid #eee",
                display: "flex",
                flexDirection: "column",
                gap: 4,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  flexWrap: "wrap",
                }}
              >
                <Link
                  to={`/episodes/${ep.id}`}
                  style={{ fontWeight: "bold", marginRight: "auto" }}
                >
                  {formatEpisodeDisplayTitle(
                    ep.number || ep.episode_number,
                    ep.title
                  )}
                </Link>

                {/* エピソード編集・削除ボタン */}
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => handleEditEpisode(ep.id)}
                >
                  {t({ ja: "編集", en: "Edit" })}
                </button>
                <button
                  type="button"
                  className="btn btn-border"
                  style={{ borderColor: "#c00", color: "#c00" }}
                  onClick={() => handleDeleteEpisode(ep.id)}
                >
                  {t({ ja: "削除", en: "Delete" })}
                </button>
              </div>

              {Array.isArray(ep.tags) && ep.tags.length > 0 && (
                <div className="tag-chip-row">
                  {ep.tags.map((tag) => (
                    <TagChipLink key={tag.id ?? tag.name} name={tag.name} />
                  ))}
                </div>
              )}

              <div
                style={{
                  fontSize: "0.85rem",
                  color: "#777",
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 8,
                }}
              >
                {ep.created_at && (
                  <span>{t({ ja: "作成日時", en: "Created" })}: {formatDateTime(ep.created_at)}</span>
                )}
                {typeof ep.view_count === "number" && (
                  <span>{t({ ja: "閲覧数", en: "Views" })}: {ep.view_count}</span>
                )}
                <span>
                  {t({ ja: "文字数", en: "Chars" })}: {countChars(ep.body)}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* ---- コメント欄 ---- */}
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

                  {myUserId && c.user_id === myUserId && (
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
    </div>
  );
}
