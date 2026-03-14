import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";

const API_BASE = getApiBase();

function TinyBarChart({ rows }) {
  const maxViews = useMemo(
    () => Math.max(1, ...rows.map((row) => Number(row.views || 0))),
    [rows]
  );
  return (
    <div style={{ display: "grid", gap: 6 }}>
      {rows.map((row) => {
        const views = Number(row.views || 0);
        const width = Math.max(2, Math.round((views / maxViews) * 100));
        return (
          <div key={row.date} style={{ display: "grid", gridTemplateColumns: "96px 1fr 64px", alignItems: "center", gap: 8 }}>
            <div style={{ fontSize: 12, color: "#666" }}>{row.date}</div>
            <div style={{ height: 10, background: "#f3f4f6", borderRadius: 999 }}>
              <div style={{ width: `${width}%`, height: "100%", background: "#2563eb", borderRadius: 999 }} />
            </div>
            <div style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{views}</div>
          </div>
        );
      })}
    </div>
  );
}

export default function AuthorDashboard() {
  const { t } = useI18n();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [selectedNovel, setSelectedNovel] = useState(null);
  const [selectedDays, setSelectedDays] = useState(30);
  const [seriesLoading, setSeriesLoading] = useState(false);
  const [seriesError, setSeriesError] = useState("");
  const [seriesData, setSeriesData] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      window.location.href = "/login";
      return;
    }
    const run = async () => {
      try {
        setLoading(true);
        setError("");
        const meRes = await fetch(`${API_BASE}/api/users/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const meData = await meRes.json().catch(() => ({}));
        if (!meRes.ok) {
          throw new Error(meData.detail || t({ ja: "ユーザー情報の取得に失敗しました", en: "Failed to load profile." }));
        }
        if (!meData?.is_premium) {
          throw new Error(
            t({
              ja: "作者ダッシュボードはプレミアム会員限定です。",
              en: "Author dashboard is available for premium members only.",
            })
          );
        }
        const res = await fetch(`${API_BASE}/api/author/dashboard`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const json = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(json.detail || t({ ja: "作者ダッシュボードの取得に失敗しました", en: "Failed to load author dashboard." }));
        }
        setData(json);
      } catch (e) {
        setError(e.message || t({ ja: "読み込み中にエラーが発生しました", en: "Failed to load." }));
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [t]);

  const loadSeries = async (novel, days) => {
    const token = localStorage.getItem("token");
    if (!token || !novel?.novel_id) return;
    try {
      setSeriesLoading(true);
      setSeriesError("");
      setSelectedNovel(novel);
      const res = await fetch(
        `${API_BASE}/api/author/dashboard/novels/${novel.novel_id}/daily?days=${days}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(json.detail || t({ ja: "PV推移の取得に失敗しました", en: "Failed to load daily metrics." }));
      }
      setSeriesData(json);
    } catch (e) {
      setSeriesError(e.message || t({ ja: "PV推移の取得に失敗しました", en: "Failed to load daily metrics." }));
      setSeriesData(null);
    } finally {
      setSeriesLoading(false);
    }
  };

  const summary = data?.summary || {};
  const novels = Array.isArray(data?.novels) ? data.novels : [];

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/mypage">{t({ ja: "← マイページへ戻る", en: "← Back to My Page" })}</Link>
      </div>
      <h2>{t({ ja: "作者ダッシュボード", en: "Author Dashboard" })}</h2>

      {loading && <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}

      {!loading && !error && (
        <>
          <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 10 }}>
            <div className="card"><strong>{t({ ja: "作品数", en: "Novels" })}</strong><div>{summary.novel_count || 0}</div></div>
            <div className="card"><strong>{t({ ja: "総PV", en: "Total Views" })}</strong><div>{summary.total_views || 0}</div></div>
            <div className="card"><strong>{t({ ja: "総いいね", en: "Total Likes" })}</strong><div>{summary.total_likes || 0}</div></div>
            <div className="card"><strong>{t({ ja: "総お気に入り", en: "Total Favorites" })}</strong><div>{summary.total_favorites || 0}</div></div>
            <div className="card"><strong>{t({ ja: "総エピソード", en: "Total Episodes" })}</strong><div>{summary.total_episodes || 0}</div></div>
          </div>

          <div style={{ marginTop: 18, overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>{t({ ja: "タイトル", en: "Title" })}</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>{t({ ja: "状態", en: "Status" })}</th>
                  <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>{t({ ja: "話数", en: "Episodes" })}</th>
                  <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>PV</th>
                  <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>{t({ ja: "いいね", en: "Likes" })}</th>
                  <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 }}>{t({ ja: "お気に入り", en: "Favorites" })}</th>
                  <th style={{ textAlign: "center", borderBottom: "1px solid #ddd", padding: 8 }}>{t({ ja: "詳細", en: "Detail" })}</th>
                </tr>
              </thead>
              <tbody>
                {novels.length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ padding: 10, color: "#666" }}>{t({ ja: "作品がありません", en: "No novels yet." })}</td>
                  </tr>
                )}
                {novels.map((novel) => (
                  <tr key={novel.novel_id}>
                    <td style={{ borderBottom: "1px solid #eee", padding: 8 }}>{novel.title}</td>
                    <td style={{ borderBottom: "1px solid #eee", padding: 8 }}>{novel.status}</td>
                    <td style={{ borderBottom: "1px solid #eee", padding: 8, textAlign: "right" }}>{novel.episode_count}</td>
                    <td style={{ borderBottom: "1px solid #eee", padding: 8, textAlign: "right" }}>{novel.view_count}</td>
                    <td style={{ borderBottom: "1px solid #eee", padding: 8, textAlign: "right" }}>{novel.like_count}</td>
                    <td style={{ borderBottom: "1px solid #eee", padding: 8, textAlign: "right" }}>{novel.favorite_count}</td>
                    <td style={{ borderBottom: "1px solid #eee", padding: 8, textAlign: "center" }}>
                      <button className="btn btn-border" onClick={() => loadSeries(novel, selectedDays)}>
                        {t({ ja: "詳細", en: "Detail" })}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: 18, border: "1px solid #ddd", borderRadius: 8, padding: 12, background: "#fff" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
              <strong>{t({ ja: "PV推移", en: "View Trend" })}</strong>
              <span style={{ color: "#666" }}>{selectedNovel ? selectedNovel.title : t({ ja: "作品を選択してください", en: "Select a novel" })}</span>
              <select
                value={selectedDays}
                onChange={(e) => {
                  const nextDays = Number(e.target.value);
                  setSelectedDays(nextDays);
                  if (selectedNovel) loadSeries(selectedNovel, nextDays);
                }}
              >
                <option value={7}>7{t({ ja: "日", en: "d" })}</option>
                <option value={30}>30{t({ ja: "日", en: "d" })}</option>
                <option value={90}>90{t({ ja: "日", en: "d" })}</option>
              </select>
            </div>
            {seriesLoading && <p>{t({ ja: "PV推移を読み込み中...", en: "Loading trend..." })}</p>}
            {seriesError && <p style={{ color: "red" }}>{seriesError}</p>}
            {!seriesLoading && !seriesError && seriesData && (
              <TinyBarChart rows={Array.isArray(seriesData.series) ? seriesData.series : []} />
            )}
            {!seriesLoading && !seriesError && !seriesData && (
              <p style={{ color: "#666" }}>{t({ ja: "右の詳細ボタンから表示できます", en: "Click Detail to view trend." })}</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
