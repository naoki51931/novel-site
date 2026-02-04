import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";
import { useI18n } from "../lib/i18n";

export default function AdminAiJobs() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(() => new Set());
  const selectedCount = useMemo(() => selected.size, [selected]);

  const loadJobs = async () => {
    try {
      setLoading(true);
      setError("");
      await apiFetch("/api/admin/auth/me", { credentials: "include" });
      const data = await apiFetch("/api/ai/jobs", { credentials: "include" });
      setJobs(Array.isArray(data) ? data : []);
    } catch (e) {
      if (String(e?.message || "").includes("401")) {
        navigate("/admin/login", { replace: true });
        return;
      }
      setError(e.message || t({ ja: "ジョブ取得に失敗しました。", en: "Failed to load jobs." }));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const toggleSelect = (jobId) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  };

  const handleKillSelected = async () => {
    if (selectedCount === 0) return;
    const ok = window.confirm(
      t(
        {
          ja: "選択したジョブを停止します。よろしいですか？",
          en: "Stop selected jobs?",
        },
        {}
      )
    );
    if (!ok) return;
    try {
      setLoading(true);
      setError("");
      await apiFetch("/api/ai/jobs/kill_selected", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_ids: Array.from(selected) }),
      });
      setSelected(new Set());
      await loadJobs();
    } catch (e) {
      setError(e.message || t({ ja: "停止に失敗しました。", en: "Failed to stop jobs." }));
    } finally {
      setLoading(false);
    }
  };

  const handleKillAll = async () => {
    const ok = window.confirm(
      t(
        {
          ja: "すべての実行中ジョブを停止します。よろしいですか？",
          en: "Stop all running jobs?",
        },
        {}
      )
    );
    if (!ok) return;
    try {
      setLoading(true);
      setError("");
      await apiFetch("/api/ai/jobs/kill_all", {
        method: "POST",
        credentials: "include",
      });
      setSelected(new Set());
      await loadJobs();
    } catch (e) {
      setError(e.message || t({ ja: "停止に失敗しました。", en: "Failed to stop jobs." }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/admin">{t({ ja: "← 管理画面に戻る", en: "← Back to Admin" })}</Link>
      </div>
      <h2 style={{ marginBottom: 8 }}>{t({ ja: "AIジョブ管理", en: "AI Jobs" })}</h2>
      <p style={{ marginTop: 0, marginBottom: 16, color: "var(--muted-text)" }}>
        {t({
          ja: "待機中/実行中のAI小説生成ジョブを停止できます。",
          en: "Stop pending or running AI jobs.",
        })}
      </p>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <button type="button" className="btn btn-border" onClick={loadJobs} disabled={loading}>
          {loading ? t({ ja: "更新中...", en: "Refreshing..." }) : t({ ja: "更新", en: "Refresh" })}
        </button>
        <button
          type="button"
          className="btn btn-border"
          onClick={handleKillSelected}
          disabled={loading || selectedCount === 0}
        >
          {t({ ja: "選択を停止", en: "Stop selected" })}
        </button>
        <button
          type="button"
          className="btn btn-border"
          onClick={handleKillAll}
          disabled={loading}
        >
          {t({ ja: "すべて停止", en: "Stop all" })}
        </button>
      </div>
      {loading ? (
        <div>{t({ ja: "読み込み中...", en: "Loading..." })}</div>
      ) : jobs.length ? (
        <div style={{ display: "grid", gap: 10 }}>
          {jobs.map((job) => (
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
                checked={selected.has(job.id)}
                onChange={() => toggleSelect(job.id)}
              />
              <div>
                <div style={{ fontWeight: 600 }}>
                  #{job.id} / {job.job_type}
                </div>
                <div style={{ fontSize: 12, color: "var(--muted-text)" }}>
                  {t({ ja: "状態", en: "Status" })}: {job.status}
                </div>
                <div style={{ fontSize: 12, color: "var(--muted-text)" }}>
                  {t({ ja: "ユーザーID", en: "User ID" })}: {job.user_id ?? "-"}
                </div>
                <div style={{ fontSize: 12, color: "var(--muted-text)" }}>
                  {t({ ja: "作成", en: "Created" })}: {job.created_at || "-"}
                </div>
              </div>
            </label>
          ))}
        </div>
      ) : (
        <div style={{ color: "var(--muted-text)" }}>
          {t({ ja: "実行中のジョブはありません。", en: "No running jobs." })}
        </div>
      )}
    </div>
  );
}
