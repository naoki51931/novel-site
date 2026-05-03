import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";

const API_BASE = getApiBase();

// 要約などの長文を折りたたみ/展開するコンポーネント
type AiLog = {
  id: number;
  created_at?: string | null;
  model?: string | null;
  tokens_used?: number | null;
  summary?: string | null;
  prompt_summary?: string | null;
};

function ExpandableText({ text, max = 120 }: { text?: string | null; max?: number }) {
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

export default function AiLogsPage() {
  const navigate = useNavigate();
  const { t, lang } = useI18n();
  const [logs, setLogs] = useState<AiLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setError(t({ ja: "ログインが必要です。", en: "Login required." }));
      setLoading(false);
      return;
    }

    (async () => {
      try {
        setLoading(true);
        setError("");

        const res = await fetch(`${API_BASE}/api/ai/logs/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(
            data.detail ||
              t(
                { ja: "AI利用履歴の取得に失敗しました (status={{status}})", en: "Failed to load AI usage history (status={{status}})" },
                { status: res.status }
              )
          );
        }

        const data = await res.json().catch(() => []);
        if (Array.isArray(data)) {
          setLogs(data);
        } else {
          setLogs([]);
        }
      } catch (error) {
        console.error(error);
        setError(
          getErrorMessage(
            error,
            t({ ja: "AI利用履歴の取得中にエラーが発生しました", en: "An error occurred while loading AI history." })
          )
        );
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const formatDateTime = (iso: string | null | undefined) => {
    if (!iso) return "";
    return new Date(iso).toLocaleString(lang === "en" ? "en-US" : "ja-JP", {
      timeZone: "Asia/Tokyo",
    });
  };

  return (
    <div>
      <div style={{ marginBottom: 12, display: "flex", gap: 8 }}>
        <button className="btn btn-border" onClick={() => navigate("/ai-novel")}>
          {t({ ja: "← 戻る", en: "← Back" })}
        </button>
        <Link to="/" className="btn btn-border">
          {t({ ja: "トップへ", en: "Home" })}
        </Link>
        <Link to="/ai-novel" className="btn btn-border">
          {t({ ja: "AI小説生成へ", en: "Go to AI Novel" })}
        </Link>
      </div>

      <h2>{t({ ja: "AI利用履歴", en: "AI Usage History" })}</h2>
      <p style={{ fontSize: "0.9rem", color: "#666" }}>
        {t({
          ja: "過去に実行した AI 小説生成の履歴です。日付・モデル・要約を確認できます。",
          en: "History of AI novel generations. Check date, model, and summary.",
        })}
      </p>

      {loading && <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>}

      {error && (
        <p style={{ color: "red", marginTop: 8, marginBottom: 8 }}>{error}</p>
      )}

      {!loading && !error && logs.length === 0 && (
        <p style={{ marginTop: 12, color: "#666" }}>
          {t({ ja: "まだ AI 小説生成の履歴がありません。", en: "No AI generation history yet." })}
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
                <th
                  style={{
                    borderBottom: "1px solid #ccc",
                    padding: "4px 6px",
                    textAlign: "left",
                    whiteSpace: "nowrap",
                  }}
                >
                  {t({ ja: "日時", en: "Date" })}
                </th>
                <th
                  style={{
                    borderBottom: "1px solid #ccc",
                    padding: "4px 6px",
                    textAlign: "left",
                    whiteSpace: "nowrap",
                  }}
                >
                  {t({ ja: "モデル", en: "Model" })}
                </th>
                <th
                  style={{
                    borderBottom: "1px solid #ccc",
                    padding: "4px 6px",
                    textAlign: "right",
                    whiteSpace: "nowrap",
                  }}
                >
                  {t({ ja: "トークン数", en: "Tokens" })}
                </th>
                <th
                  style={{
                    borderBottom: "1px solid #ccc",
                    padding: "4px 6px",
                    textAlign: "left",
                  }}
                >
                  {t({ ja: "利用要約", en: "Summary" })}
                </th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td
                    style={{
                      borderBottom: "1px solid #eee",
                      padding: "4px 6px",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {formatDateTime(log.created_at)}
                  </td>
                  <td
                    style={{
                      borderBottom: "1px solid #eee",
                      padding: "4px 6px",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {log.model || "-"}
                  </td>
                  <td
                    style={{
                      borderBottom: "1px solid #eee",
                      padding: "4px 6px",
                      textAlign: "right",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {typeof log.tokens_used === "number"
                      ? log.tokens_used
                      : "-"}
                  </td>
                  <td
                    style={{
                      borderBottom: "1px solid #eee",
                      padding: "4px 6px",
                    }}
                  >
                    <ExpandableText text={log.prompt_summary} max={160} />
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
