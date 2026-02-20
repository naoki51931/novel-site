import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";
import { useI18n } from "../lib/i18n";
import pretranslated from "../lib/i18nPretranslated.json";

function buildSourceItems() {
  const texts = new Set();
  for (const lang of ["zh-cn", "zh-tw", "ko"]) {
    const entries = pretranslated?.[lang];
    if (!entries || typeof entries !== "object") continue;
    for (const key of Object.keys(entries)) {
      const text = String(key || "").trim();
      if (!text) continue;
      texts.add(text);
    }
  }
  return Array.from(texts).map((text) => ({ source_lang: "ja", text }));
}

export default function AdminI18nJobs() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const sourceItems = useMemo(() => buildSourceItems(), []);
  const [jobs, setJobs] = useState([]);
  const [activeJobId, setActiveJobId] = useState("");
  const [activeJob, setActiveJob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const pollTimerRef = useRef(null);
  const activeJobIdRef = useRef("");

  const clearPoll = () => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  useEffect(() => {
    activeJobIdRef.current = String(activeJobId || "");
  }, [activeJobId]);

  const loadJobs = async () => {
    const data = await apiFetch("/api/admin/i18n/jobs?limit=20", {
      credentials: "include",
    });
    const list = Array.isArray(data) ? data : [];
    setJobs(list);
    if (!activeJobId && list.length) {
      setActiveJobId(String(list[0]?.job_id || ""));
    }
  };

  const loadJobDetail = async (jobId) => {
    if (!jobId) return;
    const data = await apiFetch(`/api/admin/i18n/jobs/${encodeURIComponent(jobId)}`, {
      credentials: "include",
    });
    if (String(jobId) !== activeJobIdRef.current) return;
    setActiveJob(data || null);
    if (["pending", "running"].includes(String(data?.status || ""))) {
      clearPoll();
      pollTimerRef.current = setTimeout(() => {
        loadJobDetail(jobId).catch(() => {});
      }, 2500);
    }
  };

  useEffect(() => {
    const boot = async () => {
      try {
        setLoading(true);
        await apiFetch("/api/admin/auth/me", { credentials: "include" });
        await loadJobs();
      } catch (e) {
        if (String(e?.message || "").includes("401")) {
          navigate("/admin/login", { replace: true });
          return;
        }
        setError(e?.message || t({ ja: "読み込みに失敗しました。", en: "Failed to load." }));
      } finally {
        setLoading(false);
      }
    };
    boot();
    return () => clearPoll();
  }, []);

  useEffect(() => {
    if (!activeJobId) return;
    clearPoll();
    loadJobDetail(activeJobId).catch((e) => {
      setError(e?.message || t({ ja: "ジョブ取得に失敗しました。", en: "Failed to load job." }));
    });
  }, [activeJobId]);

  const startJob = async () => {
    if (!sourceItems.length) {
      setError(t({ ja: "翻訳元テキストがありません。", en: "No source texts." }));
      return;
    }
    const currentStatus = String(activeJob?.status || "");
    const resumeFromJobId =
      activeJobId && ["failed", "canceled"].includes(currentStatus) ? String(activeJobId) : "";
    try {
      setStarting(true);
      setError("");
      const data = await apiFetch("/api/admin/i18n/jobs/start", {
        method: "POST",
        credentials: "include",
        body: {
          source_items: sourceItems,
          target_langs: ["zh-cn", "zh-tw", "ko"],
          batch_size: 10,
          notify_username: "demo02",
          ...(resumeFromJobId ? { resume_from_job_id: resumeFromJobId } : {}),
        },
      });
      const jobId = String(data?.job_id || "");
      if (jobId) {
        setActiveJobId(jobId);
      }
      await loadJobs();
    } catch (e) {
      setError(e?.message || t({ ja: "開始に失敗しました。", en: "Failed to start." }));
    } finally {
      setStarting(false);
    }
  };

  const cancelJob = async () => {
    if (!activeJobId) return;
    try {
      await apiFetch(`/api/admin/i18n/jobs/${encodeURIComponent(activeJobId)}/cancel`, {
        method: "POST",
        credentials: "include",
      });
      await loadJobDetail(activeJobId);
      await loadJobs();
    } catch (e) {
      setError(e?.message || t({ ja: "停止に失敗しました。", en: "Failed to cancel." }));
    }
  };

  const refreshNow = async () => {
    try {
      setLoading(true);
      setError("");
      await loadJobs();
      if (activeJobId) {
        await loadJobDetail(activeJobId);
      }
    } catch (e) {
      setError(e?.message || t({ ja: "更新に失敗しました。", en: "Failed to refresh." }));
    } finally {
      setLoading(false);
    }
  };

  const percent = useMemo(() => {
    const done = Number(activeJob?.processed_chunks || 0);
    const total = Number(activeJob?.total_chunks || 0);
    if (!total) return 0;
    return Math.max(0, Math.min(100, Math.round((done / total) * 100)));
  }, [activeJob]);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/admin">{t({ ja: "← 管理画面に戻る", en: "← Back to Admin" })}</Link>
      </div>
      <h2>{t({ ja: "UI多言語化ジョブ", en: "UI I18N Jobs" })}</h2>
      <p style={{ color: "var(--muted-text)" }}>
        {t(
          {
            ja: "UI文言をバックグラウンドで翻訳し、進捗表示します。完了時に demo02 へ通知します。",
            en: "Translate UI texts in background with progress. Notify demo02 when done.",
          },
          {}
        )}
      </p>

      {error && <div style={{ color: "red", marginBottom: 8 }}>{error}</div>}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <button type="button" className="btn btn-border" onClick={startJob} disabled={starting || loading}>
          {starting
            ? t({ ja: "開始中...", en: "Starting..." })
            : activeJobId && ["failed", "canceled"].includes(String(activeJob?.status || ""))
            ? t({ ja: "選択ジョブから再開", en: "Resume Selected Job" })
            : t({ ja: "ジョブ開始", en: "Start Job" })}
        </button>
        <button type="button" className="btn btn-border" onClick={refreshNow} disabled={loading}>
          {loading ? t({ ja: "更新中...", en: "Refreshing..." }) : t({ ja: "更新", en: "Refresh" })}
        </button>
        <button
          type="button"
          className="btn btn-border"
          onClick={cancelJob}
          disabled={!activeJobId || !["pending", "running"].includes(String(activeJob?.status || ""))}
        >
          {t({ ja: "現在ジョブを停止", en: "Cancel Active Job" })}
        </button>
      </div>

      <div style={{ marginBottom: 16, fontSize: 13, color: "var(--muted-text)" }}>
        {t({ ja: "翻訳元テキスト数", en: "Source texts" })}: {sourceItems.length}
      </div>

      {activeJob && (
        <div
          style={{
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: 12,
            background: "var(--surface)",
            marginBottom: 14,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 6 }}>
            #{activeJob.job_id} / {activeJob.status}
          </div>
          <div style={{ fontSize: 13, color: "var(--muted-text)" }}>
            {t({ ja: "進捗", en: "Progress" })}: {activeJob.processed_chunks || 0}/{activeJob.total_chunks || 0} ({percent}%)
          </div>
          <div style={{ fontSize: 13, color: "var(--muted-text)" }}>
            {t({ ja: "翻訳済み", en: "Translated" })}: {activeJob.translated_count || 0} / {t({ ja: "失敗", en: "Failed" })}: {activeJob.failed_count || 0}
          </div>
          <div style={{ fontSize: 13, color: "var(--muted-text)" }}>
            {t({ ja: "現在", en: "Current" })}: {(activeJob.current_source_lang || "-")} → {(activeJob.current_target_lang || "-")}
          </div>
        </div>
      )}

      <div style={{ display: "grid", gap: 8 }}>
        {jobs.map((job) => (
          <button
            key={job.job_id}
            type="button"
            className="btn btn-border"
            onClick={() => setActiveJobId(String(job.job_id))}
            style={{
              textAlign: "left",
              borderColor:
                String(activeJobId || "") === String(job.job_id || "") ? "var(--accent, #2d6cdf)" : undefined,
              background:
                String(activeJobId || "") === String(job.job_id || "") ? "var(--surface-2, #f6f8fb)" : undefined,
            }}
          >
            #{job.job_id} / {job.status} / {job.processed_chunks || 0}/{job.total_chunks || 0}
          </button>
        ))}
      </div>
    </div>
  );
}
