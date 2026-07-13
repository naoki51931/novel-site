import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import TagChipLink from "../components/TagChipLink";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";
import { formatDateTimeInUserTimeZone, setUserTimeZone } from "../lib/timezone";
import {
  MYPAGE_SHOW_R18_STORAGE_KEY,
  R18_DISPLAY_CHANGE_EVENT,
  readShowR18Setting,
} from "../lib/r18Display";

const API_BASE = getApiBase();
const ANDROID_APP_FILE = "/static/app_downloads/novelsite-android.apk";
const IPHONE_APP_FILE = "/static/app_downloads/novelsite-iphone.ipa";
const MOBILE_APP_UPDATED_AT = "2026/02/12";
const FAVORITE_SUMMARY_MAX_CHARS = 500;
const AI_JOBS_HISTORY_LIMIT = 200;

type TagItem = {
  id?: number | string | null;
  name?: string | null;
};

type NovelItem = {
  id: number | string;
  title?: string | null;
  description?: string | null;
  created_at?: string | null;
  age_limit?: string | null;
  cover_image_url?: string | null;
  tags?: TagItem[] | null;
  view_count?: number | null;
  like_count?: number | null;
  favorite_count?: number | null;
  total_char_count?: number | null;
};

type ViewHistoryNovel = {
  target_id: number | string;
  viewed_at?: string | null;
  view_count?: number | null;
  site_key?: string | null;
  title?: string | null;
  author_username?: string | null;
  age_limit?: string | null;
};

type ViewHistoryResponse = {
  items?: ViewHistoryNovel[] | null;
  total?: number | null;
  limit?: number | null;
  offset?: number | null;
  detail?: string | null;
};

type AiChatFavorite = {
  id: number | string;
  name?: string | null;
  author_username?: string | null;
  image_url?: string | null;
  personality?: string | null;
  like_count?: number | null;
  favorite_count?: number | null;
  created_at?: string | null;
  is_r18?: boolean | null;
};

type AnalyticsDay = {
  date: string;
  views?: number | null;
  likes?: number | null;
  favorites?: number | null;
};

type AnalyticsNovel = {
  id: number | string;
  title?: string | null;
  age_limit?: string | null;
  views?: number | null;
  likes?: number | null;
  favorites?: number | null;
};

type AnalyticsData = {
  novels?: AnalyticsNovel[] | null;
  days?: AnalyticsDay[] | null;
  totals?: {
    views?: number | null;
    likes?: number | null;
    favorites?: number | null;
  } | null;
};

type AiJob = {
  id: number | string;
  status?: string | null;
  job_type?: string | null;
  created_at?: string | null;
};

export default function Mypage() {
  const { t, lang } = useI18n();
  const [novels, setNovels] = useState<NovelItem[]>([]);
  const [favorites, setFavorites] = useState<NovelItem[]>([]);
  const [aiChatFavorites, setAiChatFavorites] = useState<AiChatFavorite[]>([]);
  const [isPremium, setIsPremium] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [analyticsMonth, setAnalyticsMonth] = useState(() => {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    return `${now.getFullYear()}-${month}`;
  });
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState("");
  const [selectedNovelId, setSelectedNovelId] = useState("");
  const [selectedNovelAnalytics, setSelectedNovelAnalytics] = useState<AnalyticsData | null>(null);
  const [novelAnalyticsLoading, setNovelAnalyticsLoading] = useState(false);
  const [novelAnalyticsError, setNovelAnalyticsError] = useState("");
  const [aiJobs, setAiJobs] = useState<AiJob[]>([]);
  const [aiJobsLoading, setAiJobsLoading] = useState(false);
  const [aiJobsError, setAiJobsError] = useState("");
  const [aiJobsSelected, setAiJobsSelected] = useState<Set<AiJob["id"]>>(() => new Set());
  const [aiJobsPage, setAiJobsPage] = useState(1);
  const [aiJobsFilter, setAiJobsFilter] = useState("all");
  const [username, setUsername] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("username") || "";
  });
  const [showR18, setShowR18] = useState(() => readShowR18Setting());
  const [androidAppReady, setAndroidAppReady] = useState(false);
  const [iphoneAppReady, setIphoneAppReady] = useState(false);
  const [emailAddressInvalid, setEmailAddressInvalid] = useState(false);
  const [profileEmail, setProfileEmail] = useState("");
  const [viewHistoryItems, setViewHistoryItems] = useState<ViewHistoryNovel[]>([]);
  const [viewHistoryLoading, setViewHistoryLoading] = useState(false);
  const [viewHistoryError, setViewHistoryError] = useState("");
  const [viewHistoryLimit, setViewHistoryLimit] = useState<10 | 20>(10);
  const navigate = useNavigate();

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const siteKey =
    typeof document !== "undefined"
      ? (document.documentElement?.dataset?.siteKey || "main").toLowerCase()
      : "main";
  const hideAppDownloads = siteKey === "romance" || siteKey === "history";
  const formatErrorDetail = (detail: unknown, fallback: string) => {
    if (typeof detail === "string" && detail.trim()) return detail;
    if (detail) return JSON.stringify(detail);
    return fallback;
  };
  const truncateFavoriteSummary = (text: string | null | undefined) => {
    const value = String(text || "");
    if (value.length <= FAVORITE_SUMMARY_MAX_CHARS) return value;
    return `${value.slice(0, FAVORITE_SUMMARY_MAX_CHARS)}...`;
  };

  useEffect(() => {
    if (!token) {
      navigate("/login");
      return;
    }

    const fetchMine = async () => {
      try {
        setLoading(true);
        setError("");

        const params = new URLSearchParams();
        params.set("mine", "true");
        if (lang) params.set("lang", lang);

        const res = await fetch(`${API_BASE}/api/novels?${params.toString()}`, {
          headers: {
            Authorization: "Bearer " + token,
          },
        });

        const data = await res.json().catch(() => []);

        if (!res.ok) {
          throw new Error(
            data.detail || t({ ja: "マイページの取得に失敗しました", en: "Failed to load My Page." })
          );
        }

        const sorted = (data || []).slice().sort((a: NovelItem, b: NovelItem) => {
          const ad = a.created_at ? new Date(a.created_at).getTime() : 0;
          const bd = b.created_at ? new Date(b.created_at).getTime() : 0;
          return bd - ad;
        });
        setNovels(sorted);
      } catch (err) {
        console.error(err);
        setError(
          getErrorMessage(
            err,
            t({ ja: "マイページの取得中にエラーが発生しました", en: "An error occurred while loading My Page." })
          )
        );
      } finally {
        setLoading(false);
      }
    };

    fetchMine();
  }, [lang, navigate, token]);

  const loadAiJobs = async () => {
    if (!token) return;
    try {
      setAiJobsLoading(true);
      setAiJobsError("");
      const res = await fetch(`${API_BASE}/api/ai/jobs/me?limit=${AI_JOBS_HISTORY_LIMIT}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => []);
      if (!res.ok) {
        throw new Error(
          formatErrorDetail(
            data.detail,
            t({ ja: "AIジョブの取得に失敗しました", en: "Failed to load AI jobs." })
          )
        );
      }
      const nextJobs = Array.isArray(data) ? data : [];
      setAiJobs(nextJobs);
      setAiJobsPage(1);
      } catch (err) {
        console.error(err);
        setAiJobsError(
          getErrorMessage(err, t({ ja: "AIジョブの取得中にエラーが発生しました", en: "Failed to load AI jobs." }))
        );
      } finally {
        setAiJobsLoading(false);
    }
  };

  useEffect(() => {
    loadAiJobs();
  }, [token]);

  useEffect(() => {
    if (hideAppDownloads) {
      setAndroidAppReady(false);
      setIphoneAppReady(false);
      return;
    }
    const checkFile = async (url: string, setter: (value: boolean) => void) => {
      try {
        const res = await fetch(url, { method: "HEAD" });
        setter(res.ok);
      } catch {
        setter(false);
      }
    };
    checkFile(ANDROID_APP_FILE, setAndroidAppReady);
    checkFile(IPHONE_APP_FILE, setIphoneAppReady);
  }, [hideAppDownloads]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    localStorage.setItem(MYPAGE_SHOW_R18_STORAGE_KEY, showR18 ? "1" : "0");
    window.dispatchEvent(new Event(R18_DISPLAY_CHANGE_EVENT));
    return undefined;
  }, [showR18]);

  const isR18Novel = (novel: { age_limit?: string | null } | null | undefined) =>
    String(novel?.age_limit || "all").toLowerCase() === "r18";
  const novelsVisible = showR18 ? novels : novels.filter((n) => !isR18Novel(n));
  const favoritesVisible = showR18 ? favorites : favorites.filter((n) => !isR18Novel(n));
  const aiChatFavoritesVisible = showR18
    ? aiChatFavorites
    : aiChatFavorites.filter((item) => !item?.is_r18);
  const viewHistoryVisible = showR18
    ? viewHistoryItems
    : viewHistoryItems.filter((item) => String(item.age_limit || "all").toLowerCase() !== "r18");

  useEffect(() => {
    if (!token) return;
    const loadViewHistory = async () => {
      try {
        setViewHistoryLoading(true);
        setViewHistoryError("");
        const params = new URLSearchParams();
        params.set("limit", String(viewHistoryLimit));
        const res = await fetch(`${API_BASE}/api/me/view-history/novels?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data: ViewHistoryResponse = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(
            data.detail
            || t({ ja: "閲覧履歴の取得に失敗しました", en: "Failed to load view history." })
          );
        }
        setViewHistoryItems(Array.isArray(data.items) ? data.items : []);
      } catch (err) {
        console.error(err);
        setViewHistoryError(
          getErrorMessage(
            err,
            t({ ja: "閲覧履歴の取得中にエラーが発生しました", en: "An error occurred while loading view history." })
          )
        );
      } finally {
        setViewHistoryLoading(false);
      }
    };
    loadViewHistory();
  }, [t, token, viewHistoryLimit]);

  const aiJobsFiltered = aiJobs.filter((job) => {
    if (aiJobsFilter === "all") return true;
    if (aiJobsFilter === "running") {
      return job.status === "pending" || job.status === "running";
    }
    return job.status === aiJobsFilter;
  });
  const aiJobsPageSize = 5;
  const aiJobsTotalPages = Math.max(1, Math.ceil(aiJobsFiltered.length / aiJobsPageSize));
  const aiJobsPageSafe = Math.min(Math.max(aiJobsPage, 1), aiJobsTotalPages);
  const aiJobsStartIndex = (aiJobsPageSafe - 1) * aiJobsPageSize;
  const aiJobsSlice = aiJobsFiltered.slice(aiJobsStartIndex, aiJobsStartIndex + aiJobsPageSize);

  useEffect(() => {
    if (!token || !analyticsMonth) return;

    const fetchFavoritesAndProfile = async () => {
      try {
        // お気に入り取得
        const favParams = new URLSearchParams();
        if (lang) favParams.set("lang", lang);

        const resFav = await fetch(`${API_BASE}/api/me/favorites?${favParams.toString()}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (resFav.ok) {
          const dataFav = await resFav.json();
          const sortedFav = (dataFav || []).slice().sort((a: NovelItem, b: NovelItem) => {
            const ad = a.created_at ? new Date(a.created_at).getTime() : 0;
            const bd = b.created_at ? new Date(b.created_at).getTime() : 0;
            return bd - ad;
          });
          setFavorites(sortedFav);
        } else {
          console.error("failed to fetch favorites");
        }

        // AIチャットのブックマーク取得
        const resAiChatFav = await fetch(`${API_BASE}/api/me/ai/chat/favorites`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (resAiChatFav.ok) {
          const dataAiChatFav = await resAiChatFav.json();
          const sortedAiChatFav = (dataAiChatFav || []).slice().sort((a: AiChatFavorite, b: AiChatFavorite) => {
            const ad = a.created_at ? new Date(a.created_at).getTime() : 0;
            const bd = b.created_at ? new Date(b.created_at).getTime() : 0;
            return bd - ad;
          });
          setAiChatFavorites(sortedAiChatFav);
        } else {
          console.error("failed to fetch ai chat favorites");
        }

        // プロフィール取得 → プレミアム判定
        const resProfile = await fetch(`${API_BASE}/api/users/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (resProfile.ok) {
          const profile = await resProfile.json();
          setIsPremium(!!profile.is_premium);
          setEmailAddressInvalid(profile.email_address_invalid === true);
          setProfileEmail((profile.email || "").trim());
          if (profile.timezone) setUserTimeZone(profile.timezone);
          if (profile.username) {
            setUsername(profile.username);
            localStorage.setItem("username", profile.username);
          }
        }
      } catch (e) {
        console.error(e);
      }
    };

    fetchFavoritesAndProfile();
  }, [lang, token]);

  useEffect(() => {
    if (showR18) return;
    if (!selectedNovelId) return;
    const list = Array.isArray(analyticsData?.novels) ? analyticsData.novels : [];
        const found = list.find((n: AnalyticsNovel) => String(n?.id) === String(selectedNovelId));
    if (found && isR18Novel(found)) setSelectedNovelId("");
  }, [showR18, selectedNovelId, analyticsData]);

  useEffect(() => {
    if (!token) return;

    const fetchAnalytics = async () => {
      try {
        setAnalyticsLoading(true);
        setAnalyticsError("");
        const res = await fetch(
          `${API_BASE}/api/me/analytics/novels?month=${analyticsMonth}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(
            data.detail || t({ ja: "アクセス解析の取得に失敗しました", en: "Failed to load analytics." })
          );
        }
        setAnalyticsData(data);
      } catch (err) {
        console.error(err);
        setAnalyticsError(
          getErrorMessage(
            err,
            t({ ja: "アクセス解析の取得中にエラーが発生しました", en: "An error occurred while loading analytics." })
          )
        );
      } finally {
        setAnalyticsLoading(false);
      }
    };

    fetchAnalytics();
  }, [analyticsMonth, token, t]);

  useEffect(() => {
    if (!token || !selectedNovelId) {
      setSelectedNovelAnalytics(null);
      setNovelAnalyticsError("");
      setNovelAnalyticsLoading(false);
      return;
    }

    const fetchNovelAnalytics = async () => {
      try {
        setNovelAnalyticsLoading(true);
        setNovelAnalyticsError("");
        const res = await fetch(
          `${API_BASE}/api/me/analytics/novels/${selectedNovelId}?month=${analyticsMonth}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(
            data.detail || t({ ja: "小説別アクセス解析の取得に失敗しました", en: "Failed to load novel analytics." })
          );
        }
        setSelectedNovelAnalytics(data);
      } catch (err) {
        console.error(err);
        setNovelAnalyticsError(
          getErrorMessage(
            err,
            t({
              ja: "小説別アクセス解析の取得中にエラーが発生しました",
              en: "An error occurred while loading novel analytics.",
            })
          )
        );
      } finally {
        setNovelAnalyticsLoading(false);
      }
    };

    fetchNovelAnalytics();
  }, [analyticsMonth, selectedNovelId, token, t]);

  const toggleAiJobSelected = (jobId: AiJob["id"]) => {
    setAiJobsSelected((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  };

  const handleKillSelectedAiJobs = async () => {
    if (!token || aiJobsSelected.size === 0) return;
    const ok = window.confirm(
      t({ ja: "選択したAIジョブを停止します。よろしいですか？", en: "Stop selected AI jobs?" })
    );
    if (!ok) return;
    try {
      setAiJobsLoading(true);
      setAiJobsError("");
      const res = await fetch(`${API_BASE}/api/ai/jobs/kill_selected_me`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ job_ids: Array.from(aiJobsSelected) }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          formatErrorDetail(
            data.detail,
            t({ ja: "AIジョブの停止に失敗しました", en: "Failed to stop AI jobs." })
          )
        );
      }
      setAiJobsSelected(new Set());
      await loadAiJobs();
    } catch (err) {
      console.error(err);
      setAiJobsError(
        getErrorMessage(err, t({ ja: "AIジョブの停止中にエラーが発生しました", en: "Failed to stop AI jobs." }))
      );
    } finally {
      setAiJobsLoading(false);
    }
  };

  const handleKillAllAiJobs = async () => {
    if (!token) return;
    const ok = window.confirm(
      t({ ja: "すべてのAIジョブを停止します。よろしいですか？", en: "Stop all AI jobs?" })
    );
    if (!ok) return;
    try {
      setAiJobsLoading(true);
      setAiJobsError("");
      const res = await fetch(`${API_BASE}/api/ai/jobs/kill_me`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          formatErrorDetail(
            data.detail,
            t({ ja: "AIジョブの停止に失敗しました", en: "Failed to stop AI jobs." })
          )
        );
      }
      setAiJobsSelected(new Set());
      await loadAiJobs();
    } catch (err) {
      console.error(err);
      setAiJobsError(
        getErrorMessage(err, t({ ja: "AIジョブの停止中にエラーが発生しました", en: "Failed to stop AI jobs." }))
      );
    } finally {
      setAiJobsLoading(false);
    }
  };

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">{t({ ja: "← トップに戻る", en: "← Back to Home" })}</Link>
      </div>

      <h2
        style={{
          marginBottom: "1rem",
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        <Link className="user-link" to={`/users/${encodeURIComponent(username)}`}>
          {username || t({ ja: "ユーザー", en: "User" })}
        </Link>{" "}
        {t({ ja: "さんのマイページ", en: "'s My Page" })}
        {isPremium && (
          <span
            style={{
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: "999px",
              backgroundColor: "var(--accent)",
              color: "var(--on-accent)",
              fontSize: 12,
            }}
          >
            PREMIUM
          </span>
        )}
      </h2>

      {emailAddressInvalid && (
        <div
          style={{
            marginBottom: 16,
            padding: "10px 12px",
            border: "1px solid #b3261e",
            borderRadius: 8,
            background: "#fff4f3",
            color: "#7a1812",
            lineHeight: 1.6,
          }}
        >
          {t({
            ja: `登録メールアドレス${profileEmail ? `（${profileEmail}）` : ""}を確認し、アドレス不明の場合はマイページ設定からメールアドレスを変更してください。`,
            en: `Please confirm your registered email${profileEmail ? ` (${profileEmail})` : ""}. If the address is unknown, update it in account settings.`,
          })}{" "}
          <Link to="/mypage/settings">{t({ ja: "マイページ設定へ", en: "Go to settings" })}</Link>
        </div>
      )}

      {/* プレミアム会員セクション */}
      <section style={{ marginBottom: 24 }}>
        <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
          {t({ ja: "プレミアム会員", en: "Premium" })}
        </h3>
        <p style={{ marginBottom: 8, lineHeight: 1.6 }}>
          {t({
            ja: "長文の全文表示などの追加機能を利用するには、プレミアム登録が必要です。",
            en: "Premium is required for extra features like full text display.",
          })}
        </p>

        {!isPremium && (
          <button
            type="button"
            className="btn btn-border"
            onClick={() => navigate("/premium")}
          >
            {t({ ja: "プレミアム詳細を見る", en: "View Premium details" })}
          </button>
        )}

        {isPremium && (
          <p style={{ marginTop: 8, color: "#0a0", fontWeight: "bold" }}>
            {t({ ja: "現在プレミアム会員中です。", en: "You are currently Premium." })}
          </p>
        )}
      </section>

      <section style={{ marginTop: 16 }}>
        <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
          {t({ ja: "表示設定", en: "Display" })}
        </h3>
        <div
          style={{
            marginTop: 10,
            padding: "10px 12px",
            border: "1px solid var(--border)",
            borderRadius: 10,
            background: "var(--surface)",
            display: "flex",
            flexWrap: "wrap",
            gap: 10,
            alignItems: "center",
          }}
        >
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={showR18}
              onChange={(e) => setShowR18(e.target.checked)}
            />
            <span>{t({ ja: "R18作品を表示", en: "Show R18 works" })}</span>
          </label>
          {!showR18 && (
            <span style={{ fontSize: 12, color: "var(--muted-text)" }}>
              {t({
                ja: "R18は「作成した小説」「お気に入り」「アクセス解析(小説別)」から非表示になります。",
                en: "R18 items are hidden from your lists and per-novel analytics.",
              })}
            </span>
          )}
        </div>
      </section>

      {/* AIジョブ管理 */}
      <section style={{ marginTop: "2.5rem" }}>
        <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
          {t({ ja: "AIジョブ管理", en: "AI Jobs" })}
        </h3>
        <p style={{ marginTop: 8, lineHeight: 1.6, color: "var(--muted-text)" }}>
          {t({
            ja: "待機中/実行中のAI小説生成ジョブを停止できます。",
            en: "Stop pending or running AI jobs.",
          })}
        </p>
        {aiJobsError && <p style={{ marginTop: 10, color: "red" }}>{aiJobsError}</p>}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          <button type="button" className="btn btn-border" onClick={loadAiJobs} disabled={aiJobsLoading}>
            {aiJobsLoading ? t({ ja: "更新中...", en: "Refreshing..." }) : t({ ja: "更新", en: "Refresh" })}
          </button>
          <button
            type="button"
            className="btn btn-border"
            onClick={handleKillSelectedAiJobs}
            disabled={aiJobsLoading || aiJobsSelected.size === 0}
          >
            {t({ ja: "選択を停止", en: "Stop selected" })}
          </button>
          <button
            type="button"
            className="btn btn-border"
            onClick={handleKillAllAiJobs}
            disabled={aiJobsLoading}
          >
            {t({ ja: "すべて停止", en: "Stop all" })}
          </button>
        </div>
        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginTop: 10 }}>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => {
              setAiJobsFilter("all");
              setAiJobsPage(1);
            }}
            disabled={aiJobsFilter === "all"}
          >
            {t({ ja: "全件", en: "All" })}
          </button>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => {
              setAiJobsFilter("running");
              setAiJobsPage(1);
            }}
            disabled={aiJobsFilter === "running"}
          >
            {t({ ja: "実行中", en: "Running" })}
          </button>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => {
              setAiJobsFilter("succeeded");
              setAiJobsPage(1);
            }}
            disabled={aiJobsFilter === "succeeded"}
          >
            {t({ ja: "完了", en: "Completed" })}
          </button>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => {
              setAiJobsFilter("failed");
              setAiJobsPage(1);
            }}
            disabled={aiJobsFilter === "failed"}
          >
            {t({ ja: "失敗", en: "Failed" })}
          </button>
        </div>
        {aiJobsLoading ? (
          <p style={{ marginTop: 10 }}>{t({ ja: "読み込み中...", en: "Loading..." })}</p>
        ) : aiJobsFiltered.length ? (
          <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
            {aiJobsSlice.map((job) => (
              <label
                key={job.id}
                style={{
                  display: "flex",
                  gap: 10,
                  alignItems: "flex-start",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  padding: 10,
                  background: "var(--surface)",
                }}
              >
                <input
                  type="checkbox"
                  checked={aiJobsSelected.has(job.id)}
                  onChange={() => toggleAiJobSelected(job.id)}
                />
                <div>
                  <div style={{ fontWeight: 600 }}>
                    #{job.id} / {job.job_type}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted-text)" }}>
                    {t({ ja: "状態", en: "Status" })}: {job.status}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted-text)" }}>
                    {t({ ja: "作成", en: "Created" })}: {formatDateTimeInUserTimeZone(job.created_at, lang === "en" ? "en-US" : "ja-JP") || "-"}
                  </div>
                </div>
              </label>
            ))}
            {aiJobsTotalPages > 1 && (
              <div style={{ display: "flex", gap: "0.4rem", marginTop: 4, flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => setAiJobsPage((prev) => Math.max(1, prev - 1))}
                  disabled={aiJobsPageSafe <= 1}
                >
                  {t({ ja: "前へ", en: "Prev" })}
                </button>
                <div style={{ alignSelf: "center", fontSize: 12, color: "var(--muted-text)" }}>
                  {t(
                    { ja: "{{page}} / {{total}} ページ", en: "Page {{page}} / {{total}}" },
                    { page: aiJobsPageSafe, total: aiJobsTotalPages }
                  )}
                </div>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => setAiJobsPage((prev) => Math.min(aiJobsTotalPages, prev + 1))}
                  disabled={aiJobsPageSafe >= aiJobsTotalPages}
                >
                  {t({ ja: "次へ", en: "Next" })}
                </button>
              </div>
            )}
          </div>
        ) : (
          <p style={{ marginTop: 10, color: "var(--muted-text)" }}>
            {t({ ja: "ジョブがありません。", en: "No jobs found." })}
          </p>
        )}
      </section>

      {/* マイページ設定 */}
      <section style={{ marginTop: "2.5rem" }}>
        <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
          {t({ ja: "マイページ設定", en: "My Page settings" })}
        </h3>

        <div style={{ marginTop: 12 }}>
          <Link className="btn btn-border" to="/mypage/settings">
            {t({ ja: "設定を開く", en: "Open settings" })}
          </Link>
        </div>
        <div style={{ marginTop: 8 }}>
          <Link className="btn btn-border" to="/notifications">
            {t({ ja: "通知センター", en: "Notifications" })}
          </Link>
        </div>
      </section>

      <section style={{ marginTop: "2.5rem" }}>
        <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
          {t({ ja: "ブログ", en: "Blog" })}
        </h3>
        <p style={{ marginTop: 8, lineHeight: 1.6 }}>
          {t({ ja: "あなたの公開ページに表示するブログ記事を作成・更新できます。", en: "Create and update blog posts shown on your public page." })}
        </p>
        <div style={{ marginTop: 12 }}>
          <Link className="btn btn-border" to="/me/blog">
            {t({ ja: "ブログ作成・更新", en: "Create or update blog" })}
          </Link>
        </div>
      </section>

      <section style={{ marginTop: "2.5rem" }}>
        <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
          {t({ ja: "スマホアプリのダウンロード", en: "Mobile App Downloads" })}
        </h3>
        {hideAppDownloads ? (
          <>
            <p style={{ marginTop: 12, color: "var(--muted-text)" }}>
              {t({
                ja: "Android アプリは未配置です。",
                en: "Android app is not uploaded yet.",
              })}
            </p>
            <p style={{ marginTop: 8, color: "var(--muted-text)" }}>
              {t({
                ja: "iPhone アプリは未配置です。",
                en: "iPhone app is not uploaded yet.",
              })}
            </p>
          </>
        ) : (
          <>
            <p style={{ marginTop: 8, lineHeight: 1.6 }}>
              {t({
                ja: "Android / iPhone 向け実アプリファイルをダウンロードできます。",
                en: "Download app binaries for Android and iPhone.",
              })}
            </p>
            <p style={{ marginTop: 8, lineHeight: 1.6, fontWeight: 600 }}>
              {t({
                ja: `${MOBILE_APP_UPDATED_AT} にアプリを更新しました。`,
                en: `App updated on ${MOBILE_APP_UPDATED_AT}.`,
              })}
            </p>
            {androidAppReady ? (
              <div style={{ marginTop: 12 }}>
                <a className="btn btn-border" href={ANDROID_APP_FILE} download>
                  {t({ ja: "Android APKをダウンロード", en: "Download Android APK" })}
                </a>
              </div>
            ) : (
              <p style={{ marginTop: 12, color: "var(--muted-text)" }}>
                {t({
                  ja: "Android APK は未配置です（/static/app_downloads/novelsite-android.apk）。",
                  en: "Android APK is not uploaded yet (/static/app_downloads/novelsite-android.apk).",
                })}
              </p>
            )}
            {iphoneAppReady ? (
              <div style={{ marginTop: 8 }}>
                <a className="btn btn-border" href={IPHONE_APP_FILE} download>
                  {t({ ja: "iPhone IPAをダウンロード", en: "Download iPhone IPA" })}
                </a>
              </div>
            ) : (
              <p style={{ marginTop: 8, color: "var(--muted-text)" }}>
                {t({
                  ja: "iPhone IPA は未配置です（/static/app_downloads/novelsite-iphone.ipa）。",
                  en: "iPhone IPA is not uploaded yet (/static/app_downloads/novelsite-iphone.ipa).",
                })}
              </p>
            )}
          </>
        )}
      </section>

      {/* 作者ダッシュボード */}
      <section style={{ marginTop: "2.5rem" }}>
        <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
          {t({ ja: "作者ダッシュボード", en: "Creator Dashboard" })}
        </h3>
        <p style={{ marginTop: 8, lineHeight: 1.6 }}>
          {t({
            ja: "支援の売上残高や精算設定を確認できます。",
            en: "Check support revenue balances and payout settings.",
          })}
        </p>
        <div style={{ marginTop: 12 }}>
          <Link className="btn btn-border" to="/me/creator">
            {t({ ja: "作者ダッシュボードを開く", en: "Open creator dashboard" })}
          </Link>
        </div>
        {isPremium ? (
          <>
            <div style={{ marginTop: 8 }}>
              <Link className="btn btn-border" to="/author/dashboard">
                {t({ ja: "作品分析ダッシュボード", en: "Open analytics dashboard" })}
              </Link>
            </div>
            <div style={{ marginTop: 8 }}>
              <Link className="btn btn-border" to="/me/scheduled-episodes">
                {t({ ja: "予約投稿一覧", en: "Scheduled episodes" })}
              </Link>
            </div>
          </>
        ) : (
          <p style={{ marginTop: 8, color: "var(--muted-text)" }}>
            {t({
              ja: "作品分析ダッシュボードと投稿予約はプレミアム会員限定です。",
              en: "Analytics dashboard and scheduled publishing are premium-only features.",
            })}
          </p>
        )}
        <div style={{ marginTop: 8 }}>
          <Link className="btn btn-border" to="/me/support-plans">
            {t({ ja: "月額支援プラン管理", en: "Manage monthly plans" })}
          </Link>
        </div>
      </section>

      {/* 公開ページ */}
      <section style={{ marginTop: "2.5rem" }}>
        <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
          {t({ ja: "公開ページ", en: "Public page" })}
        </h3>
        <p style={{ marginTop: 8, lineHeight: 1.6 }}>
          {t({ ja: "他のユーザーから閲覧できるあなたのページです。", en: "Your page visible to other users." })}
        </p>
        <div style={{ marginTop: 12 }}>
          <Link className="btn btn-border" to={`/users/${encodeURIComponent(username)}`}>
            {t({ ja: "公開ページを見る", en: "View public page" })}
          </Link>
        </div>
      </section>

      {/* アクセス解析 */}
      <section style={{ marginTop: "2.5rem" }}>
        <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
          {t({ ja: "アクセス解析", en: "Analytics" })}
        </h3>

        <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
          <label style={{ fontSize: 14 }}>
            {t({ ja: "月を選択", en: "Select month" })}
          </label>
          <input
            type="month"
            value={analyticsMonth}
            onChange={(e) => setAnalyticsMonth(e.target.value)}
            style={{
              padding: "6px 10px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: "var(--surface)",
              color: "var(--text)",
            }}
          />
        </div>

        {analyticsLoading && <p style={{ marginTop: 10 }}>{t({ ja: "読み込み中...", en: "Loading..." })}</p>}
        {analyticsError && <p style={{ marginTop: 10, color: "red" }}>{analyticsError}</p>}

        {!analyticsLoading && !analyticsError && analyticsData && (
          <div style={{ marginTop: 16 }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
              <div
                style={{
                  padding: "8px 12px",
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                  background: "var(--surface)",
                }}
              >
                <strong style={{ fontSize: 13 }}>
                  {t({ ja: "合計閲覧", en: "Total views" })}
                </strong>
                <div style={{ fontSize: 18, marginTop: 4 }}>
                  {analyticsData.totals?.views ?? 0}
                </div>
              </div>
              <div
                style={{
                  padding: "8px 12px",
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                  background: "var(--surface)",
                }}
              >
                <strong style={{ fontSize: 13 }}>
                  {t({ ja: "合計いいね", en: "Total likes" })}
                </strong>
                <div style={{ fontSize: 18, marginTop: 4 }}>
                  {analyticsData.totals?.likes ?? 0}
                </div>
              </div>
              <div
                style={{
                  padding: "8px 12px",
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                  background: "var(--surface)",
                }}
              >
                <strong style={{ fontSize: 13 }}>
                  {t({ ja: "合計ブックマーク", en: "Total bookmarks" })}
                </strong>
                <div style={{ fontSize: 18, marginTop: 4 }}>
                  {analyticsData.totals?.favorites ?? 0}
                </div>
              </div>
            </div>

            <div style={{ marginTop: 16 }}>
              <h4 style={{ marginBottom: 8 }}>
                {t({ ja: "日ごとの履歴", en: "Daily history" })}
              </h4>
              {Array.isArray(analyticsData.days) && analyticsData.days.length > 0 ? (
                <div style={{ display: "grid", gap: 6 }}>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "120px repeat(3, minmax(0, 1fr))",
                      fontSize: 12,
                      color: "var(--muted-text)",
                      paddingBottom: 4,
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    <span>{t({ ja: "日付", en: "Date" })}</span>
                    <span>{t({ ja: "閲覧", en: "Views" })}</span>
                    <span>{t({ ja: "いいね", en: "Likes" })}</span>
                    <span>{t({ ja: "ブックマーク", en: "Bookmarks" })}</span>
                  </div>
                  {analyticsData.days.map((row: AnalyticsDay) => (
                    <div
                      key={row.date}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "120px repeat(3, minmax(0, 1fr))",
                        fontSize: 13,
                        padding: "4px 0",
                        borderBottom: "1px solid rgba(0,0,0,0.04)",
                      }}
                    >
                      <span>{row.date}</span>
                      <span>{row.views ?? 0}</span>
                      <span>{row.likes ?? 0}</span>
                      <span>{row.favorites ?? 0}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ marginTop: 8 }}>
                  {t({ ja: "データがありません。", en: "No data." })}
                </p>
              )}
            </div>

            <div style={{ marginTop: 20 }}>
              <h4 style={{ marginBottom: 8 }}>
                {t({ ja: "小説別の集計", en: "By novel" })}
              </h4>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center", marginBottom: 12 }}>
                <label style={{ fontSize: 14 }}>
                  {t({ ja: "小説を選択", en: "Select novel" })}
                </label>
                <select
                  value={selectedNovelId}
                  onChange={(e) => setSelectedNovelId(e.target.value)}
                  style={{
                    padding: "6px 10px",
                    borderRadius: 6,
                    border: "1px solid var(--border)",
                    background: "var(--surface)",
                    color: "var(--text)",
                    minWidth: 220,
                  }}
                >
                  <option value="">{t({ ja: "選択してください", en: "Choose a novel" })}</option>
                  {(() => {
                    const all = Array.isArray(analyticsData?.novels) ? analyticsData.novels : [];
                    const visible = showR18 ? all : all.filter((n: AnalyticsNovel) => !isR18Novel(n));
                    return visible.map((novel: AnalyticsNovel) => (
                      <option key={novel.id} value={novel.id}>
                        {novel.title || t({ ja: "無題", en: "Untitled" })}
                      </option>
                    ));
                  })()}
                </select>
              </div>
              {(() => {
                const all = Array.isArray(analyticsData?.novels) ? analyticsData.novels : [];
                const visible = showR18 ? all : all.filter((n: AnalyticsNovel) => !isR18Novel(n));
                if (visible.length > 0) {
                  return (
                <div style={{ display: "grid", gap: 6 }}>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr repeat(3, minmax(0, 120px))",
                      fontSize: 12,
                      color: "var(--muted-text)",
                      paddingBottom: 4,
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    <span>{t({ ja: "タイトル", en: "Title" })}</span>
                    <span>{t({ ja: "閲覧", en: "Views" })}</span>
                    <span>{t({ ja: "いいね", en: "Likes" })}</span>
                    <span>{t({ ja: "ブックマーク", en: "Bookmarks" })}</span>
                  </div>
                  {visible.map((novel: AnalyticsNovel) => (
                    <div
                      key={novel.id}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr repeat(3, minmax(0, 120px))",
                        fontSize: 13,
                        padding: "4px 0",
                        borderBottom: "1px solid rgba(0,0,0,0.04)",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <Link to={`/novels/${novel.id}`} style={{ fontWeight: 600 }}>
                        {novel.title || t({ ja: "無題", en: "Untitled" })}
                      </Link>
                      <span>{novel.views ?? 0}</span>
                      <span>{novel.likes ?? 0}</span>
                      <span>{novel.favorites ?? 0}</span>
                    </div>
                  ))}
                </div>
                  );
                }
                if (all.length > 0 && !showR18) {
                  return (
                    <p style={{ marginTop: 8, color: "var(--muted-text)" }}>
                      {t({ ja: "R18作品を非表示にしているため、表示できるデータがありません。", en: "No visible data (R18 is hidden)." })}
                    </p>
                  );
                }
                return (
                  <p style={{ marginTop: 8 }}>
                    {t({ ja: "小説別のデータがありません。", en: "No per-novel data." })}
                  </p>
                );
              })()}
            </div>

            <div style={{ marginTop: 20 }}>
              <h4 style={{ marginBottom: 8 }}>
                {t({ ja: "小説別の日ごとの履歴", en: "Novel daily history" })}
              </h4>
              {!selectedNovelId && (
                <p style={{ marginTop: 8 }}>
                  {t({ ja: "小説を選択すると日ごとの集計が表示されます。", en: "Select a novel to see daily stats." })}
                </p>
              )}
              {novelAnalyticsLoading && <p style={{ marginTop: 8 }}>{t({ ja: "読み込み中...", en: "Loading..." })}</p>}
              {novelAnalyticsError && <p style={{ marginTop: 8, color: "red" }}>{novelAnalyticsError}</p>}
              {!novelAnalyticsLoading && !novelAnalyticsError && selectedNovelAnalytics && (
                <div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 10 }}>
                    <div
                      style={{
                        padding: "8px 12px",
                        borderRadius: 8,
                        border: "1px solid var(--border)",
                        background: "var(--surface)",
                      }}
                    >
                      <strong style={{ fontSize: 13 }}>
                        {t({ ja: "合計閲覧", en: "Total views" })}
                      </strong>
                      <div style={{ fontSize: 18, marginTop: 4 }}>
                        {selectedNovelAnalytics.totals?.views ?? 0}
                      </div>
                    </div>
                    <div
                      style={{
                        padding: "8px 12px",
                        borderRadius: 8,
                        border: "1px solid var(--border)",
                        background: "var(--surface)",
                      }}
                    >
                      <strong style={{ fontSize: 13 }}>
                        {t({ ja: "合計いいね", en: "Total likes" })}
                      </strong>
                      <div style={{ fontSize: 18, marginTop: 4 }}>
                        {selectedNovelAnalytics.totals?.likes ?? 0}
                      </div>
                    </div>
                    <div
                      style={{
                        padding: "8px 12px",
                        borderRadius: 8,
                        border: "1px solid var(--border)",
                        background: "var(--surface)",
                      }}
                    >
                      <strong style={{ fontSize: 13 }}>
                        {t({ ja: "合計ブックマーク", en: "Total bookmarks" })}
                      </strong>
                      <div style={{ fontSize: 18, marginTop: 4 }}>
                        {selectedNovelAnalytics.totals?.favorites ?? 0}
                      </div>
                    </div>
                  </div>
                  {Array.isArray(selectedNovelAnalytics.days) && selectedNovelAnalytics.days.length > 0 ? (
                    <div style={{ display: "grid", gap: 6 }}>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "120px repeat(3, minmax(0, 1fr))",
                          fontSize: 12,
                          color: "var(--muted-text)",
                          paddingBottom: 4,
                          borderBottom: "1px solid var(--border)",
                        }}
                      >
                        <span>{t({ ja: "日付", en: "Date" })}</span>
                        <span>{t({ ja: "閲覧", en: "Views" })}</span>
                        <span>{t({ ja: "いいね", en: "Likes" })}</span>
                        <span>{t({ ja: "ブックマーク", en: "Bookmarks" })}</span>
                      </div>
                      {selectedNovelAnalytics.days.map((row: AnalyticsDay) => (
                        <div
                          key={row.date}
                          style={{
                            display: "grid",
                            gridTemplateColumns: "120px repeat(3, minmax(0, 1fr))",
                            fontSize: 13,
                            padding: "4px 0",
                            borderBottom: "1px solid rgba(0,0,0,0.04)",
                          }}
                        >
                          <span>{row.date}</span>
                          <span>{row.views ?? 0}</span>
                          <span>{row.likes ?? 0}</span>
                          <span>{row.favorites ?? 0}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={{ marginTop: 8 }}>
                      {t({ ja: "データがありません。", en: "No data." })}
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </section>

      {/* お気に入りAIチャット */}
      <section style={{ marginTop: "2.5rem" }}>
        <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
          {t({ ja: "お気に入りAIチャット", en: "Favorite AI chats" })}
        </h3>

        {aiChatFavoritesVisible.length === 0 ? (
          <p style={{ marginTop: 10 }}>
            {aiChatFavorites.length > 0 && !showR18
              ? t({ ja: "R18作品を非表示にしているため、表示できるお気に入りがありません。", en: "No visible favorites (R18 is hidden)." })
              : t({ ja: "お気に入りはまだありません。", en: "No favorites yet." })}
          </p>
        ) : (
          <div style={{ display: "grid", gap: 14, marginTop: 14 }}>
            {aiChatFavoritesVisible.map((item) => (
              <div
                key={item.id}
                style={{
                  border: "1px solid var(--novel-card-border)",
                  borderRadius: 8,
                  padding: 12,
                  boxShadow: "0 2px 4px var(--shadow)",
                  backgroundColor: "var(--novel-card-bg)",
                  color: "var(--text)",
                }}
              >
                {item.image_url && (
                  <img
                    src={item.image_url.startsWith("http") ? item.image_url : API_BASE + item.image_url}
                    alt={t({ ja: "キャラクター画像", en: "Character image" })}
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
                <h4 style={{ marginBottom: 6 }}>
                  <Link to={`/ai_chat/public/${item.id}`}>{item.name}</Link>
                </h4>
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
                  <span>@{item.author_username || "unknown"}</span>
                  <span>{t({ ja: "LIKE", en: "Likes" })}: {item.like_count ?? 0}</span>
                  <span>{t({ ja: "ブックマーク", en: "Bookmarks" })}: {item.favorite_count ?? 0}</span>
                  {item.is_r18 ? <span>R18</span> : null}
                </div>
                <p style={{ fontSize: 14, whiteSpace: "pre-wrap", margin: 0 }}>
                  {item.personality || ""}
                </p>
                <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
                  <Link className="btn btn-border" to={`/ai_chat/public/${item.id}`}>
                    {t({ ja: "公開チャットを見る", en: "View public chat" })}
                  </Link>
                  <Link
                    className="btn btn-border"
                    to="/ai_chat"
                    state={{
                      source: "public_chat_character",
                      characterId: item.id,
                      prefillCharacterName: item.name || "",
                      prefillPersonality: item.personality || "",
                    }}
                  >
                    {t({ ja: "このキャラでAIチャットを開始", en: "Start AI chat with this character" })}
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* お気に入り小説 */}
      <section style={{ marginTop: "2.5rem" }}>
        <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
          {t({ ja: "お気に入り小説", en: "Favorite novels" })}
        </h3>

        {favoritesVisible.length === 0 ? (
          <p style={{ marginTop: 10 }}>
            {favorites.length > 0 && !showR18
              ? t({ ja: "R18作品を非表示にしているため、表示できるお気に入りがありません。", en: "No visible favorites (R18 is hidden)." })
              : t({ ja: "お気に入りはまだありません。", en: "No favorites yet." })}
          </p>
        ) : (
          <div style={{ display: "grid", gap: 14, marginTop: 14 }}>
            {favoritesVisible.map((novel) => (
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
                <h4 style={{ marginBottom: 6 }}>
                  <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
                </h4>

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
                  <span>{t({ ja: "お気に入り", en: "Favorites" })}: {novel.favorite_count ?? 0}</span>
                  <span>{t({ ja: "文字数", en: "Chars" })}: {novel.total_char_count ?? 0}</span>
                  <span className="tag-chip-row">
                    {Array.isArray(novel.tags) && novel.tags.length > 0 ? (
                      novel.tags.map((t: TagItem) => (
                        <TagChipLink key={t.id ?? t.name} name={t.name} />
                      ))
                    ) : (
                      <span style={{ color: "var(--muted-text)" }}>
                        {t({ ja: "タグ: なし", en: "Tags: none" })}
                      </span>
                    )}
                  </span>
                </div>

                <p style={{ fontSize: 14, whiteSpace: "pre-wrap", margin: 0 }}>
                  {truncateFavoriteSummary(novel.description)}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 閲覧履歴 */}
      <section style={{ marginTop: "2.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: 6, margin: 0 }}>
            {t({ ja: "閲覧履歴", en: "View History" })}
          </h3>
          <Link className="btn btn-border" to="/me/view-history">
            {t({ ja: "続きを見る", en: "See more" })}
          </Link>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          <button
            type="button"
            className="btn btn-border"
            disabled={viewHistoryLimit === 10}
            onClick={() => setViewHistoryLimit(10)}
            style={
              viewHistoryLimit === 10
                ? {
                    background: "var(--accent, #2f6f6d)",
                    borderColor: "var(--accent, #2f6f6d)",
                    color: "#fff",
                    fontWeight: 700,
                  }
                : undefined
            }
          >
            {t({ ja: "10件", en: "10 items" })}
          </button>
          <button
            type="button"
            className="btn btn-border"
            disabled={viewHistoryLimit === 20}
            onClick={() => setViewHistoryLimit(20)}
            style={
              viewHistoryLimit === 20
                ? {
                    background: "var(--accent, #2f6f6d)",
                    borderColor: "var(--accent, #2f6f6d)",
                    color: "#fff",
                    fontWeight: 700,
                  }
                : undefined
            }
          >
            {t({ ja: "20件", en: "20 items" })}
          </button>
        </div>
        {viewHistoryError && <p style={{ color: "red", marginTop: 10 }}>{viewHistoryError}</p>}
        {viewHistoryLoading ? (
          <p style={{ marginTop: 10 }}>{t({ ja: "読み込み中...", en: "Loading..." })}</p>
        ) : viewHistoryVisible.length === 0 ? (
          <p style={{ marginTop: 10 }}>
            {viewHistoryItems.length > 0 && !showR18
              ? t({ ja: "R18作品を非表示にしているため、表示できる閲覧履歴がありません。", en: "No visible history (R18 is hidden)." })
              : t({ ja: "閲覧履歴はまだありません。", en: "No view history yet." })}
          </p>
        ) : (
          <div style={{ display: "grid", gap: 12, marginTop: 12 }}>
            {viewHistoryVisible.map((item) => (
              <div
                key={`${item.target_id}-${item.viewed_at || ""}`}
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  padding: 12,
                  background: "var(--surface)",
                }}
              >
                <h4 style={{ margin: "0 0 6px 0" }}>
                  <Link to={`/novels/${item.target_id}`}>{item.title || `#${item.target_id}`}</Link>
                </h4>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", fontSize: 12, color: "var(--muted-text)" }}>
                  <span>{t({ ja: "作者", en: "Author" })}: @{item.author_username || "-"}</span>
                  <span>{t({ ja: "閲覧回数", en: "Views" })}: {item.view_count ?? 0}</span>
                  <span>{t({ ja: "最終閲覧", en: "Last viewed" })}: {item.viewed_at || "-"}</span>
                  {item.age_limit ? <span>{String(item.age_limit).toUpperCase()}</span> : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 作成した小説 */}
      <section style={{ marginTop: "3rem" }}>
        <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
          {t({ ja: "作成した小説", en: "Your novels" })}
        </h3>

        {error && <p style={{ color: "red" }}>{error}</p>}

        {novelsVisible.length === 0 && (
          <p style={{ marginTop: 10 }}>
            {novels.length > 0 && !showR18
              ? t({ ja: "R18作品を非表示にしているため、表示できる小説がありません。", en: "No visible novels (R18 is hidden)." })
              : t({ ja: "まだ作成した小説がありません。", en: "You haven't created any novels yet." })}
          </p>
        )}

        <div style={{ display: "grid", gap: 20, marginTop: 20 }}>
          {novelsVisible.map((novel) => (
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
              <h4 style={{ marginBottom: 6 }}>
                <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
              </h4>

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
                <span>{t({ ja: "お気に入り", en: "Favorites" })}: {novel.favorite_count ?? 0}</span>
                <span>{t({ ja: "文字数", en: "Chars" })}: {novel.total_char_count ?? 0}</span>
                <span className="tag-chip-row">
                  {Array.isArray(novel.tags) && novel.tags.length > 0 ? (
                    novel.tags.map((t: TagItem) => (
                      <TagChipLink key={t.id ?? t.name} name={t.name} />
                    ))
                  ) : (
                    <span style={{ color: "var(--muted-text)" }}>
                      {t({ ja: "タグ: なし", en: "Tags: none" })}
                    </span>
                  )}
                </span>
              </div>

              <p
                style={{
                  fontSize: 14,
                  marginTop: 6,
                  marginBottom: 12,
                  whiteSpace: "pre-wrap",
                }}
              >
                {novel.description || ""}
              </p>

              <div style={{ display: "flex", gap: 10 }}>
                <Link className="btn btn-border" to={`/novels/${novel.id}`}>
                  {t({ ja: "詳細を見る", en: "View details" })}
                </Link>
                <Link
                  className="btn btn-border"
                  to={`/novels/${novel.id}/edit`}
                >
                  {t({ ja: "編集する", en: "Edit" })}
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
