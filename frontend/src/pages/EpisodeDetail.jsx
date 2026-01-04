import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import TagChipLink from "../components/TagChipLink.jsx";
import SupportPanel from "../components/SupportPanel.jsx";

const API_BASE = "";

export default function EpisodeDetail() {
  const { id } = useParams(); // episode_id
  const navigate = useNavigate();

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
    const text = displayTitle ? `${displayTitle}` : "エピソードを読みました";
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
        throw new Error("決済セッションの作成に失敗しました");
      }
      const data = await res.json();
      if (data.url) {
        const returnTo = window.location.pathname + window.location.search;
        sessionStorage.setItem("stripe_return_to", returnTo);
        window.location.href = data.url;
      } else {
        alert("決済URLを取得できませんでした。");
      }
    } catch (e) {
      console.error(e);
      alert("決済処理中にエラーが発生しました");
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
          throw new Error("エピソードの取得に失敗しました (" + res.status + ")");
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
        setError(err.message || "エピソードの取得中にエラーが発生しました");
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
      alert("いいねするにはログインが必要です。");
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
        throw new Error(data.detail || "いいね操作に失敗しました");
      }

      if (typeof data.like_count === "number") {
        setLikeCount(data.like_count);
      } else {
        setLikeCount((prev) => prev + (isLiked ? -1 : 1));
      }
      setIsLiked((prev) => !prev);
    } catch (e) {
      console.error(e);
      alert(e.message || "いいね操作中にエラーが発生しました");
    }
  };

  if (loading) {
    return <div>読み込み中...</div>;
  }

  if (error) {
    return (
      <div>
        <p style={{ color: "red" }}>{error}</p>
        <button className="btn btn-border" onClick={handleBackToNovel}>
          戻る
        </button>
      </div>
    );
  }

  if (!episode) {
    return (
      <div>
        <p>エピソードが見つかりませんでした。</p>
        <button className="btn btn-border" onClick={handleBackToNovel}>
          戻る
        </button>
      </div>
    );
  }

  const tags = Array.isArray(episode.tags) ? episode.tags : [];
  const illusts = Array.isArray(episode.illusts) ? episode.illusts : [];

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString("ja-JP");
  };

  const titleStartsWithEpisodePrefix = (title) => {
    if (typeof title !== "string") return false;
    return /^\s*第\s*(?:[0-9０-９]+|[一二三四五六七八九十百千万]+)\s*話/.test(title);
  };

  const formatEpisodeDisplayTitle = (episodeNumber, title) => {
    const cleanTitle = typeof title === "string" ? title.trim() : "";
    if (cleanTitle && titleStartsWithEpisodePrefix(cleanTitle)) return cleanTitle;
    if (episodeNumber == null || episodeNumber === "") return cleanTitle;
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
    ? `前のエピソードへ：${prevEpisodeTitle}`
    : "前のエピソードへ";
  const nextEpisodeLabel = nextEpisodeTitle
    ? `次のエピソードへ：${nextEpisodeTitle}`
    : "次のエピソードへ";

  return (
    <div>
      <button className="btn btn-border" onClick={handleBackToNovel}>
        ← 戻る
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
            作者:{" "}
            <Link
              className="user-link"
              to={`/users/${encodeURIComponent(episode.author_username)}`}
            >
              {episode.author_username}
            </Link>
          </span>
        ) : (
          <span>小説ID: {episode.novel_id}</span>
        )}
        {episode.created_at && (
          <span>作成日時: {formatDateTime(episode.created_at)}</span>
        )}
        {typeof episode.view_count === "number" && (
          <span>閲覧数: {episode.view_count}</span>
        )}
	<Link
          to={`/ai-novel?episode_id=${episode.id}`}
          className="btn btn-border"
        >
          AIで続きを生成
        </Link>

        <button
          type="button"
          className="btn btn-border"
          onClick={handleShareToX}
        >
          Xで共有
        </button>

        <button
          type="button"
          className="btn btn-border"
          onClick={handleToggleLike}
          style={{ marginLeft: "auto" }}
        >
          {isLiked ? "♥ いいね済み" : "♡ いいね"} ({likeCount})
        </button>
      </div>

      {episode?.author_id && (
        <SupportPanel
          authorUserId={episode.author_id}
          novelId={episode.novel_id}
          episodeId={episode.id}
          authorName={episode.author_username || "作者"}
        />
      )}

      {/* 表紙画像 */}
      {episode.cover_image_url && (
        <div style={{ margin: "12px 0" }}>
          <p style={{ marginBottom: 4 }}>表紙:</p>
          <img
            src={API_BASE + episode.cover_image_url}
            alt="表紙画像"
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
                alt={segment.illust.caption || "挿絵"}
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
      {episode.is_premium_user ? (
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
            ★ あなたは課金済みユーザーです（PREMIUM）
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
            全文を読むには月額1000円のプレミアム購読が必要です。
          </p>
          <button className="btn btn-border" onClick={handleSubscribe}>
            課金して続きを読む
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
          小説詳細へ戻る
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
              alt="拡大画像"
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
              閉じる
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
