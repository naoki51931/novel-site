// frontend/src/pages/Home.jsx
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import TagChipLink from "../components/TagChipLink.jsx";

const API_BASE = "";

export default function Home({ query = "" }) {
  const location = useLocation();
  const [novels, setNovels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchNovels = async () => {
      try {
        setLoading(true);
        setError("");

        const params = new URLSearchParams(location.search);
        const urlQuery = (params.get("q") ?? "").trim();
        const urlTag = (params.get("tag") ?? "").trim();
        const effectiveQuery = urlQuery || (query ?? "").trim();

        let url = `${API_BASE}/api/public/novels`;
        const apiParams = new URLSearchParams();
        if (effectiveQuery) apiParams.set("q", effectiveQuery);
        if (urlTag) apiParams.set("tag", urlTag);
        const qs = apiParams.toString();
        if (qs) url += `?${qs}`;

        const res = await fetch(url);
        if (!res.ok) throw new Error("小説一覧の取得に失敗しました");

        const data = await res.json();

        const sorted = (data || []).slice().sort((a, b) => {
          const ad = a.created_at ? new Date(a.created_at).getTime() : 0;
          const bd = b.created_at ? new Date(b.created_at).getTime() : 0;
          return bd - ad;
        });

        setNovels(sorted);
      } catch (err) {
        console.error(err);
        setError(err.message || "エラーが発生しました");
      } finally {
        setLoading(false);
      }
    };

    fetchNovels();
  }, [query, location.search]); // ← 検索語 or URL が変わるたびに再取得

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString("ja-JP");
  };

  const shorten = (text, max = 120) => {
    if (!text) return "";
    if (text.length <= max) return text;
    return text.slice(0, max) + "…";
  };

  if (loading) return <p>読み込み中...</p>;

  return (
    <div>
      {error && (
        <p style={{ color: "red", marginTop: 8, marginBottom: 8 }}>{error}</p>
      )}

      {novels.length === 0 && <p>小説が見つかりません。</p>}

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
              {shorten(novel.description, 120) || "説明がありません。"}
            </p>

            <div style={{ fontSize: 12, color: "var(--novel-card-meta)", marginBottom: 8 }}>
              <div>
                作者:{" "}
                {novel.author_username
                  ? novel.author_username
                  : novel.author_id
                  ? `ユーザーID: ${novel.author_id}`
                  : "不明"}
              </div>
              <div>作成日時: {formatDateTime(novel.created_at)}</div>
            </div>

            {Array.isArray(novel.tag_names) && novel.tag_names.length > 0 && (
              <div className="tag-chip-row" style={{ marginBottom: 10 }}>
                {novel.tag_names.map((name) => (
                  <TagChipLink key={name} name={name} />
                ))}
              </div>
            )}

            <div style={{ textAlign: "right" }}>
              <Link to={`/novels/${novel.id}`} className="btn btn-border">
                続きを読む
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
