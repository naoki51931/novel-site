import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";
import { formatDateTimeInUserTimeZone } from "../lib/timezone";

const API_BASE = getApiBase();

type ScheduledEpisode = {
  episode_id: number | string;
  novel_title?: string | null;
  episode_title?: string | null;
  scheduled_publish_at?: string | null;
  status?: string | null;
};

export default function ScheduledEpisodes() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [items, setItems] = useState<ScheduledEpisode[]>([]);

  const loadItems = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      navigate("/login");
      return;
    }
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
            ja: "予約投稿機能はプレミアム会員限定です。",
            en: "Scheduled publishing is available for premium members only.",
          })
        );
      }
      const res = await fetch(`${API_BASE}/api/me/scheduled-episodes`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(json.detail || t({ ja: "予約投稿一覧の取得に失敗しました", en: "Failed to load scheduled episodes." }));
      }
      setItems(Array.isArray(json.items) ? json.items : []);
    } catch (e) {
      setError(
        getErrorMessage(e, t({ ja: "予約投稿一覧の取得に失敗しました", en: "Failed to load scheduled episodes." }))
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleUnschedule = async (episodeId: ScheduledEpisode["episode_id"]) => {
    const token = localStorage.getItem("token");
    if (!token) {
      navigate("/login");
      return;
    }
    if (!window.confirm(t({ ja: "この予約を解除しますか？", en: "Cancel this schedule?" }))) return;
    const res = await fetch(`${API_BASE}/api/episodes/${episodeId}/unschedule`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(json.detail || t({ ja: "予約解除に失敗しました", en: "Failed to unschedule." }));
      return;
    }
    setItems((prev: ScheduledEpisode[]) => prev.filter((item) => item.episode_id !== episodeId));
  };

  return (
    <div style={{ maxWidth: 980, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/mypage">{t({ ja: "← マイページへ戻る", en: "← Back to My Page" })}</Link>
      </div>
      <h2>{t({ ja: "予約投稿一覧", en: "Scheduled Episodes" })}</h2>
      {loading && <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}
      {!loading && !error && (
        <div style={{ marginTop: 12, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>{t({ ja: "作品名", en: "Novel" })}</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>{t({ ja: "タイトル", en: "Episode" })}</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>{t({ ja: "予約日時", en: "Scheduled At" })}</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>{t({ ja: "状態", en: "Status" })}</th>
                <th style={{ textAlign: "center", padding: 8, borderBottom: "1px solid #ddd" }}>{t({ ja: "操作", en: "Actions" })}</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ padding: 12, color: "#666" }}>
                    {t({ ja: "予約中のエピソードはありません", en: "No scheduled episodes." })}
                  </td>
                </tr>
              )}
              {items.map((item) => (
                <tr key={item.episode_id}>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>{item.novel_title}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>{item.episode_title}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>
                    {formatDateTimeInUserTimeZone(item.scheduled_publish_at, lang === "en" ? "en-US" : "ja-JP") || "-"}
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>{item.status}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee", textAlign: "center", whiteSpace: "nowrap" }}>
                    <Link className="btn btn-border" to={`/episodes/${item.episode_id}/edit`}>
                      {t({ ja: "編集", en: "Edit" })}
                    </Link>
                    <button className="btn btn-border" style={{ marginLeft: 8 }} onClick={() => handleUnschedule(item.episode_id)}>
                      {t({ ja: "予約解除", en: "Unschedule" })}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
