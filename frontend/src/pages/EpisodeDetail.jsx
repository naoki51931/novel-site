import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";

const API_BASE = "";

// 画像パスを安全に絶対 URL にするヘルパー
function toImageUrl(path) {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (path.startsWith("/")) return path;
  // 先頭スラッシュが無い "static/..." 形式なら "/static/..." にする
  return "/" + path.replace(/^\/+/, "");
}

export default function EpisodeDetail() {
  const { id } = useParams(); // episode_id
  const navigate = useNavigate();
  const [episode, setEpisode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // 画像プレビュー用 state
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);

  const openPreview = (url) => {
    setPreviewUrl(url);
    setPreviewOpen(true);
  };

  const closePreview = () => {
    setPreviewOpen(false);
    setPreviewUrl("");
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
        console.log("👀 EpisodeDetail /api/episodes/" + id, data);
        setEpisode(data);
      } catch (err) {
        console.error(err);
        setError(err.message || "エピソードの取得中にエラーが発生しました");
      } finally {
        setLoading(false);
      }
    };

    fetchEpisode();
  }, [id]);

  if (loading) {
    return <div>読み込み中...</div>;
  }

  if (error) {
    return (
      <div>
        <p style={{ color: "red" }}>{error}</p>
        <button className="btn btn-border" onClick={() => navigate(-1)}>
          戻る
        </button>
      </div>
    );
  }

  if (!episode) {
    return (
      <div>
        <p>エピソードが見つかりませんでした。</p>
        <button className="btn btn-border" onClick={() => navigate(-1)}>
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

  const coverUrl = toImageUrl(episode.cover_image_url);

  return (
    <div>
      <button className="btn btn-border" onClick={() => navigate(-1)}>
        ← 戻る
      </button>

      <h2 style={{ marginTop: 12 }}>
        第{episode.number || episode.episode_number}話 {episode.title}
      </h2>

      {/* デバッグ用: 返ってきてる JSON を確認できるようにしておく */}
      <details style={{ margin: "8px 0", fontSize: "0.8rem" }}>
        <summary>APIレスポンス（デバッグ用）</summary>
        <pre style={{ whiteSpace: "pre-wrap" }}>
{JSON.stringify(episode, null, 2)}
        </pre>
      </details>

      {/* タグ表示 */}
      {tags.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          {tags.map((t) => (
            <span
              key={t.id}
              style={{
                display: "inline-block",
                marginRight: 4,
                padding: "2px 8px",
                borderRadius: 12,
                border: "1px solid #ccc",
                fontSize: "0.85rem",
              }}
            >
              #{t.name}
            </span>
          ))}
        </div>
      )}

      <p style={{ color: "#666", marginBottom: 4 }}>小説ID: {episode.novel_id}</p>

      {episode.created_at && (
        <p style={{ color: "#999", fontSize: "0.9rem", marginBottom: 8 }}>
          作成日時: {formatDateTime(episode.created_at)}
        </p>
      )}

      {/* 表紙画像（クリックで拡大） */}
      {coverUrl && (
        <div style={{ marginTop: 16, marginBottom: 16 }}>
          <p style={{ marginBottom: 4 }}>表紙</p>
          <img
            src={coverUrl}
            alt="表紙画像"
            style={{
              maxWidth: "220px",
              borderRadius: 8,
              cursor: "pointer",
              boxShadow: "0 0 6px rgba(0,0,0,0.2)",
            }}
            onClick={() => openPreview(coverUrl)}
          />
        </div>
      )}

      {/* 挿絵一覧（クリックで拡大） */}
      {illusts.length > 0 && (
        <div style={{ marginTop: 16, marginBottom: 16 }}>
          <p style={{ marginBottom: 4 }}>挿絵</p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))",
              gap: 12,
            }}
          >
            {illusts.map((ill) => {
              const url = toImageUrl(ill.image_url);
              return (
                <div
                  key={ill.id ?? ill.image_url}
                  style={{
                    textAlign: "center",
                    padding: 6,
                    borderRadius: 8,
                    border: "1px solid #eee",
                  }}
                >
                  <img
                    src={url}
                    alt={ill.caption || "挿絵"}
                    style={{
                      maxWidth: "100%",
                      borderRadius: 6,
                      cursor: "pointer",
                    }}
                    onClick={() => openPreview(url)}
                  />
                  {ill.caption && (
                    <div
                      style={{
                        marginTop: 4,
                        fontSize: 12,
                        color: "#555",
                        wordBreak: "break-all",
                      }}
                    >
                      {ill.caption}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <hr />

      <div
        style={{
          whiteSpace: "pre-wrap",
          lineHeight: 1.8,
          marginTop: 12,
        }}
      >
        {episode.body}
      </div>

      {episode.is_premium_user ? (
        <div
          style={{
            marginTop: 16,
            padding: 12,
            border: "1px solid #0a0",
            background: "#efe",
            borderRadius: 6,
          }}
        >
          <p
            style={{
              marginBottom: 0,
              color: "#060",
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

      <div style={{ marginTop: 24 }}>
        <Link to={"/novels/" + episode.novel_id} className="btn btn-border">
          小説詳細へ戻る
        </Link>
      </div>

      {/* 画像プレビューモーダル */}
      {previewOpen && (
        <div
          onClick={closePreview}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.8)",
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
            }}
          >
            <img
              src={previewUrl}
              alt="画像プレビュー"
              style={{
                maxWidth: "100%",
                maxHeight: "90vh",
                borderRadius: 8,
                boxShadow: "0 0 18px rgba(0,0,0,0.6)",
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
