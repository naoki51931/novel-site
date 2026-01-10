import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import TagChipLink from "../components/TagChipLink.jsx";
import SupportPanel from "../components/SupportPanel.jsx";
import { useI18n } from "../lib/i18n";

const API_BASE = "";
const FREE_READING_SCHEDULE = {
  ja: "無料開放時間: 平日17:00-19:00 / 土日祝14:00-19:00（JST）",
  en: "Free reading hours: Weekdays 17:00-19:00 / Weekends & holidays 14:00-19:00 (JST)",
};

export default function EpisodeDetail() {
  const { id } = useParams(); // episode_id
  const navigate = useNavigate();
  const { t, lang } = useI18n();

  const isXInAppBrowser =
    typeof navigator !== "undefined" && /Twitter/i.test(navigator.userAgent);

  const [episode, setEpisode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // ★ いいね / 閲覧数
  const [likeCount, setLikeCount] = useState(0);
  const [isLiked, setIsLiked] = useState(false);

  // ★ 画像モーダル
  const [modalImageUrl, setModalImageUrl] = useState("");
  const isPremiumUser = !!episode?.is_premium_user;
  const isFreeReadingTime = !!episode?.is_free_reading_time;
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

  const handleSubscribe = async () => {
    const token = localStorage.getItem("token");
    try {
      const res = await fetch(API_BASE + "/api/stripe/create-checkout-session", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({}),
      });
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
        const res = await fetch(API_BASE + "/api/episodes/" + id, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) {
          throw new Error(
            t(
              { ja: "エピソードの取得に失敗しました ({{status}})", en: "Failed to load episode ({{status}})" },
              { status: res.status }
            )
          );
        }

        const data = await res.json();
        setEpisode(data);

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
          err.message || t({ ja: "エピソードの取得中にエラーが発生しました", en: "An error occurred while loading the episode." })
        );
      } finally {
        setLoading(false);
      }
    };

    fetchEpisode();
  }, [id]);

  // ★ いいねトグル
  const handleToggleLike = async () => {
    const token = localStorage.getItem("token");
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
        setLikeCount((prev) => prev + (isLiked ? -1 : 1));
      }
      setIsLiked((prev) => !prev);
    } catch (e) {
      console.error(e);
      alert(
        e.message || t({ ja: "いいね操作中にエラーが発生しました", en: "An error occurred while liking." })
      );
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

  const tags = Array.isArray(episode.tags) ? episode.tags : [];
  const illusts = Array.isArray(episode.illusts) ? episode.illusts : [];

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString(lang === "en" ? "en-US" : "ja-JP");
  };

  const titleStartsWithEpisodePrefix = (title) => {
    if (typeof title !== "string") return false;
    return /^\s*第\s*(?:[0-9０-９]+|[一二三四五六七八九十百千万]+)\s*話/.test(title);
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

  const openModal = (url) => {
    if (!url) return;
    setModalImageUrl(url);
  };

  const closeModal = () => {
    setModalImageUrl("");
  };

  const buildBodySegments = (text, illustList) => {
    const segments = [];
    const tagToIllust = new Map();
    const usedTags = new Set();
    for (const ill of illustList) {
      if (ill.illust_tag) {
        tagToIllust.set(ill.illust_tag, ill);
      }
    }

    const regex = /\[\[illust:(\d{8})\]\]/g;
    let lastIndex = 0;
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        segments.push({ type: "text", text: text.slice(lastIndex, match.index) });
      }
      const tag = `illust:${match[1]}`;
      const illust = tagToIllust.get(tag);
      if (illust) {
        usedTags.add(tag);
      }
      segments.push({ type: "illust", tag, illust });
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < text.length) {
      segments.push({ type: "text", text: text.slice(lastIndex) });
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
          {tags.map((t) => (
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
        <div style={{ margin: "12px 0" }}>
          <p style={{ marginBottom: 4 }}>{t({ ja: "表紙:", en: "Cover:" })}</p>
          <img
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
          return (
            <div
              key={`illust-${segment.illust.id ?? segment.tag}-${index}`}
              style={{
                margin: "12px 0",
                textAlign: "center",
              }}
            >
              <img
                src={API_BASE + segment.illust.image_url}
                alt={segment.illust.caption || t({ ja: "挿絵", en: "Illustration" })}
                style={{
                  maxWidth: "100%",
                  maxHeight: "70vh",
                  objectFit: "contain",
                  borderRadius: 6,
                  cursor: "pointer",
                  boxShadow: "0 2px 6px rgba(0,0,0,0.2)",
                }}
                onClick={() =>
                  openModal(API_BASE + segment.illust.image_url)
                }
              />
              {segment.illust.caption && (
                <div
                  style={{
                    marginTop: 6,
                    fontSize: 12,
                    color: "#555",
                    wordBreak: "break-word",
                  }}
                >
                  {segment.illust.caption}
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
