import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";
import { formatDateTimeInUserTimeZone } from "../lib/timezone";
import { readShowR18Setting } from "../lib/r18Display";

const API_BASE = getApiBase();
const PAGE_SIZE = 20;

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

export default function ViewHistoryPage() {
  const navigate = useNavigate();
  const { t, lang } = useI18n();
  const [items, setItems] = useState<ViewHistoryNovel[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showR18, setShowR18] = useState(() => readShowR18Setting());

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  useEffect(() => {
    if (!token) {
      navigate("/login");
      return;
    }
    const load = async () => {
      try {
        setLoading(true);
        setError("");
        const params = new URLSearchParams();
        params.set("limit", String(PAGE_SIZE));
        params.set("offset", String((page - 1) * PAGE_SIZE));
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
        setItems(Array.isArray(data.items) ? data.items : []);
        setTotal(Number(data.total) || 0);
      } catch (e) {
        setError(
          getErrorMessage(
            e,
            t({ ja: "閲覧履歴の取得中にエラーが発生しました", en: "An error occurred while loading view history." })
          )
        );
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [navigate, page, t, token]);

  const visibleItems = useMemo(() => {
    if (showR18) return items;
    return items.filter((item) => String(item.age_limit || "all").toLowerCase() !== "r18");
  }, [items, showR18]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const formatDateTime = (iso: string | null | undefined) =>
    formatDateTimeInUserTimeZone(iso, lang === "en" ? "en-US" : "ja-JP");

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <div style={{ marginBottom: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Link to="/mypage" className="btn btn-border">
          {t({ ja: "← マイページへ戻る", en: "← Back to My Page" })}
        </Link>
      </div>
      <h2>{t({ ja: "閲覧履歴", en: "View History" })}</h2>
      <p style={{ color: "var(--muted-text)", marginTop: 0 }}>
        {t({
          ja: "最近閲覧した小説の履歴です。20件ずつ表示します。",
          en: "History of recently viewed novels, shown 20 items per page.",
        })}
      </p>

      <div style={{ marginBottom: 12 }}>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={showR18}
            onChange={(e) => setShowR18(e.target.checked)}
          />
          <span>{t({ ja: "R18作品を表示", en: "Show R18 works" })}</span>
        </label>
      </div>

      {loading && <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}
      {!loading && !error && visibleItems.length === 0 && (
        <p style={{ color: "var(--muted-text)" }}>
          {t({ ja: "閲覧履歴はまだありません。", en: "No view history yet." })}
        </p>
      )}

      {!loading && !error && visibleItems.length > 0 && (
        <div style={{ display: "grid", gap: 12, marginTop: 14 }}>
          {visibleItems.map((item) => (
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
                <span>{t({ ja: "最終閲覧", en: "Last viewed" })}: {formatDateTime(item.viewed_at)}</span>
                {item.age_limit ? <span>{String(item.age_limit).toUpperCase()}</span> : null}
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && !error && totalPages > 1 && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 16, flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => setPage((prev) => Math.max(1, prev - 1))}
            disabled={page <= 1}
          >
            {t({ ja: "前へ", en: "Prev" })}
          </button>
          <span style={{ fontSize: 13, color: "var(--muted-text)" }}>
            {t({ ja: "{{page}} / {{total}} ページ", en: "Page {{page}} / {{total}}" }, { page, total: totalPages })}
          </span>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
            disabled={page >= totalPages}
          >
            {t({ ja: "次へ", en: "Next" })}
          </button>
        </div>
      )}
    </div>
  );
}
