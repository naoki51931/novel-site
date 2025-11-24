import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function EpisodeDetail() {
  const { id } = useParams(); // episode_id
  const navigate = useNavigate();
  const [episode, setEpisode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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

  // ★ タグ配列を安全に用意（undefined / null 対策）
  const tags = Array.isArray(episode.tags) ? episode.tags : [];

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString("ja-JP");
  };

  return (
    <div>
      <button className="btn btn-border" onClick={() => navigate(-1)}>
        ← 戻る
      </button>

      <h2 style={{ marginTop: 12 }}>
        第{episode.number || episode.episode_number}話 {episode.title}
      </h2>

      {/* ★ タグ表示 */}
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
    </div>
  );
}

