import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";

type AdminAiLog = {
  id: number;
  created_at?: string | null;
  model?: string | null;
  tokens_used?: number | null;
  prompt_summary?: string | null;
  user_id?: number | null;
  guest_id?: string | null;
  username?: string | null;
};

function ExpandableText({ text, max = 160 }: { text?: string | null; max?: number }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  if (!text) return <span>-</span>;

  const isLong = text.length > max;
  const displayText = open ? text : text.slice(0, max);

  return (
    <div>
      <span style={{ whiteSpace: "pre-wrap" }}>{displayText}</span>
      {isLong && (
        <button
          type="button"
          onClick={() => setOpen(!open)}
          style={{
            marginLeft: 8,
            fontSize: "0.8rem",
            border: "1px solid #ccc",
            padding: "2px 6px",
            borderRadius: 4,
            background: "#fafafa",
          }}
        >
          {open ? t({ ja: "閉じる ▲", en: "Close ▲" }) : t({ ja: "全文を見る ▼", en: "View all ▼" })}
        </button>
      )}
    </div>
  );
}

export default function AdminAiLogs() {
  const navigate = useNavigate();
  const { t, lang } = useI18n();
  const [logs, setLogs] = useState<AdminAiLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError("");
        await apiFetch("/api/admin/auth/me", { credentials: "include" });
        const data = await apiFetch("/api/admin/ai/logs?limit=200", {
          credentials: "include",
        });
        setLogs(Array.isArray(data) ? data : []);
      } catch (e) {
        if (getErrorMessage(e, "").includes("401")) {
          navigate("/admin/login", { replace: true });
          return;
        }
        setError(
          getErrorMessage(
            e,
            t({ ja: "AI利用履歴の取得に失敗しました。", en: "Failed to load AI usage history." })
          )
        );
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [navigate, t]);

  const formatDateTime = (iso: string | null | undefined) => {
    if (!iso) return "";
    return new Date(iso).toLocaleString(lang === "en" ? "en-US" : "ja-JP", {
      timeZone: "Asia/Tokyo",
    });
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ marginBottom: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Link to="/admin" className="btn btn-border">
          {t({ ja: "← 管理画面に戻る", en: "← Back to Admin" })}
        </Link>
        <Link to="/admin/users" className="btn btn-border">
          {t({ ja: "ユーザー管理へ", en: "Go to Users" })}
        </Link>
      </div>

      <h2>{t({ ja: "AI利用履歴", en: "AI Usage History" })}</h2>
      <p style={{ fontSize: "0.9rem", color: "#666" }}>
        {t({
          ja: "管理者向け一覧です。AI小説生成と翻訳の利用履歴を、ユーザー横断で確認できます。",
          en: "Admin-wide view of AI novel generation and translation usage history across users.",
        })}
      </p>

      {loading && <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>}
      {error && <p style={{ color: "red", marginTop: 8 }}>{error}</p>}

      {!loading && !error && logs.length === 0 && (
        <p style={{ marginTop: 12, color: "#666" }}>
          {t({ ja: "まだ AI 利用履歴がありません。", en: "No AI usage history yet." })}
        </p>
      )}

      {!loading && !error && logs.length > 0 && (
        <div style={{ marginTop: 16, overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "0.9rem",
            }}
          >
            <thead>
              <tr>
                <th style={{ borderBottom: "1px solid #ccc", padding: "4px 6px", textAlign: "left", whiteSpace: "nowrap" }}>
                  {t({ ja: "日時", en: "Date" })}
                </th>
                <th style={{ borderBottom: "1px solid #ccc", padding: "4px 6px", textAlign: "left", whiteSpace: "nowrap" }}>
                  {t({ ja: "ユーザー", en: "User" })}
                </th>
                <th style={{ borderBottom: "1px solid #ccc", padding: "4px 6px", textAlign: "left", whiteSpace: "nowrap" }}>
                  {t({ ja: "モデル", en: "Model" })}
                </th>
                <th style={{ borderBottom: "1px solid #ccc", padding: "4px 6px", textAlign: "right", whiteSpace: "nowrap" }}>
                  {t({ ja: "トークン数", en: "Tokens" })}
                </th>
                <th style={{ borderBottom: "1px solid #ccc", padding: "4px 6px", textAlign: "left" }}>
                  {t({ ja: "利用要約", en: "Summary" })}
                </th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td style={{ borderBottom: "1px solid #eee", padding: "4px 6px", whiteSpace: "nowrap" }}>
                    {formatDateTime(log.created_at)}
                  </td>
                  <td style={{ borderBottom: "1px solid #eee", padding: "4px 6px", whiteSpace: "nowrap" }}>
                    {log.username || (log.guest_id ? `guest:${log.guest_id}` : "-")}
                  </td>
                  <td style={{ borderBottom: "1px solid #eee", padding: "4px 6px", whiteSpace: "nowrap" }}>
                    {log.model || "-"}
                  </td>
                  <td style={{ borderBottom: "1px solid #eee", padding: "4px 6px", textAlign: "right", whiteSpace: "nowrap" }}>
                    {typeof log.tokens_used === "number" ? log.tokens_used : "-"}
                  </td>
                  <td style={{ borderBottom: "1px solid #eee", padding: "4px 6px" }}>
                    <ExpandableText text={log.prompt_summary} max={180} />
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
