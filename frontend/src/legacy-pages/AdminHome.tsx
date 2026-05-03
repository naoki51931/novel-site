import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";

type ContactMessage = {
  id: number | string;
  subject?: string | null;
  body?: string | null;
  admin_username?: string | null;
  created_at: string;
};

type IndexingUrlItem = {
  url?: string | null;
  indexed?: boolean | null;
  score?: number | null;
  view_count?: number | null;
  page_type?: string | null;
  inspection_verdict?: string | null;
  inspection_error?: string | null;
};

type IndexingResult = {
  daily_limit?: number | null;
  carryover_count?: number | null;
  carryover_updated_at?: string | null;
  carryover_urls?: string[] | null;
  submitted?: number | null;
  success?: number | null;
  failed?: number | null;
  attempted?: number | null;
};

export default function AdminHome() {
  const navigate = useNavigate();
  const { t, lang } = useI18n();
  const [contactError, setContactError] = useState("");
  const [contactMessages, setContactMessages] = useState<ContactMessage[]>([]);
  const [contactLoading, setContactLoading] = useState(true);
  const [indexingError, setIndexingError] = useState("");
  const [indexingLoading, setIndexingLoading] = useState(false);
  const [indexingSubmitting, setIndexingSubmitting] = useState(false);
  const [indexingUrlItems, setIndexingUrlItems] = useState<IndexingUrlItem[]>([]);
  const [indexingTotal, setIndexingTotal] = useState(0);
  const [indexingSummary, setIndexingSummary] = useState({
    indexed: 0,
    unindexed: 0,
    unknown: 0,
  });
  const [indexingInspectionError, setIndexingInspectionError] = useState("");
  const [indexingResult, setIndexingResult] = useState<IndexingResult | null>(null);
  const [indexingDailyLimit, setIndexingDailyLimit] = useState(199);
  const [indexingCarryoverCount, setIndexingCarryoverCount] = useState(0);
  const [indexingCarryoverUpdatedAt, setIndexingCarryoverUpdatedAt] = useState("");
  const [indexingCarryoverUrls, setIndexingCarryoverUrls] = useState<string[]>([]);
  const [indexingCarryoverClearing, setIndexingCarryoverClearing] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        await apiFetch("/api/admin/auth/me", { credentials: "include" });
      } catch {
        navigate("/admin/login", { replace: true });
        return;
      }
      try {
        const messages = await apiFetch("/api/admin/contact/messages?limit=50", {
          credentials: "include",
        });
        setContactMessages(messages || []);
      } catch (e) {
        setContactError(
          getErrorMessage(e, t({ ja: "送信ログの取得に失敗しました。", en: "Failed to load messages." }))
        );
      } finally {
        setContactLoading(false);
      }
      try {
        const carry = await apiFetch("/api/admin/indexing/carryover", {
          credentials: "include",
        });
        setIndexingDailyLimit(Number(carry?.daily_limit) || 199);
        setIndexingCarryoverCount(Number(carry?.carryover_count) || 0);
        setIndexingCarryoverUpdatedAt(String(carry?.carryover_updated_at || ""));
        setIndexingCarryoverUrls(Array.isArray(carry?.carryover_urls) ? carry.carryover_urls : []);
      } catch {
        // ignore
      }
    };
    checkAuth();
  }, [navigate, t]);

  const handleLogout = async () => {
    await apiFetch("/api/admin/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    navigate("/admin/login", { replace: true });
  };

  const handleLoadIndexingUrls = async () => {
    try {
      setIndexingLoading(true);
      setIndexingError("");
      setIndexingInspectionError("");
      const data = await apiFetch("/api/admin/indexing/urls?limit=2000&inspect=1", {
        credentials: "include",
      });
      const items = Array.isArray(data?.items)
        ? data.items
        : (Array.isArray(data?.urls) ? data.urls : []).map((url: string) => ({
            url,
            indexed: null,
            inspection_verdict: null,
            inspection_error: null,
          }));
      setIndexingUrlItems(items);
      setIndexingTotal(Number(data?.total) || 0);
      setIndexingSummary({
        indexed: Number(data?.indexed_count) || 0,
        unindexed: Number(data?.unindexed_count) || 0,
        unknown: Number(data?.unknown_count) || 0,
      });
      setIndexingDailyLimit(Number(data?.daily_limit) || 199);
      setIndexingCarryoverCount(Number(data?.carryover_count) || 0);
      setIndexingCarryoverUpdatedAt(String(data?.carryover_updated_at || ""));
      setIndexingCarryoverUrls(Array.isArray(data?.carryover_urls) ? data.carryover_urls : []);
      if (data?.inspection_error) {
        setIndexingInspectionError(String(data.inspection_error));
      }
    } catch (e) {
      setIndexingError(
        getErrorMessage(e, t({ ja: "URL一覧の取得に失敗しました。", en: "Failed to load URL list." }))
      );
    } finally {
      setIndexingLoading(false);
    }
  };

  const handleSubmitAllIndexing = async () => {
    try {
      setIndexingSubmitting(true);
        setIndexingError("");
      const prioritizedUrls = indexingUrlItems.length
        ? [...indexingUrlItems]
            .sort((a: IndexingUrlItem, b: IndexingUrlItem) => {
              const rank = (v: boolean | null | undefined) =>
                v === false ? 0 : v === null || typeof v === "undefined" ? 1 : 2;
              const rankDiff = rank(a?.indexed) - rank(b?.indexed);
              if (rankDiff !== 0) return rankDiff;
              const scoreA = Number(a?.score) || 0;
              const scoreB = Number(b?.score) || 0;
              return scoreB - scoreA;
            })
            .map((item) => item?.url)
            .filter(Boolean)
        : [];
      const data = await apiFetch("/api/admin/indexing/submit", {
        method: "POST",
        body: prioritizedUrls.length ? { all_pages: false, urls: prioritizedUrls } : { all_pages: true },
        credentials: "include",
      });
      setIndexingResult(data || null);
      setIndexingDailyLimit(Number(data?.daily_limit) || 199);
      setIndexingCarryoverCount(Number(data?.carryover_count) || 0);
      setIndexingCarryoverUpdatedAt(String(data?.carryover_updated_at || ""));
      setIndexingCarryoverUrls(Array.isArray(data?.carryover_urls) ? data.carryover_urls : []);
      if (!indexingTotal && Number(data?.submitted) > 0) {
        setIndexingTotal(Number(data.submitted));
      }
    } catch (e) {
      setIndexingError(
        getErrorMessage(
          e,
          t({ ja: "インデックス送信に失敗しました。", en: "Failed to submit indexing requests." })
        )
      );
    } finally {
      setIndexingSubmitting(false);
    }
  };

  const handleClearIndexingCarryover = async () => {
    try {
      setIndexingCarryoverClearing(true);
      setIndexingError("");
      const data = await apiFetch("/api/admin/indexing/carryover", {
        method: "DELETE",
        credentials: "include",
      });
      setIndexingDailyLimit(Number(data?.daily_limit) || 199);
      setIndexingCarryoverCount(Number(data?.carryover_count) || 0);
      setIndexingCarryoverUpdatedAt(String(data?.carryover_updated_at || ""));
      setIndexingCarryoverUrls(Array.isArray(data?.carryover_urls) ? data.carryover_urls : []);
    } catch (e) {
      setIndexingError(
        getErrorMessage(
          e,
          t({ ja: "繰越キューの削除に失敗しました。", en: "Failed to clear carryover queue." })
        )
      );
    } finally {
      setIndexingCarryoverClearing(false);
    }
  };

  return (
    <div style={{ maxWidth: 700, margin: "0 auto" }}>
      <section
        id="admin-contact"
        style={{
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: 16,
          marginBottom: 20,
          background: "var(--surface)",
        }}
      >
        <h3 style={{ marginTop: 0 }}>{t({ ja: "お問い合わせ", en: "Contact" })}</h3>
        {contactError && <div style={{ color: "red" }}>{contactError}</div>}
        <div style={{ marginTop: 16 }}>
          <h4 style={{ marginBottom: 8 }}>{t({ ja: "送信ログ", en: "Send log" })}</h4>
          {contactLoading ? (
            <div>{t({ ja: "読み込み中...", en: "Loading..." })}</div>
          ) : contactMessages.length ? (
            <div style={{ display: "grid", gap: 10 }}>
              {contactMessages.map((message: ContactMessage) => (
                <div
                  key={message.id}
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    padding: 10,
                    background: "var(--surface-2)",
                  }}
                >
                  <div style={{ fontWeight: 600 }}>{message.subject}</div>
                  <div style={{ whiteSpace: "pre-wrap", marginTop: 6 }}>{message.body}</div>
                  <div style={{ fontSize: 12, color: "var(--muted-text)", marginTop: 6 }}>
                    {message.admin_username
                      ? `${message.admin_username} / `
                      : ""}
                    {new Date(message.created_at).toLocaleString(
                      lang === "en" ? "en-US" : "ja-JP",
                      { timeZone: "Asia/Tokyo" }
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: "var(--muted-text)" }}>
              {t({ ja: "送信ログはまだありません。", en: "No messages yet." })}
            </div>
          )}
        </div>
      </section>
      <section
        style={{
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: 16,
          marginBottom: 20,
          background: "var(--surface)",
        }}
      >
        <h3 style={{ marginTop: 0 }}>
          {t({ ja: "Google インデックス登録送信", en: "Google Indexing Submission" })}
        </h3>
        <p style={{ color: "var(--muted-text)", marginTop: 0 }}>
          {t({
            ja: "公開ページURLを取得し、スコア（重要度・閲覧数・新しさ）が高い順に Google Indexing API に送信します。必要に応じてSearch Console確認付きAPIを別途実行できます。",
            en: "Load public URLs, then submit to Google Indexing API by priority score (importance, views, recency). You can run Search Console inspection separately when needed.",
          })}
        </p>
        {indexingError && <div style={{ color: "red", marginBottom: 8 }}>{indexingError}</div>}
        {indexingInspectionError && (
          <div style={{ color: "#a16207", marginBottom: 8 }}>{indexingInspectionError}</div>
        )}
        <button
          type="button"
          className="btn btn-border"
          onClick={handleLoadIndexingUrls}
          disabled={indexingLoading}
        >
          {indexingLoading
            ? t({ ja: "URL一覧を取得中...", en: "Loading URLs..." })
            : t({ ja: "公開URL一覧を取得", en: "Load public URLs" })}
        </button>
        <button
          type="button"
          className="btn btn-border"
          onClick={handleSubmitAllIndexing}
          disabled={indexingSubmitting}
          style={{ marginLeft: 8 }}
        >
          {indexingSubmitting
            ? t({ ja: "送信中...", en: "Submitting..." })
            : t({
                ja: "未登録ページ優先でインデックス登録送信",
                en: "Submit to indexing (prioritize unindexed)",
              })}
        </button>
        <div style={{ marginTop: 10, fontSize: 13, color: "var(--muted-text)" }}>
          {t(
            { ja: "1日あたり送信上限: {{count}}", en: "Daily submit limit: {{count}}" },
            { count: indexingDailyLimit || 199 }
          )}
        </div>
        <div style={{ marginTop: 6, fontSize: 13, color: "var(--muted-text)" }}>
          {t(
            { ja: "対象URL数: {{count}}", en: "Target URLs: {{count}}" },
            { count: indexingTotal || indexingUrlItems.length || 0 }
          )}
        </div>
        <div style={{ marginTop: 6, fontSize: 13, color: "var(--muted-text)" }}>
          {t(
            { ja: "繰越キュー: {{count}} 件", en: "Carryover queue: {{count}}" },
            { count: indexingCarryoverCount || 0 }
          )}
          {indexingCarryoverUpdatedAt ? (
            <span style={{ marginLeft: 8 }}>
              {t(
                { ja: "更新: {{time}}", en: "Updated: {{time}}" },
                {
                  time: new Date(indexingCarryoverUpdatedAt).toLocaleString(
                    lang === "en" ? "en-US" : "ja-JP",
                    { timeZone: "Asia/Tokyo" }
                  ),
                }
              )}
            </span>
          ) : null}
          <button
            type="button"
            className="btn btn-border"
            onClick={handleClearIndexingCarryover}
            disabled={indexingCarryoverClearing || !indexingCarryoverCount}
            style={{ marginLeft: 8 }}
          >
            {indexingCarryoverClearing
              ? t({ ja: "削除中...", en: "Clearing..." })
              : t({ ja: "繰越を削除", en: "Clear carryover" })}
          </button>
        </div>
        {indexingCarryoverUrls.length > 0 && (
          <div style={{ marginTop: 6, maxHeight: 100, overflowY: "auto", fontSize: 12, color: "var(--muted-text)" }}>
            {indexingCarryoverUrls.slice(0, 20).map((url) => (
              <div key={url}>{url}</div>
            ))}
            {indexingCarryoverUrls.length > 20 && (
              <div>
                {t(
                  { ja: "…他 {{count}} 件", en: "...and {{count}} more" },
                  { count: indexingCarryoverUrls.length - 20 }
                )}
              </div>
            )}
          </div>
        )}
        {indexingUrlItems.length > 0 && (
          <div style={{ marginTop: 6, fontSize: 13, color: "var(--muted-text)" }}>
            {t(
              {
                ja: "登録済み {{indexed}} / 未登録 {{unindexed}} / 不明 {{unknown}}",
                en: "Indexed {{indexed}} / Unindexed {{unindexed}} / Unknown {{unknown}}",
              },
              {
                indexed: indexingSummary.indexed || 0,
                unindexed: indexingSummary.unindexed || 0,
                unknown: indexingSummary.unknown || 0,
              }
            )}
          </div>
        )}
        {indexingUrlItems.length > 0 && (
          <div style={{ marginTop: 8, maxHeight: 140, overflowY: "auto", fontSize: 12 }}>
            {indexingUrlItems.slice(0, 50).map((item) => (
              <div key={item.url}>
                {item.url}{" "}
                <span style={{ color: item.indexed === false ? "#b91c1c" : item.indexed ? "#166534" : "#6b7280" }}>
                  {item.indexed === false
                    ? t({ ja: "(未登録)", en: "(Unindexed)" })
                    : item.indexed === true
                      ? t({ ja: "(登録済み)", en: "(Indexed)" })
                      : t({ ja: "(不明)", en: "(Unknown)" })}
                </span>
                <span style={{ color: "var(--muted-text)", marginLeft: 6 }}>
                  {t(
                    { ja: "score={{score}} view={{view}} type={{type}}", en: "score={{score}} view={{view}} type={{type}}" },
                    {
                      score: Number(item?.score || 0).toFixed(2),
                      view: Number(item?.view_count || 0),
                      type: String(item?.page_type || "-"),
                    }
                  )}
                </span>
              </div>
            ))}
            {indexingUrlItems.length > 50 && (
              <div style={{ color: "var(--muted-text)" }}>
                {t(
                  { ja: "…他 {{count}} 件", en: "...and {{count}} more" },
                  { count: indexingUrlItems.length - 50 }
                )}
              </div>
            )}
          </div>
        )}
        {indexingResult && (
          <div style={{ marginTop: 10, fontSize: 13 }}>
            <div>
              {t(
                {
                  ja: "送信 {{submitted}} 件 / 成功 {{success}} 件 / 失敗 {{failed}} 件",
                  en: "Submitted {{submitted}} / Success {{success}} / Failed {{failed}}",
                },
                {
                  submitted: indexingResult.submitted || 0,
                  success: indexingResult.success || 0,
                  failed: indexingResult.failed || 0,
                }
              )}
            </div>
            <div style={{ marginTop: 4, color: "var(--muted-text)" }}>
              {t(
                {
                  ja: "今回送信試行 {{attempted}} 件 / 繰越 {{carryover}} 件",
                  en: "Attempted {{attempted}} / Carryover {{carryover}}",
                },
                {
                  attempted: Number(indexingResult.attempted || 0),
                  carryover: Number(indexingResult.carryover_count || 0),
                }
              )}
            </div>
          </div>
        )}
      </section>
      <h2 style={{ marginBottom: 16 }}>{t({ ja: "管理画面", en: "Admin" })}</h2>
      <p style={{ marginBottom: 12 }}>
        {t({ ja: "運営向けの管理機能です。", en: "Administration tools for operators." })}
      </p>
      <a href="#admin-contact" style={{ display: "inline-block", marginBottom: 12 }}>
        {t({ ja: "お問い合わせへ", en: "Go to Contact" })}
      </a>
      <Link className="btn btn-border" to="/admin/payouts">
        {t({ ja: "精算管理へ", en: "Go to Payouts" })}
      </Link>
      <Link className="btn btn-border" to="/admin/dashboard" style={{ marginLeft: 8 }}>
        {t({ ja: "支援/振込ダッシュボードへ", en: "Go to Support & Payout Dashboard" })}
      </Link>
      <Link className="btn btn-border" to="/admin/users" style={{ marginLeft: 8 }}>
        {t({ ja: "ユーザー管理へ", en: "Go to Users" })}
      </Link>
      <Link className="btn btn-border" to="/admin/ai-jobs" style={{ marginLeft: 8 }}>
        {t({ ja: "AIジョブ管理へ", en: "Go to AI Jobs" })}
      </Link>
      <Link className="btn btn-border" to="/admin/i18n-jobs" style={{ marginLeft: 8 }}>
        {t({ ja: "UI多言語化ジョブへ", en: "Go to UI I18N Jobs" })}
      </Link>
      <button
        type="button"
        className="btn btn-border"
        onClick={handleLogout}
        style={{ marginLeft: 8 }}
      >
        {t({ ja: "ログアウト", en: "Log out" })}
      </button>
    </div>
  );
}
