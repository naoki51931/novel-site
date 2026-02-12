import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import TagChipLink from "../components/TagChipLink.jsx";
import { getStoredLanguage, translate, useI18n } from "../lib/i18n";

const API_BASE = import.meta.env.VITE_BACKEND_ORIGIN || "https://shosetsu-toukou-site.org";
const ANDROID_APP_FILE = "/static/app_downloads/novelsite-android.apk";
const IPHONE_APP_FILE = "/static/app_downloads/novelsite-iphone.ipa";
const MOBILE_APP_UPDATED_AT = "2026/02/12";

async function startStripeCheckout(navigate) {
  try {
    const token = localStorage.getItem("token");
    if (!token) {
      alert(
        translate(
          { ja: "ログインしてください。ログインページへ移動します。", en: "Please log in. Redirecting to login page." },
          getStoredLanguage()
        )
      );
      navigate("/login");
      return;
    }

    const res = await fetch("/api/stripe/create-checkout-session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
      },
    });

    const data = await res.json().catch(() => ({}));

    if (res.status === 401) {
      alert(
        translate(
          { ja: "ログインしてください。ログインページへ移動します。", en: "Please log in. Redirecting to login page." },
          getStoredLanguage()
        )
      );
      navigate("/login");
      return;
    }

    if (!res.ok) {
      throw new Error(
        data.detail ||
          translate(
            { ja: "決済セッションの作成に失敗しました ({{status}})", en: "Failed to create checkout session ({{status}})" },
            getStoredLanguage(),
            { status: res.status }
          )
      );
    }

    if (data.url) {
      window.location.href = data.url;
    } else {
      throw new Error(
        translate({ ja: "決済URLが取得できませんでした。", en: "Could not get checkout URL." }, getStoredLanguage())
      );
    }
  } catch (err) {
    console.error(err);
    alert(
      err.message ||
        translate({ ja: "決済の開始に失敗しました。", en: "Failed to start payment." }, getStoredLanguage())
    );
  }
}

export default function Mypage() {
  const { t } = useI18n();
  const [novels, setNovels] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [isPremium, setIsPremium] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [analyticsMonth, setAnalyticsMonth] = useState(() => {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    return `${now.getFullYear()}-${month}`;
  });
  const [analyticsData, setAnalyticsData] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState("");
  const [selectedNovelId, setSelectedNovelId] = useState("");
  const [selectedNovelAnalytics, setSelectedNovelAnalytics] = useState(null);
  const [novelAnalyticsLoading, setNovelAnalyticsLoading] = useState(false);
  const [novelAnalyticsError, setNovelAnalyticsError] = useState("");
  const [aiJobs, setAiJobs] = useState([]);
  const [aiJobsLoading, setAiJobsLoading] = useState(false);
  const [aiJobsError, setAiJobsError] = useState("");
  const [aiJobsSelected, setAiJobsSelected] = useState(() => new Set());
  const [aiJobsPage, setAiJobsPage] = useState(1);
  const [aiJobsFilter, setAiJobsFilter] = useState("all");
  const [username, setUsername] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("username") || "";
  });
  const [androidAppReady, setAndroidAppReady] = useState(false);
  const [iphoneAppReady, setIphoneAppReady] = useState(false);
  const navigate = useNavigate();

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const formatErrorDetail = (detail, fallback) => {
    if (typeof detail === "string" && detail.trim()) return detail;
    if (detail) return JSON.stringify(detail);
    return fallback;
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

        const res = await fetch(`${API_BASE}/api/novels?mine=true`, {
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

        const sorted = (data || []).slice().sort((a, b) => {
          const ad = a.created_at ? new Date(a.created_at).getTime() : 0;
          const bd = b.created_at ? new Date(b.created_at).getTime() : 0;
          return bd - ad;
        });
        setNovels(sorted);
      } catch (err) {
        console.error(err);
        setError(
          err.message || t({ ja: "マイページの取得中にエラーが発生しました", en: "An error occurred while loading My Page." })
        );
      } finally {
        setLoading(false);
      }
    };

    fetchMine();
  }, [navigate, token]);

  const loadAiJobs = async () => {
    if (!token) return;
    try {
      setAiJobsLoading(true);
      setAiJobsError("");
      const res = await fetch(`${API_BASE}/api/ai/jobs/me`, {
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
        err.message || t({ ja: "AIジョブの取得中にエラーが発生しました", en: "Failed to load AI jobs." })
      );
    } finally {
      setAiJobsLoading(false);
    }
  };

  useEffect(() => {
    loadAiJobs();
  }, [token]);

  useEffect(() => {
    const checkFile = async (url, setter) => {
      try {
        const res = await fetch(url, { method: "HEAD" });
        setter(res.ok);
      } catch {
        setter(false);
      }
    };
    checkFile(ANDROID_APP_FILE, setAndroidAppReady);
    checkFile(IPHONE_APP_FILE, setIphoneAppReady);
  }, []);

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
        const resFav = await fetch(`${API_BASE}/api/me/favorites`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (resFav.ok) {
          const dataFav = await resFav.json();
          const sortedFav = (dataFav || []).slice().sort((a, b) => {
            const ad = a.created_at ? new Date(a.created_at).getTime() : 0;
            const bd = b.created_at ? new Date(b.created_at).getTime() : 0;
            return bd - ad;
          });
          setFavorites(sortedFav);
        } else {
          console.error("failed to fetch favorites");
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
  }, [token]);

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
          err.message ||
            t({ ja: "アクセス解析の取得中にエラーが発生しました", en: "An error occurred while loading analytics." })
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
          err.message ||
            t({
              ja: "小説別アクセス解析の取得中にエラーが発生しました",
              en: "An error occurred while loading novel analytics.",
            })
        );
      } finally {
        setNovelAnalyticsLoading(false);
      }
    };

    fetchNovelAnalytics();
  }, [analyticsMonth, selectedNovelId, token, t]);

  const toggleAiJobSelected = (jobId) => {
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
        err.message || t({ ja: "AIジョブの停止中にエラーが発生しました", en: "Failed to stop AI jobs." })
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
        err.message || t({ ja: "AIジョブの停止中にエラーが発生しました", en: "Failed to stop AI jobs." })
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
              backgroundColor: "#f0b400",
              color: "#fff",
              fontSize: 12,
            }}
          >
            PREMIUM
          </span>
        )}
      </h2>

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
            onClick={() => startStripeCheckout(navigate)}
          >
            {t({ ja: "プレミアム会員になる（決済ページへ）", en: "Become Premium (go to payment)" })}
          </button>
        )}

        {isPremium && (
          <p style={{ marginTop: 8, color: "#0a0", fontWeight: "bold" }}>
            {t({ ja: "現在プレミアム会員中です。", en: "You are currently Premium." })}
          </p>
        )}
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
                    {t({ ja: "作成", en: "Created" })}: {job.created_at || "-"}
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
          {t({ ja: "スマホアプリのダウンロード", en: "Mobile App Downloads" })}
        </h3>
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
                  {analyticsData.days.map((row) => (
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
                  {(analyticsData.novels || []).map((novel) => (
                    <option key={novel.id} value={novel.id}>
                      {novel.title || t({ ja: "無題", en: "Untitled" })}
                    </option>
                  ))}
                </select>
              </div>
              {Array.isArray(analyticsData.novels) && analyticsData.novels.length > 0 ? (
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
                  {analyticsData.novels.map((novel) => (
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
              ) : (
                <p style={{ marginTop: 8 }}>
                  {t({ ja: "小説別のデータがありません。", en: "No per-novel data." })}
                </p>
              )}
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
                      {selectedNovelAnalytics.days.map((row) => (
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

      {/* お気に入り小説 */}
      <section style={{ marginTop: "2.5rem" }}>
        <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
          {t({ ja: "お気に入り小説", en: "Favorite novels" })}
        </h3>

        {favorites.length === 0 ? (
          <p style={{ marginTop: 10 }}>
            {t({ ja: "お気に入りはまだありません。", en: "No favorites yet." })}
          </p>
        ) : (
          <div style={{ display: "grid", gap: 14, marginTop: 14 }}>
            {favorites.map((novel) => (
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
                      novel.tags.map((t) => (
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
                  {novel.description || ""}
                </p>
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

        {novels.length === 0 && (
          <p style={{ marginTop: 10 }}>
            {t({ ja: "まだ作成した小説がありません。", en: "You haven't created any novels yet." })}
          </p>
        )}

        <div style={{ display: "grid", gap: 20, marginTop: 20 }}>
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
                    novel.tags.map((t) => (
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
