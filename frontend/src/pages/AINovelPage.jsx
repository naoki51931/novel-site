// frontend/src/pages/AINovelPage.jsx
import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getStoredLanguage, translate, useI18n } from "../lib/i18n";
import { applyPolishReplacement, buildPolishPrompt } from "../lib/aiPolish.mjs";

/**
 * 既存プロジェクトで JWT をどこに保存しているかに合わせてここを調整する
 * 例:
 * - localStorage.getItem("token")
 * - localStorage.getItem("access_token")
 * - cookie など
 */
function getAuthToken() {
  return localStorage.getItem("access_token") || localStorage.getItem("token");
}

const PENDING_AI_POST_KEY = "pending_ai_post_v1";
const PENDING_AI_POST_ERROR_KEY = "pending_ai_post_error_v1";
const AI_NOVEL_DRAFT_KEY = "draft_ai_novel_v1";
const PENDING_AI_JOB_KEY = "pending_ai_job_v1";

function savePendingAiPost(data) {
  try {
    localStorage.setItem(PENDING_AI_POST_KEY, JSON.stringify(data));
  } catch {
    // ignore
  }
}

function loadPendingAiPost() {
  try {
    const raw = localStorage.getItem(PENDING_AI_POST_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function consumePendingAiPostError() {
  try {
    const msg = localStorage.getItem(PENDING_AI_POST_ERROR_KEY);
    if (!msg) return null;
    localStorage.removeItem(PENDING_AI_POST_ERROR_KEY);
    return msg;
  } catch {
    return null;
  }
}

function savePendingAiJob(data) {
  try {
    localStorage.setItem(PENDING_AI_JOB_KEY, JSON.stringify(data));
  } catch {
    // ignore
  }
}

function loadPendingAiJob() {
  try {
    const raw = localStorage.getItem(PENDING_AI_JOB_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function clearPendingAiJob() {
  try {
    localStorage.removeItem(PENDING_AI_JOB_KEY);
  } catch {
    // ignore
  }
}

function notifyAndroidAiResult({ title = "", body = "", url = "" } = {}) {
  try {
    if (typeof window === "undefined") return;
    const bridge = window.AndroidFormBridge;
    if (!bridge || typeof bridge.notifyAiGeneration !== "function") return;
    bridge.notifyAiGeneration(
      JSON.stringify({
        title: String(title || ""),
        body: String(body || ""),
        url: String(url || ""),
      })
    );
  } catch {
    // ignore
  }
}

function normalizeAINovelResponse(data) {
  if (!data || typeof data !== "object") return data;
  if (typeof data.body !== "string") return data;

  const raw = data.body.trim();
  if (!raw) return data;

  const stripFence = (s) => {
    const t = (s || "").trim();
    if (!t.startsWith("```")) return t;
    const lines = t.split("\n");
    if (lines.length && lines[0].startsWith("```")) lines.shift();
    if (lines.length && lines[lines.length - 1].trim() === "```") lines.pop();
    return lines.join("\n").trim();
  };

  const tryParse = (s) => {
    const cleaned = stripFence(s);
    if (!cleaned.startsWith("{")) return null;
    try {
      const parsed = JSON.parse(cleaned);
      if (parsed && typeof parsed === "object") return parsed;
    } catch {
      // ignore
    }
    return null;
  };

  const parsed =
    tryParse(raw) ||
    (raw.includes('\\"') ? tryParse(raw.replace(/\\"/g, '"')) : null);

  if (!parsed) return data;

  const title =
    data.generated_title ||
    parsed.title ||
    parsed.generated_title ||
    parsed.generatedTitle ||
    translate({ ja: "タイトル未設定", en: "Untitled" }, getStoredLanguage());
  const body = parsed.body || parsed.text || parsed.content || parsed.story || data.body;

  return { ...data, generated_title: title, body };
}

function getJwtUserId(token) {
  try {
    if (!token) return null;
    const parts = token.split(".");
    if (parts.length < 2) return null;
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "===".slice((base64.length + 3) % 4);
    const json = atob(padded);
    const payload = JSON.parse(json);
    const sub = payload?.sub;
    if (sub === undefined || sub === null) return null;
    const n = Number(sub);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i += 1) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

function uint8ArrayToBase64Url(bytes) {
  if (!bytes || !bytes.length) return "";
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function pushDebug(token, stage, detail = "") {
  try {
    const headers = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    await fetch("/api/push/debug", {
      method: "POST",
      headers,
      body: JSON.stringify({ stage, detail: String(detail || "") }),
    });
  } catch {
    // ignore
  }
}

async function ensureWebPushSubscription(token, onStatus = null) {
  const report = (stage, detail = "", ok = null) => {
    if (typeof onStatus === "function") onStatus({ stage, detail, ok, at: Date.now() });
  };
  if (typeof window === "undefined") return;
  if (window.location.protocol !== "https:" && window.location.hostname !== "localhost") {
    console.warn("web push requires https");
    await pushDebug(token, "skip_insecure_context", window.location.href || "");
    report("skip_insecure_context", window.location.href || "", false);
    return;
  }
  if (!("Notification" in window)) return;
  if (!("serviceWorker" in navigator)) return;
  if (!("PushManager" in window)) return;

  let permission = Notification.permission;
  if (permission === "default") {
    try {
      permission = await Notification.requestPermission();
    } catch {
      report("permission_request_failed", "", false);
      return;
    }
  }
  if (permission !== "granted") {
    report("permission_not_granted", permission, false);
    return;
  }
  await pushDebug(token, "permission_granted", permission);
  report("permission_granted", permission, null);

  try {
    const reg = await navigator.serviceWorker.register("/sw.js");
    await navigator.serviceWorker.ready;
    await pushDebug(token, "sw_ready", reg?.scope || "");
    report("sw_ready", reg?.scope || "", null);
    const keyRes = await fetch("/api/push/public_key");
    if (!keyRes.ok) {
      console.warn("push public key request failed", keyRes.status);
      await pushDebug(token, "public_key_failed", String(keyRes.status));
      report("public_key_failed", String(keyRes.status), false);
      return;
    }
    const keyData = await keyRes.json().catch(() => ({}));
    if (!keyData?.enabled || !keyData?.public_key) {
      console.warn("push is disabled on backend");
      await pushDebug(token, "public_key_disabled", JSON.stringify(keyData || {}));
      report("public_key_disabled", JSON.stringify(keyData || {}), false);
      return;
    }
    await pushDebug(token, "public_key_ok", "enabled=true");
    report("public_key_ok", "enabled=true", null);

    let subscription = await reg.pushManager.getSubscription();
    if (!subscription) {
      let lastErr = null;
      for (let i = 0; i < 3; i += 1) {
        try {
          const keyBytes = urlBase64ToUint8Array(keyData.public_key);
          const appServerKey =
            i === 0
              ? keyBytes
              : i === 1
                ? keyBytes.buffer
                : new Uint8Array(keyBytes).buffer;
          subscription = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: appServerKey,
          });
          break;
        } catch (e) {
          lastErr = e;
          if (e?.name !== "AbortError" && e?.name !== "TypeError") break;
          await pushDebug(token, "subscribe_abort_retry", `attempt=${i + 1}`);
          report("subscribe_abort_retry", `attempt=${i + 1}`, null);
          await new Promise((resolve) => setTimeout(resolve, 1000));
          subscription = await reg.pushManager.getSubscription();
          if (subscription) break;
        }
      }
      if (!subscription && lastErr) throw lastErr;
    }
    if (!subscription) {
      report("subscription_not_created", "", false);
      return;
    }
    const raw = subscription.toJSON ? subscription.toJSON() : {};
    const endpoint = raw?.endpoint || subscription.endpoint || "";
    const p256dhFromRaw = raw?.keys?.p256dh || "";
    const authFromRaw = raw?.keys?.auth || "";
    const p256dhKey = subscription.getKey ? subscription.getKey("p256dh") : null;
    const authKey = subscription.getKey ? subscription.getKey("auth") : null;
    const p256dh =
      p256dhFromRaw || (p256dhKey ? uint8ArrayToBase64Url(new Uint8Array(p256dhKey)) : "");
    const auth =
      authFromRaw || (authKey ? uint8ArrayToBase64Url(new Uint8Array(authKey)) : "");
    if (!endpoint || !p256dh || !auth) {
      console.warn("push subscription payload is incomplete");
      await pushDebug(token, "subscription_payload_incomplete", JSON.stringify({ endpoint: Boolean(endpoint), p256dh: Boolean(p256dh), auth: Boolean(auth) }));
      report("subscription_payload_incomplete", JSON.stringify({ endpoint: Boolean(endpoint), p256dh: Boolean(p256dh), auth: Boolean(auth) }), false);
      return;
    }
    await pushDebug(token, "subscription_payload_ok", endpoint.slice(0, 80));
    report("subscription_payload_ok", endpoint.slice(0, 80), null);
    const payload = { endpoint, keys: { p256dh, auth } };

    const headers = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const subRes = await fetch("/api/push/subscribe", {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (!subRes.ok) {
      console.warn("push subscribe failed", subRes.status);
      await pushDebug(token, "subscribe_failed", String(subRes.status));
      report("subscribe_failed", String(subRes.status), false);
      return;
    }
    await pushDebug(token, "subscribe_ok", "ok");
    report("subscribe_ok", "ok", true);
  } catch (e) {
    console.error("failed to subscribe web push", e);
    await pushDebug(
      token,
      "subscribe_exception",
      `${e?.name || "Error"}:${e?.message || String(e)}`
    );
    report("subscribe_exception", `${e?.name || "Error"}:${e?.message || String(e)}`, false);
  }
}

export default function AINovelPage() {
  const { t, lang } = useI18n();
  const [titleHint, setTitleHint] = useState("");
  const [genre, setGenre] = useState("");
  const [characters, setCharacters] = useState("");
  const [tone, setTone] = useState("");
  const [length, setLength] = useState("medium");
  const [model, setModel] = useState("gpt-4.1-mini");
  const [isR18, setIsR18] = useState(false);
  const [retryMode, setRetryMode] = useState(false);
  const [retryMax, setRetryMax] = useState(2);
  const [retryAttempts, setRetryAttempts] = useState(0);
  const [activeRetryMax, setActiveRetryMax] = useState(null);

  // ★ ここが「続き生成モード」用の state
  const [isContinueMode, setIsContinueMode] = useState(false);
  const [episodeId, setEpisodeId] = useState(null);
  const [continueNovelId, setContinueNovelId] = useState(null);
  const [continueEpisodeNumber, setContinueEpisodeNumber] = useState(null);
  const [canPostToContinueNovel, setCanPostToContinueNovel] = useState(null); // null=判定中, true/false
  const [continueInfoError, setContinueInfoError] = useState("");
  const [isEditMode, setIsEditMode] = useState(false);
  const [editSourceBody, setEditSourceBody] = useState("");

  const [loading, setLoading] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const [autoFillLoading, setAutoFillLoading] = useState(false);
  const [posting, setPosting] = useState(false);
  const [polishing, setPolishing] = useState(false);
  const [polishIntensity, setPolishIntensity] = useState(50);
  const [lastPolishContext, setLastPolishContext] = useState(null);
  const [hasActiveSelection, setHasActiveSelection] = useState(false);
  const [polishPreview, setPolishPreview] = useState(null);
  const [error, setError] = useState("");
  const [quotaError, setQuotaError] = useState("");
  const [premiumError, setPremiumError] = useState("");
  const [autoFillError, setAutoFillError] = useState("");
  const [autoFillPreview, setAutoFillPreview] = useState(null);
  const [guestRemaining, setGuestRemaining] = useState(null);
  const [userRemaining, setUserRemaining] = useState(null);
  const [result, setResult] = useState(null);
  const [continuationBody, setContinuationBody] = useState("");
  const [postEpisodeTitle, setPostEpisodeTitle] = useState("");
  const [lastGenerateParams, setLastGenerateParams] = useState(null);
  const [draftSlots, setDraftSlots] = useState([]);
  const [draftSlotsLoading, setDraftSlotsLoading] = useState(false);
  const [draftSlotsError, setDraftSlotsError] = useState("");
  const [selectedDraftId, setSelectedDraftId] = useState("");
  const [draftTitle, setDraftTitle] = useState("");
  const [hasContinuationAttempted, setHasContinuationAttempted] = useState(false);
  const [redoContinuationArmed, setRedoContinuationArmed] = useState(false);
  const [textEditMode, setTextEditMode] = useState(false);
  const [textEditValue, setTextEditValue] = useState("");
  const [textEditOriginal, setTextEditOriginal] = useState("");
  const [isPushDebugUser, setIsPushDebugUser] = useState(false);
  const [pushDebugInfo, setPushDebugInfo] = useState({
    stage: "idle",
    detail: "",
    ok: null,
    at: 0,
  });

  const fetchWithTimeout = async (url, options, timeoutMs) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { ...options, signal: controller.signal });
    } finally {
      clearTimeout(timeoutId);
    }
  };

  const isAbortError = (err) => err && (err.name === "AbortError" || err.code === "ABORT_ERR");

  const countChars = (value) => (value || "").length;
  const showRetryStatus =
    (loading || continuing) &&
    ((typeof activeRetryMax === "number" && activeRetryMax > 0) ||
      (activeRetryMax === null && retryMode && retryMax > 0));
  const displayRetryMax =
    typeof activeRetryMax === "number" ? activeRetryMax : retryMode ? retryMax : null;

  const navigate = useNavigate();
  const resultBodyRef = useRef(null);
  const charactersInputRef = useRef(null);
  const combinedBodyRef = useRef("");
  const lastSelectionContextRef = useRef(null);
  const jobPollTimerRef = useRef(null);
  const activeJobSessionRef = useRef(0);
  const localDraftRef = useRef(null);
  const draftSaveTimerRef = useRef(null);
  const hasUserInputRef = useRef(false);
  const [pendingJob, setPendingJob] = useState(null);
  const hasAuthToken = Boolean(getAuthToken());
  const markUserInput = () => {
    hasUserInputRef.current = true;
  };

  useEffect(() => {
    const fetchRemaining = async () => {
      try {
        const token = getAuthToken();
        const res = await fetch("/api/ai/novels/remaining", {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) return;
        if (typeof data?.guest_remaining === "number") {
          setGuestRemaining(data.guest_remaining);
        } else {
          setGuestRemaining(null);
        }
        if (typeof data?.user_remaining === "number") {
          setUserRemaining(data.user_remaining);
        } else {
          setUserRemaining(null);
        }
      } catch (e) {
        console.error("failed to load ai remaining", e);
      }
    };

    fetchRemaining();
  }, []);

  const stopJobPolling = () => {
    if (jobPollTimerRef.current) {
      clearTimeout(jobPollTimerRef.current);
      jobPollTimerRef.current = null;
    }
  };

  const extractDraftTimestamp = (draft) => {
    if (!draft) return 0;
    const raw = draft.saved_at || draft.savedAt || null;
    if (!raw) return 0;
    const ts = Date.parse(raw);
    return Number.isFinite(ts) ? ts : 0;
  };

  const applyDraft = (draft) => {
    if (!draft || typeof draft !== "object") return;
    const draftEpisodeId =
      typeof draft.episodeId === "number" || typeof draft.episodeId === "string"
        ? draft.episodeId
        : null;
    if (typeof draft.titleHint === "string") setTitleHint(draft.titleHint);
    if (typeof draft.genre === "string") setGenre(draft.genre);
    if (typeof draft.characters === "string") setCharacters(draft.characters);
    if (typeof draft.tone === "string") setTone(draft.tone);
    if (typeof draft.length === "string") setLength(draft.length);
    if (typeof draft.model === "string") setModel(draft.model);
    if (typeof draft.isR18 === "boolean") setIsR18(draft.isR18);
    if (typeof draft.retryMode === "boolean") setRetryMode(draft.retryMode);
    if (typeof draft.retryMax === "number") setRetryMax(draft.retryMax);
    if (typeof draft.isContinueMode === "boolean") {
      setIsContinueMode(Boolean(draft.isContinueMode && draftEpisodeId !== null));
    }
    setEpisodeId(draftEpisodeId);
    if (typeof draft.continueNovelId === "number" || draft.continueNovelId === null)
      setContinueNovelId(draft.continueNovelId);
    if (typeof draft.continueEpisodeNumber === "number" || draft.continueEpisodeNumber === null)
      setContinueEpisodeNumber(draft.continueEpisodeNumber);
    if (typeof draft.isEditMode === "boolean") setIsEditMode(draft.isEditMode);
    if (typeof draft.editSourceBody === "string") setEditSourceBody(draft.editSourceBody);
    if (draft.result && typeof draft.result === "object") setResult(draft.result);
    if (typeof draft.continuationBody === "string") setContinuationBody(draft.continuationBody);
    if (typeof draft.postEpisodeTitle === "string") setPostEpisodeTitle(draft.postEpisodeTitle);
    if (draft.lastGenerateParams && typeof draft.lastGenerateParams === "object") {
      setLastGenerateParams(draft.lastGenerateParams);
    }
  };

  const buildDraftPayload = () => ({
    titleHint,
    genre,
    characters,
    tone,
    length,
    model,
    isR18,
    retryMode,
    retryMax,
    isContinueMode,
    episodeId,
    continueNovelId,
    continueEpisodeNumber,
    isEditMode,
    editSourceBody,
    result,
    continuationBody,
    postEpisodeTitle,
    lastGenerateParams,
    saved_at: new Date().toISOString(),
  });

  const buildDefaultDraftTitle = () => {
    const base = (draftTitle || "").trim() || (result?.generated_title || "").trim() || (titleHint || "").trim();
    if (base) return base;
    const stamp = new Date().toISOString().slice(0, 16).replace("T", " ");
    return t({ ja: `AI生成 ${stamp}`, en: `AI Draft ${stamp}` });
  };

  const handleSelectDraftSlot = (value) => {
    setSelectedDraftId(value);
    const match = draftSlots.find((item) => String(item.id) === String(value));
    if (match && typeof match.title === "string") {
      setDraftTitle(match.title);
    }
  };

  const handleJobResult = (job, payload) => {
    if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted") {
      const titleText =
        job?.kind === "continuation"
          ? t({ ja: "続き生成が完了しました", en: "Continuation is ready" })
          : t({ ja: "AI小説生成が完了しました", en: "AI novel is ready" });
      try {
        new Notification(titleText);
      } catch {
        // ignore
      }
    }
    if (payload && typeof payload === "object") {
      if (typeof payload.guest_remaining === "number") {
        setGuestRemaining(payload.guest_remaining);
      } else {
        setGuestRemaining(null);
      }
      if (typeof payload.user_remaining === "number") {
        setUserRemaining(payload.user_remaining);
      } else {
        setUserRemaining(null);
      }
    }
    if (job?.kind === "continuation") {
      const data = normalizeAINovelResponse(payload || {});
      const nextBody = (data?.body || "").trim();
      if (nextBody) {
        setContinuationBody((prev) => (prev ? `${prev}\n\n${nextBody}` : nextBody));
      }
      notifyAndroidAiResult({
        title: t({ ja: "続き生成が完了しました", en: "Continuation is ready" }),
        body: nextBody.slice(0, 120),
        url: "/ai-novel",
      });
      setContinuing(false);
      setRetryAttempts(0);
      setActiveRetryMax(null);
      return;
    }
    const normalized = normalizeAINovelResponse(payload || {});
    setResult(normalized);
    notifyAndroidAiResult({
      title:
        normalized?.generated_title ||
        t({ ja: "AI小説生成が完了しました", en: "AI novel is ready" }),
      body: String(normalized?.body || "").slice(0, 120),
      url: "/ai-novel",
    });
    setLoading(false);
    setRetryAttempts(0);
    setActiveRetryMax(null);
  };

  const pollAiJob = async (job, sessionId = activeJobSessionRef.current) => {
    if (!job || !job.job_id) return;
    if (sessionId !== activeJobSessionRef.current) return;
    const startedAt = Number(job.started_at || 0);
    if (startedAt && Date.now() - startedAt > 60 * 60 * 1000) {
      setError(
        t({
          ja: "生成待機が長時間続いています。通信を再試行中です。画面を閉じても完了時に通知されます。",
          en: "Generation is taking longer than usual. Retrying in background. You will be notified when it completes.",
        })
      );
      jobPollTimerRef.current = setTimeout(() => pollAiJob(job, sessionId), 5000);
      return;
    }
    const token = getAuthToken();
    try {
      const res = await fetchWithTimeout(
        `/api/ai/jobs/${job.job_id}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
        15000
      );

      if (res.status === 401 && token) {
        setError(
          t({
            ja: "ログインの有効期限が切れています。再ログインしてください。",
            en: "Your session has expired. Please log in again.",
          })
        );
        setTimeout(() => navigate("/login"), 800);
        stopJobPolling();
        setLoading(false);
        setContinuing(false);
        setRetryAttempts(0);
        setActiveRetryMax(null);
        clearPendingAiJob();
        setPendingJob(null);
        return;
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (res.status >= 500) {
          setError(
            t({
              ja: "サーバー応答が不安定なため再試行しています。画面を閉じても完了時に通知されます。",
              en: "Server response is unstable. Retrying. You will be notified when it completes.",
            })
          );
          jobPollTimerRef.current = setTimeout(() => pollAiJob(job, sessionId), 4000);
          return;
        }
        const message =
          data?.detail ||
          t(
            { ja: "生成状況の取得に失敗しました (status={{status}})", en: "Failed to load status (status={{status}})" },
            { status: res.status }
          );
        if (res.status === 404) {
          setError(
            t({
              ja: "生成ジョブが見つかりませんでした。もう一度生成をやり直してください。",
              en: "The job was not found. Please start generation again.",
            })
          );
        } else {
          setError(message);
        }
        stopJobPolling();
        setLoading(false);
        setContinuing(false);
        setRetryAttempts(0);
        setActiveRetryMax(null);
        clearPendingAiJob();
        setPendingJob(null);
        return;
      }

      const data = await res.json();
      if (typeof data?.retry_attempts === "number") {
        setRetryAttempts(data.retry_attempts);
      }
      if (typeof data?.retry_max === "number") {
        setActiveRetryMax(data.retry_max);
      }
      if (data.status === "succeeded") {
        handleJobResult(job, data.response);
        stopJobPolling();
        clearPendingAiJob();
        setPendingJob(null);
        return;
      }
      if (data.status === "failed") {
        if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted") {
          const titleText =
            job?.kind === "continuation"
              ? t({ ja: "続き生成が失敗しました", en: "Continuation failed" })
              : t({ ja: "AI小説生成が失敗しました", en: "AI novel failed" });
          try {
            new Notification(titleText);
          } catch {
            // ignore
          }
        }
        setError(
          data.error ||
            t({ ja: "生成中にエラーが発生しました。", en: "An error occurred during generation." })
        );
        stopJobPolling();
        setLoading(false);
        setContinuing(false);
        setRetryAttempts(0);
        setActiveRetryMax(null);
        clearPendingAiJob();
        setPendingJob(null);
        return;
      }
      jobPollTimerRef.current = setTimeout(() => pollAiJob(job, sessionId), 2000);
    } catch (err) {
      console.error(err);
      if (isAbortError(err)) {
        setError(
          t({
            ja: "生成状況の取得がタイムアウトしました。自動で再試行します。画面を閉じても完了時に通知されます。",
            en: "Status check timed out. Retrying automatically. You will be notified when it completes.",
          })
        );
        jobPollTimerRef.current = setTimeout(() => pollAiJob(job, sessionId), 4000);
        return;
      }
      jobPollTimerRef.current = setTimeout(() => pollAiJob(job, sessionId), 3000);
    }
  };

  const startJobPolling = (job) => {
    stopJobPolling();
    if (!job) return;
    const withStartedAt = job.started_at ? job : { ...job, started_at: Date.now() };
    setPendingJob(withStartedAt);
    savePendingAiJob(withStartedAt);
    if (job.kind === "continuation") {
      setContinuing(true);
    } else {
      setLoading(true);
    }
    const sessionId = activeJobSessionRef.current;
    jobPollTimerRef.current = setTimeout(() => pollAiJob(withStartedAt, sessionId), 500);
  };

  const resumePendingJobIfAny = (kind) => {
    const job = pendingJob || loadPendingAiJob();
    if (!job || job.kind !== kind || !job.job_id) return false;
    startJobPolling(job);
    return true;
  };

  const fetchDraftSlots = async (selectId = null) => {
    const token = getAuthToken();
    if (!token) return;
    setDraftSlotsLoading(true);
    setDraftSlotsError("");
    try {
      const res = await fetch("/api/ai/novels/drafts", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        throw new Error(
          t(
            { ja: "保存データの取得に失敗しました (status={{status}})", en: "Failed to load saves (status={{status}})" },
            { status: res.status }
          )
        );
      }
      const data = await res.json().catch(() => []);
      const list = Array.isArray(data) ? data : [];
      setDraftSlots(list);
      if (selectId) {
        setSelectedDraftId(String(selectId));
      }
    } catch (e) {
      console.error(e);
      setDraftSlotsError(
        e.message || t({ ja: "保存データの取得中にエラーが発生しました。", en: "Failed to load saves." })
      );
    } finally {
      setDraftSlotsLoading(false);
    }
  };

  const handleLoadDraftSlot = async () => {
    const token = getAuthToken();
    if (!token || !selectedDraftId) return;
    setDraftSlotsLoading(true);
    setDraftSlotsError("");
    try {
      const res = await fetch(`/api/ai/novels/drafts/${selectedDraftId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        throw new Error(
          t(
            { ja: "保存データの読み込みに失敗しました (status={{status}})", en: "Failed to load save (status={{status}})" },
            { status: res.status }
          )
        );
      }
      const data = await res.json().catch(() => ({}));
      if (data?.draft) {
        applyDraft(data.draft);
      }
      if (typeof data?.title === "string") {
        setDraftTitle(data.title);
      }
    } catch (e) {
      console.error(e);
      setDraftSlotsError(
        e.message || t({ ja: "保存データの読み込み中にエラーが発生しました。", en: "Failed to load save." })
      );
    } finally {
      setDraftSlotsLoading(false);
    }
  };

  const handleSaveDraftSlot = async () => {
    const token = getAuthToken();
    if (!token) {
      setDraftSlotsError(t({ ja: "ログインしてください。", en: "Please log in." }));
      return;
    }
    setDraftSlotsLoading(true);
    setDraftSlotsError("");
    try {
      const title = buildDefaultDraftTitle();
      const payload = buildDraftPayload();
      const res = await fetch("/api/ai/novels/drafts", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ title, draft: payload }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "failed");
      }
      const data = await res.json().catch(() => ({}));
      if (typeof data?.title === "string") {
        setDraftTitle(data.title);
      }
      await fetchDraftSlots(data?.id ? String(data.id) : null);
    } catch (e) {
      console.error(e);
      setDraftSlotsError(
        e.message || t({ ja: "保存中にエラーが発生しました。", en: "Failed to save." })
      );
    } finally {
      setDraftSlotsLoading(false);
    }
  };

  const handleOverwriteDraftSlot = async () => {
    const token = getAuthToken();
    if (!token || !selectedDraftId) return;
    setDraftSlotsLoading(true);
    setDraftSlotsError("");
    try {
      const payload = buildDraftPayload();
      const title = buildDefaultDraftTitle();
      const res = await fetch(`/api/ai/novels/drafts/${selectedDraftId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ title, draft: payload }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "failed");
      }
      const data = await res.json().catch(() => ({}));
      if (typeof data?.title === "string") {
        setDraftTitle(data.title);
      }
      await fetchDraftSlots();
    } catch (e) {
      console.error(e);
      setDraftSlotsError(
        e.message || t({ ja: "上書き保存中にエラーが発生しました。", en: "Failed to overwrite." })
      );
    } finally {
      setDraftSlotsLoading(false);
    }
  };

  const handleDeleteDraftSlot = async () => {
    const token = getAuthToken();
    if (!token || !selectedDraftId) return;
    const target = draftSlots.find((item) => String(item.id) === String(selectedDraftId));
    const name = (target?.title || "").trim();
    const ok = window.confirm(
      t(
        {
          ja: "保存データ「{{title}}」を削除します。よろしいですか？",
          en: "Delete saved draft “{{title}}”?",
        },
        { title: name || "Untitled" }
      )
    );
    if (!ok) return;
    setDraftSlotsLoading(true);
    setDraftSlotsError("");
    try {
      const res = await fetch(`/api/ai/novels/drafts/${selectedDraftId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "failed");
      }
      setSelectedDraftId("");
      await fetchDraftSlots();
    } catch (e) {
      console.error(e);
      setDraftSlotsError(
        e.message || t({ ja: "削除中にエラーが発生しました。", en: "Failed to delete." })
      );
    } finally {
      setDraftSlotsLoading(false);
    }
  };

  const startTextEditMode = () => {
    const current = getCombinedBody();
    setTextEditOriginal(current);
    setTextEditValue(current);
    setTextEditMode(true);
  };

  const cancelTextEditMode = () => {
    setTextEditValue(textEditOriginal);
    setTextEditMode(false);
  };

  const applyTextEditMode = () => {
    const nextBody = textEditValue || "";
    setResult((prev) => ({
      ...(prev || {}),
      body: nextBody,
    }));
    // 手動編集後は 1 本化して扱う
    setContinuationBody("");
    setTextEditMode(false);
  };

  const handleResetAll = () => {
    setTitleHint("");
    setGenre("");
    setCharacters("");
    setTone("");
    setLength("medium");
    setModel("gpt-4.1-mini");
    setIsR18(false);
    setRetryMode(false);
    setRetryMax(2);
    setRetryAttempts(0);
    setActiveRetryMax(null);
    setResult(null);
    setContinuationBody("");
    setPostEpisodeTitle("");
    setLastGenerateParams(null);
    setAutoFillPreview(null);
    setAutoFillError("");
    setError("");
    setQuotaError("");
    setPremiumError("");
    setPolishPreview(null);
    setLastPolishContext(null);
    setHasContinuationAttempted(false);
    setRedoContinuationArmed(false);
    setTextEditMode(false);
    setTextEditValue("");
    setTextEditOriginal("");
  };

  useEffect(() => {
    const pending = loadPendingAiJob();
      if (pending && pending.job_id) {
      if (pending.kind === "continuation") {
        setContinuing(true);
      } else {
        setLoading(true);
      }
      startJobPolling(pending);
    }
    return () => stopJobPolling();
  }, []);

  useEffect(() => {
    if (!result) {
      setTextEditMode(false);
      setTextEditValue("");
      setTextEditOriginal("");
    }
  }, [result]);

  useEffect(() => {
    if (!hasAuthToken) return;
    fetchDraftSlots();
  }, [hasAuthToken]);

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      setIsPushDebugUser(false);
      return;
    }
    (async () => {
      try {
        const res = await fetch("/api/users/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          setIsPushDebugUser(false);
          return;
        }
        const data = await res.json().catch(() => ({}));
        setIsPushDebugUser((data?.username || "") === "demo02");
      } catch {
        setIsPushDebugUser(false);
      }
    })();
  }, [hasAuthToken]);

  useEffect(() => {
    const handleSelectionChange = () => {
      const selection = window.getSelection ? window.getSelection() : null;
      if (!selection || selection.rangeCount === 0) {
        setHasActiveSelection(false);
        return;
      }
      const range = selection.getRangeAt(0);
      if (range.collapsed) {
        setHasActiveSelection(false);
        return;
      }
      const pre = resultBodyRef.current;
      if (!pre || !pre.contains(range.commonAncestorContainer)) {
        setHasActiveSelection(false);
        return;
      }
      const context = getSelectionContext(selection);
      const hasSelection = Boolean(context && context.selectedText);
      setHasActiveSelection(hasSelection);
      if (hasSelection) {
        lastSelectionContextRef.current = context;
      }
    };

    document.addEventListener("selectionchange", handleSelectionChange);
    return () => document.removeEventListener("selectionchange", handleSelectionChange);
  }, []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(AI_NOVEL_DRAFT_KEY);
      if (!raw) return;
      const draft = JSON.parse(raw);
      localDraftRef.current = draft;
      applyDraft(draft);
    } catch (e) {
      console.error("failed to load ai novel draft", e);
    }
  }, []);

  useEffect(() => {
    const token = getAuthToken();
    if (!token) return;
    (async () => {
      try {
        const res = await fetch("/api/ai/novels/draft", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return;
        const data = await res.json().catch(() => ({}));
        const serverDraft = data?.draft || null;
        if (!serverDraft) return;
        if (hasUserInputRef.current) return;
        const localTs = extractDraftTimestamp(localDraftRef.current);
        const serverTs = extractDraftTimestamp(serverDraft);
        if (serverTs >= localTs) {
          localDraftRef.current = serverDraft;
          applyDraft(serverDraft);
        }
      } catch (e) {
        console.error("failed to load ai novel server draft", e);
      }
    })();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      const payload = buildDraftPayload();
      try {
        localStorage.setItem(AI_NOVEL_DRAFT_KEY, JSON.stringify(payload));
        localDraftRef.current = payload;
      } catch (e) {
        console.error("failed to save ai novel draft", e);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [
    titleHint,
    genre,
    characters,
    tone,
    length,
    model,
    isR18,
    retryMode,
    retryMax,
    isContinueMode,
    episodeId,
    continueNovelId,
    continueEpisodeNumber,
    isEditMode,
    editSourceBody,
    result,
    continuationBody,
    postEpisodeTitle,
    lastGenerateParams,
  ]);

  useEffect(() => {
    const token = getAuthToken();
    if (!token) return;
    if (draftSaveTimerRef.current) {
      clearTimeout(draftSaveTimerRef.current);
    }
    const payload = buildDraftPayload();
    draftSaveTimerRef.current = setTimeout(() => {
      fetch("/api/ai/novels/draft", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ draft: payload }),
      }).catch((e) => {
        console.error("failed to save ai novel server draft", e);
      });
    }, 1500);
    return () => {
      if (draftSaveTimerRef.current) {
        clearTimeout(draftSaveTimerRef.current);
      }
    };
  }, [
    titleHint,
    genre,
    characters,
    tone,
    length,
    model,
    isR18,
    retryMode,
    retryMax,
    isContinueMode,
    episodeId,
    continueNovelId,
    continueEpisodeNumber,
    isEditMode,
    editSourceBody,
    result,
    continuationBody,
    postEpisodeTitle,
    lastGenerateParams,
  ]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const restore = params.get("restore_pending");
    if (restore !== "1") return;

    const pending = loadPendingAiPost();
    if (!pending || !pending.body) return;
    const errMsg = consumePendingAiPostError();
    if (errMsg) setError(errMsg);
    setResult({
      generated_title:
        pending.generated_title || pending.title || t({ ja: "AI生成小説", en: "AI-generated novel" }),
      body: pending.body,
    });
  }, []);

  // ★ URL の ?episode_id=xxx を拾って「続きモード」にする
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const eid = params.get("episode_id");
    if (!eid) return;

    setIsContinueMode(true);
    setEpisodeId(eid);
    setContinueInfoError("");
    setCanPostToContinueNovel(null);

    // ここでエピソードを取得して、タイトルヒントなどに反映しておくと親切
    (async () => {
      try {
        const token = getAuthToken();
        if (!token) {
          setContinueInfoError(
            t({
              ja: "ログインが必要です。ログイン後にもう一度お試しください。",
              en: "Login required. Please sign in and try again.",
            })
          );
          setCanPostToContinueNovel(false);
          return;
        }
        const res = await fetch(`/api/episodes/${eid}`, {
          headers: token
            ? { Authorization: `Bearer ${token}` }
            : {},
        });
        if (!res.ok) {
          console.warn("failed to load episode for continue mode", res.status);
          setContinueInfoError(
            t(
              {
                ja: "続き生成元のエピソード情報を取得できませんでした (status={{status}})",
                en: "Failed to load the source episode (status={{status}})",
              },
              { status: res.status }
            )
          );
          setCanPostToContinueNovel(false);
          return;
        }
        const data = await res.json();

        // タイトルのイメージに「◯話の続き」っぽい文言を入れておく
        if (data?.title) {
          setTitleHint(
            t(
              { ja: "「{{title}}」の続き", en: "Continuation of \"{{title}}\"" },
              { title: data.title }
            )
          );
        }
        if (typeof data?.novel_id === "number") setContinueNovelId(data.novel_id);
        if (typeof data?.episode_number === "number") setContinueEpisodeNumber(data.episode_number);
        // 必要ならここで characters / tone を埋めてもよい

        // 既存小説へ投稿できるか（作者か）を判定
        const novelId = typeof data?.novel_id === "number" ? data.novel_id : null;
        if (!novelId) {
          setContinueInfoError(
            t({ ja: "投稿先の小説IDを取得できませんでした。", en: "Could not get destination novel ID." })
          );
          setCanPostToContinueNovel(false);
          return;
        }
        const meId = getJwtUserId(token);
        if (!meId) {
          // 判定できない場合は投稿時にサーバの 403 を見て案内する
          setCanPostToContinueNovel(true);
          return;
        }
        const novelRes = await fetch(`/api/novels/${novelId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!novelRes.ok) {
          setCanPostToContinueNovel(false);
          setContinueInfoError(
            t(
              {
                ja: "投稿先の小説情報を取得できませんでした (status={{status}})",
                en: "Failed to load destination novel (status={{status}})",
              },
              { status: novelRes.status }
            )
          );
          return;
        }
        const novelData = await novelRes.json().catch(() => ({}));
        const authorId = typeof novelData?.author_id === "number" ? novelData.author_id : null;
        if (!authorId) {
          setCanPostToContinueNovel(false);
          setContinueInfoError(
            t({
              ja: "投稿先の小説の author_id を取得できませんでした。",
              en: "Could not get the destination novel's author ID.",
            })
          );
          return;
        }
        if (authorId !== meId) {
          setCanPostToContinueNovel(false);
          setContinueInfoError(
            t({
              ja: "この小説はあなたの作品ではないため、既存小説への続き投稿はできません。",
              en: "This novel isn't yours, so you can't post a continuation.",
            })
          );
          return;
        }
        setCanPostToContinueNovel(true);
      } catch (e) {
        console.error(e);
        setContinueInfoError(
          t({
            ja: "続き生成の準備中にエラーが発生しました。",
            en: "An error occurred while preparing continuation.",
          })
        );
        setCanPostToContinueNovel(false);
      }
    })();
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("episode_id")) return;
    const editEid = params.get("edit_episode_id");
    if (!editEid) return;

    setIsEditMode(true);
    setIsContinueMode(false);
    setEpisodeId(null);
    setContinueNovelId(null);
    setContinueEpisodeNumber(null);
    setContinueInfoError("");
    setCanPostToContinueNovel(null);
    setError("");

    (async () => {
      try {
        const token = getAuthToken();
        if (!token) {
          setError(
            t({
              ja: "ログインが必要です。ログイン後にもう一度お試しください。",
              en: "Login required. Please sign in and try again.",
            })
          );
          return;
        }
        const res = await fetch(`/api/episodes/${editEid}/edit`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          throw new Error(
            t(
              {
                ja: "編集対象のエピソードを取得できませんでした (status={{status}})",
                en: "Failed to load the episode for editing (status={{status}})",
              },
              { status: res.status }
            )
          );
        }
        const data = await res.json().catch(() => ({}));
        const title = data?.title || t({ ja: "タイトル未設定", en: "Untitled" });
        const body = data?.body || "";
        if (typeof data?.novel_id === "number") setContinueNovelId(data.novel_id);
        if (typeof data?.episode_number === "number") setContinueEpisodeNumber(data.episode_number);
        if (data?.can_edit_full === false) {
          setCanPostToContinueNovel(false);
          setContinueInfoError(
            t({
              ja: "このエピソードの作者ではないため、次話として投稿できません。",
              en: "You are not the author of this episode, so you can't post the next episode.",
            })
          );
        } else {
          setCanPostToContinueNovel(true);
        }
        setEditSourceBody(body);
        setResult({ generated_title: title, body });
      } catch (e) {
        console.error(e);
        setError(
          e.message ||
            t({ ja: "編集用エピソードの読み込み中にエラーが発生しました。", en: "Failed to load episode for edit." })
        );
      }
    })();
  }, []);

  useEffect(() => {
    if (!result) return;
    if (isContinueMode) {
      setPostEpisodeTitle(result.generated_title || t({ ja: "続き", en: "Continuation" }));
      return;
    }
    setPostEpisodeTitle("");
  }, [result, isContinueMode]);

  const getCombinedBody = () => {
    if (!result?.body) return "";
    if (!continuationBody) return result.body;
    return `${result.body}\n\n${continuationBody}`;
  };

  useEffect(() => {
    combinedBodyRef.current = getCombinedBody();
  }, [result, continuationBody]);

  const getSelectionContext = (selectionOverride = null) => {
    const selection = selectionOverride || (window.getSelection ? window.getSelection() : null);
    if (!selection || selection.rangeCount === 0) return null;
    const range = selection.getRangeAt(0);
    if (range.collapsed) return null;
    const pre = resultBodyRef.current;
    if (!pre || !pre.contains(range.commonAncestorContainer)) return null;

    const fullText = combinedBodyRef.current || "";
    if (!fullText) return null;
    const beforeRange = document.createRange();
    beforeRange.selectNodeContents(pre);
    beforeRange.setEnd(range.startContainer, range.startOffset);
    const start = beforeRange.toString().length;
    const selectedText = range.toString();
    const end = start + selectedText.length;
    if (!selectedText) return null;

    return { fullText, start, end, selectedText };
  };

  const buildContinuationPrompt = (baseBody, params) => {
    const lengthMap = {
      short: "800〜1200文字程度",
      medium: "2000〜3000文字程度",
      long: "4000〜6000文字程度",
      xlong: "6000〜8000文字程度",
      xxlong: "8000〜10000文字程度",
    };
    const lengthText = lengthMap[params.length || "medium"] || lengthMap.medium;
    const r18Note = params.isR18
      ? "成人向けの内容を許可します。性的描写を含めても構いません。"
      : "一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。";
    const titleHintText = params.titleHint || "指定なし";
    const genreText = params.genre || "指定なし";
    const toneText = params.tone || "指定なし";
    const charactersText = params.characters || "指定なし";

    return [
      "あなたは日本語のライトノベル作家です。",
      "以下の小説本文の続きを自然につながるように書いてください。",
      r18Note,
      "",
      "【前に書いた本文】",
      baseBody,
      "",
      "【参考情報】",
      `- タイトルのイメージ: ${titleHintText}`,
      `- ジャンル: ${genreText}`,
      `- 雰囲気: ${toneText}`,
      `- 登場人物・設定: ${charactersText}`,
      `- 文字数の目安: ${lengthText}`,
      "",
      "出力は JSON の body に続き本文のみを書いてください（タイトルは変更しない）。",
    ].join("\n");
  };

  const buildEditPrompt = (baseBody, params) => {
    const lengthMap = {
      short: "800〜1200文字程度",
      medium: "2000〜3000文字程度",
      long: "4000〜6000文字程度",
      xlong: "6000〜8000文字程度",
      xxlong: "8000〜10000文字程度",
    };
    const lengthText = lengthMap[params.length || "medium"] || lengthMap.medium;
    const r18Note = params.isR18
      ? "成人向けの内容を許可します。性的描写を含めても構いません。"
      : "一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。";
    const titleHintText = params.titleHint || "指定なし";
    const genreText = params.genre || "指定なし";
    const toneText = params.tone || "指定なし";
    const charactersText = params.characters || "指定なし";

    return [
      "あなたは日本語の小説編集者です。",
      "以下の本文を、内容の整合性を保ちながら読みやすく整えてください。",
      "語尾の揺れや冗長な表現を適宜調整し、自然な文体にしてください。",
      r18Note,
      "",
      "【本文】",
      baseBody,
      "",
      "【参考情報】",
      `- 編集方針・指示: ${titleHintText}`,
      `- ジャンル: ${genreText}`,
      `- 雰囲気: ${toneText}`,
      `- 登場人物・設定: ${charactersText}`,
      `- 文字数の目安: ${lengthText}`,
      "",
      "出力は JSON の body に修正文のみを書いてください（タイトルは変更しない）。",
    ].join("\n");
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    await ensureWebPushSubscription(getAuthToken(), setPushDebugInfo);
    // 新規生成開始時は過去ジョブの応答を無効化し、過去パラメータ参照をクリアする
    activeJobSessionRef.current += 1;
    stopJobPolling();
    clearPendingAiJob();
    setPendingJob(null);
    setLoading(true);
    setError("");
    setQuotaError("");
    setPremiumError("");
    setAutoFillError("");
    const baseBodyForEdit = isEditMode
      ? (result?.body || editSourceBody || "").trim()
      : "";
    setResult(null);
    setLastGenerateParams(null);
    setContinuationBody("");
    setHasContinuationAttempted(false);
    setRedoContinuationArmed(false);

    const token = getAuthToken();
    if (episodeId && !token) {
      setError(
        t({
          ja: "ログインが必要です。ログイン画面へ移動します。",
          en: "Login required. Redirecting to the login page.",
        })
      );
      setTimeout(() => {
        navigate("/login"); // 既存のログインパスに合わせて変更
      }, 800);
      setLoading(false);
      return;
    }
    if (isEditMode && !baseBodyForEdit) {
      setError(
        t({
          ja: "編集対象の本文が空です。エピソード本文を確認してください。",
          en: "The source body is empty. Please check the episode text.",
        })
      );
      setLoading(false);
      return;
    }

    const params = {
      titleHint,
      genre,
      characters,
      tone,
      length,
      model,
      isR18,
      retryMode,
      retryMax,
    };
    // ★ ここで「通常の新規生成」と「エピソード続き生成」を切り替える
    const endpoint = episodeId
      ? `/api/ai/episodes/${episodeId}/continue_job`
      : "/api/ai/novels/generate_job";
    const prompt =
      isEditMode && baseBodyForEdit
        ? buildEditPrompt(baseBodyForEdit, params)
        : null;

    try {
      const res = await fetchWithTimeout(
        endpoint,
        {
          method: "POST",
          headers: token
            ? {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
              }
            : { "Content-Type": "application/json" },
          body: JSON.stringify({
            title_hint: titleHint || null,
            genre: genre || null,
            characters: characters || null,
            tone: tone || null,
            length: length || "medium",
            model: model || "gpt-4.1-mini",
            r18: isR18,
            prompt,
            retry_mode: retryMode,
            retry_max: retryMax,
          }),
        },
        20000
      );

      if (res.status === 401 && token) {
        setError(
          t({
            ja: "ログインの有効期限が切れています。再ログインしてください。",
            en: "Your session has expired. Please log in again.",
          })
        );
        setTimeout(() => navigate("/login"), 800);
        setLoading(false);
        return;
      }

      if (res.status === 402) {
        setPremiumError(
          t({
            ja: "この機能は有料プラン専用です。マイページからプランをご確認ください。",
            en: "This feature is for paid plans only. Check your plan on My Page.",
          })
        );
        setLoading(false);
        return;
      }

      if (res.status === 429) {
        const data = await res.json().catch(() => ({}));
        setQuotaError(
          data.detail ||
            t({
              ja: "本日の AI 小説生成の上限回数に達しました。明日またお試しください。",
              en: "You've reached today's AI generation limit. Please try again tomorrow.",
            })
        );
        setLoading(false);
        return;
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(
          data.detail ||
            t(
              { ja: "生成に失敗しました (status={{status}})", en: "Generation failed (status={{status}})" },
              { status: res.status }
            )
        );
      }

      const data = await res.json();
      setLastGenerateParams(params);
      setRetryAttempts(0);
      setActiveRetryMax(params.retryMode ? params.retryMax : 0);
      startJobPolling({ job_id: data.job_id, kind: "generate" });
    } catch (err) {
      console.error(err);
      if (isAbortError(err)) {
        setError(
          t({
            ja: "生成リクエストがタイムアウトしました。通信環境を確認してもう一度お試しください。",
            en: "The request timed out. Please check your connection and try again.",
          })
        );
      } else {
        setError(
          err.message || t({ ja: "生成中にエラーが発生しました。", en: "An error occurred during generation." })
        );
      }
      setLoading(false);
    }
  };

  const handleGenerateContinuation = async (baseBodyOverride = null) => {
    if (!result?.body) return;
    await ensureWebPushSubscription(getAuthToken(), setPushDebugInfo);
    if (resumePendingJobIfAny("continuation")) {
      return;
    }
    activeJobSessionRef.current += 1;
    stopJobPolling();
    clearPendingAiJob();
    setPendingJob(null);
    setContinuing(true);
    setHasContinuationAttempted(true);
    setRedoContinuationArmed(false);
    setError("");
    setQuotaError("");
    setPremiumError("");
    setAutoFillError("");

    const token = getAuthToken();
    const params = lastGenerateParams || {
      titleHint,
      genre,
      characters,
      tone,
      length,
      model,
      isR18,
      retryMode,
      retryMax,
    };

    const baseBody = typeof baseBodyOverride === "string" ? baseBodyOverride : getCombinedBody();
    const prompt = buildContinuationPrompt(baseBody, params);
    try {
      const res = await fetchWithTimeout(
        "/api/ai/novels/generate_job",
        {
          method: "POST",
          headers: token
            ? {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
              }
            : { "Content-Type": "application/json" },
          body: JSON.stringify({
            title_hint: params.titleHint || null,
            genre: params.genre || null,
            characters: params.characters || null,
            tone: params.tone || null,
            length: null,
            model: params.model || "gpt-4.1-mini",
            r18: params.isR18,
            prompt,
            retry_mode: params.retryMode,
            retry_max: params.retryMax,
          }),
        },
        20000
      );

      if (res.status === 401 && token) {
        setError(
          t({
            ja: "ログインの有効期限が切れています。再ログインしてください。",
            en: "Your session has expired. Please log in again.",
          })
        );
        setTimeout(() => navigate("/login"), 800);
        setContinuing(false);
        return;
      }

      if (res.status === 402) {
        setPremiumError(
          t({
            ja: "この機能は有料プラン専用です。マイページからプランをご確認ください。",
            en: "This feature is for paid plans only. Check your plan on My Page.",
          })
        );
        setContinuing(false);
        return;
      }

      if (res.status === 429) {
        const data = await res.json().catch(() => ({}));
        setQuotaError(
          data.detail ||
            t({
              ja: "本日の AI 小説生成の上限回数に達しました。明日またお試しください。",
              en: "You've reached today's AI generation limit. Please try again tomorrow.",
            })
        );
        setContinuing(false);
        return;
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(
          data.detail ||
            t(
              { ja: "生成に失敗しました (status={{status}})", en: "Generation failed (status={{status}})" },
              { status: res.status }
            )
        );
      }

      const data = await res.json();
      setRetryAttempts(0);
      setActiveRetryMax(params.retryMode ? params.retryMax : 0);
      startJobPolling({ job_id: data.job_id, kind: "continuation" });
    } catch (err) {
      console.error(err);
      if (isAbortError(err)) {
        setError(
          t({
            ja: "生成リクエストがタイムアウトしました。通信環境を確認してもう一度お試しください。",
            en: "The request timed out. Please check your connection and try again.",
          })
        );
      } else {
        setError(
          err.message || t({ ja: "生成中にエラーが発生しました。", en: "An error occurred during generation." })
        );
      }
      setContinuing(false);
    }
  };

  const handleRedoContinuation = async () => {
    if (!result?.body) return;
    await ensureWebPushSubscription(getAuthToken(), setPushDebugInfo);
    if (resumePendingJobIfAny("continuation")) {
      return;
    }
    setContinuationBody("");
    await handleGenerateContinuation(result.body);
  };

  const handlePolishText = async (overrideContext = null) => {
    const safeOverride =
      overrideContext && typeof overrideContext === "object" && "selectedText" in overrideContext
        ? overrideContext
        : null;
    const selectionContext =
      safeOverride || lastSelectionContextRef.current || getSelectionContext();
    const combinedBody = combinedBodyRef.current || getCombinedBody();
    if (!combinedBody) return;
    if (!selectionContext && !result?.body) {
      setError(
        t({
          ja: "本文が取得できませんでした。先にAI生成を行ってください。",
          en: "No text available. Generate content before polishing.",
        })
      );
      return;
    }
    const context = selectionContext || {
      fullText: combinedBody,
      start: 0,
      end: combinedBody.length,
      selectedText: combinedBody,
    };
    const baseBody = context.selectedText;
    if (!baseBody) return;
    setPolishing(true);
    setError("");
    setQuotaError("");
    setPremiumError("");
    setAutoFillError("");
    setPolishPreview(null);

    const token = getAuthToken();
    const params = lastGenerateParams || {
      titleHint,
      genre,
      characters,
      tone,
      length,
      model,
      isR18,
    };

    try {
      setLastPolishContext(context);
      const maxChars = combinedBody.length || 0;
      const prompt = buildPolishPrompt({
        baseBody,
        tone: params.tone,
        genre: params.genre,
        characters: params.characters,
        isR18: params.isR18,
        intensity: polishIntensity,
        maxChars,
      });
      const res = await fetch("/api/ai/novels/generate", {
        method: "POST",
        headers: token
          ? {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            }
          : { "Content-Type": "application/json" },
        body: JSON.stringify({
          title_hint: params.titleHint || null,
          genre: params.genre || null,
          characters: params.characters || null,
          tone: params.tone || null,
          length: String(maxChars),
          model: params.model || "gpt-4.1-mini",
          r18: params.isR18,
          prompt,
        }),
      });

      let errorDetail = null;
      if (!res.ok) {
        const isJson = res.headers.get("content-type")?.includes("application/json");
        if (isJson) {
          const data = await res.json().catch(() => ({}));
          if (data && typeof data.detail === "string" && data.detail.trim()) {
            errorDetail = data.detail.trim();
          }
        } else {
          const text = await res.text().catch(() => "");
          if (text && text.trim()) {
            errorDetail = text.trim().slice(0, 300);
          }
        }
      }

      if (res.status === 401 && token) {
        setError(
          t({
            ja: "ログインの有効期限が切れています。再ログインしてください。",
            en: "Your session has expired. Please log in again.",
          })
        );
        setTimeout(() => navigate("/login"), 800);
        setPolishing(false);
        return;
      }

      if (res.status === 402) {
        setPremiumError(
          t({
            ja: "この機能は有料プラン専用です。マイページからプランをご確認ください。",
            en: "This feature is for paid plans only. Check your plan on My Page.",
          })
        );
        setPolishing(false);
        return;
      }

      if (res.status === 429) {
        setQuotaError(
          errorDetail ||
            t({
              ja: "本日の AI 小説生成の上限回数に達しました。明日またお試しください。",
              en: "You've reached today's AI generation limit. Please try again tomorrow.",
            })
        );
        setPolishing(false);
        return;
      }

      if (!res.ok) {
        throw new Error(
          errorDetail ||
            t(
              { ja: "生成に失敗しました (status={{status}})", en: "Generation failed (status={{status}})" },
              { status: res.status }
            )
        );
      }

      const data = normalizeAINovelResponse(await res.json());
      if (typeof data?.guest_remaining === "number") {
        setGuestRemaining(data.guest_remaining);
      } else {
        setGuestRemaining(null);
      }
      if (typeof data?.user_remaining === "number") {
        setUserRemaining(data.user_remaining);
      } else {
        setUserRemaining(null);
      }
      const nextBody = (data?.body || "").trim();
      setPolishPreview({
        context,
        proposedText: nextBody || context.selectedText,
      });
    } catch (err) {
      console.error(err);
      setError(
        err.message || t({ ja: "添削中にエラーが発生しました。", en: "An error occurred during polishing." })
      );
    } finally {
      setPolishing(false);
    }
  };

  const handleApplyPolishPreview = () => {
    if (!polishPreview || !polishPreview.context) return;
    const { context, proposedText } = polishPreview;
    const updatedFullText = applyPolishReplacement(
      context.fullText,
      context.start,
      context.end,
      proposedText
    );
    setResult((prev) => ({
      ...(prev || {}),
      body: updatedFullText,
    }));
    setContinuationBody("");
    setPolishPreview(null);
  };

  const handleCancelPolishPreview = () => {
    setPolishPreview(null);
  };

  const handlePostAsNewNovel = async () => {
    if (!result?.body) return;
    setPosting(true);
    setError("");
    setQuotaError("");
    setPremiumError("");
    setAutoFillError("");

    const token = getAuthToken();
    const combinedBody = getCombinedBody();
    if (!token) {
      savePendingAiPost({
        kind: "new_novel",
        generated_title: result.generated_title || t({ ja: "AI生成小説", en: "AI-generated novel" }),
        body: combinedBody,
        age_limit: isR18 ? "r18" : "all",
        createdAt: Date.now(),
      });
      setError(
        t({
          ja: "投稿にはログインが必要です。ログイン画面へ移動します。",
          en: "Login required to post. Redirecting to the login page.",
        })
      );
      setTimeout(() => navigate("/login"), 200);
      setPosting(false);
      return;
    }

    try {
      const novelPayload = {
        title: result.generated_title || t({ ja: "AI生成小説", en: "AI-generated novel" }),
        description: t({ ja: "AI生成", en: "AI-generated" }),
        age_limit: isR18 ? "r18" : "all",
        is_ai_generated: true,
        tag_names: [],
      };

      const novelRes = await fetch("/api/novels", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(novelPayload),
      });
      const novelData = await novelRes.json().catch(() => ({}));
      if (!novelRes.ok) {
        throw new Error(
          novelData.detail ||
            t(
              { ja: "小説の作成に失敗しました (status={{status}})", en: "Failed to create novel (status={{status}})" },
              { status: novelRes.status }
            )
        );
      }
      const novelId = novelData?.id;
      if (!novelId) {
        throw new Error(
          t({ ja: "小説IDが取得できませんでした。", en: "Could not get novel ID." })
        );
      }

      const episodePayload = {
        episode_number: 1,
        title: t({ ja: "第1話", en: "Episode 1" }),
        body: combinedBody,
        tag_names: [],
      };
      const epRes = await fetch(`/api/novels/${novelId}/episodes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(episodePayload),
      });
      const epData = await epRes.json().catch(() => ({}));
      if (!epRes.ok) {
        throw new Error(
          epData.detail ||
            t(
              { ja: "第1話の投稿に失敗しました (status={{status}})", en: "Failed to post Episode 1 (status={{status}})" },
              { status: epRes.status }
            )
        );
      }

      navigate(`/novels/${novelId}`);
    } catch (err) {
      console.error(err);
      setError(
        err.message || t({ ja: "投稿中にエラーが発生しました。", en: "An error occurred while posting." })
      );
    } finally {
      setPosting(false);
    }
  };

  const handlePostAsNextEpisode = async () => {
    if (!result?.body) return;
    if (!continueNovelId) {
      setError(
        t({
          ja: "投稿先の小説が特定できません（novel_id が取得できませんでした）。",
          en: "Could not identify the destination novel (novel_id missing).",
        })
      );
      return;
    }
    if (canPostToContinueNovel === false) {
      setError(
        continueInfoError ||
          t({ ja: "既存小説への投稿権限がありません。", en: "You don't have permission to post here." })
      );
      return;
    }
    setPosting(true);
    setError("");
    setQuotaError("");
    setPremiumError("");
    setAutoFillError("");

    const token = getAuthToken();
    const combinedBody = getCombinedBody();
    if (!token) {
      savePendingAiPost({
        kind: "next_episode",
        continue_novel_id: continueNovelId,
        post_episode_title: postEpisodeTitle || "",
        generated_title: result.generated_title || t({ ja: "続き", en: "Continuation" }),
        body: combinedBody,
        createdAt: Date.now(),
      });
      setError(
        t({
          ja: "投稿にはログインが必要です。ログイン画面へ移動します。",
          en: "Login required to post. Redirecting to the login page.",
        })
      );
      setTimeout(() => navigate("/login"), 200);
      setPosting(false);
      return;
    }

    try {
      const listRes = await fetch(`/api/novels/${continueNovelId}/episodes`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const listData = await listRes.json().catch(() => []);
      if (!listRes.ok) {
        throw new Error(
          (listData && listData.detail) ||
            t(
              {
                ja: "エピソード一覧の取得に失敗しました (status={{status}})",
                en: "Failed to fetch episode list (status={{status}})",
              },
              { status: listRes.status }
            )
        );
      }

      const numbers = Array.isArray(listData)
        ? listData.map((e) => (typeof e?.number === "number" ? e.number : null)).filter((n) => n !== null)
        : [];
      const maxNumber = numbers.length ? Math.max(...numbers) : 0;
      const nextNumber = maxNumber + 1;

      const episodePayload = {
        episode_number: nextNumber,
        title:
          (postEpisodeTitle || "").trim() ||
          t({ ja: "第{{num}}話", en: "Episode {{num}}" }, { num: nextNumber }),
        body: combinedBody,
        tag_names: [],
      };
      const epRes = await fetch(`/api/novels/${continueNovelId}/episodes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(episodePayload),
      });
      if (epRes.status === 403) {
        throw new Error(
          t({
            ja: "この小説にエピソードを追加する権限がありません（作者のみ投稿できます）。",
            en: "You don't have permission to add episodes (authors only).",
          })
        );
      }
      const epData = await epRes.json().catch(() => ({}));
      if (!epRes.ok) {
        throw new Error(
          epData.detail ||
            t(
              { ja: "エピソードの投稿に失敗しました (status={{status}})", en: "Failed to post episode (status={{status}})" },
              { status: epRes.status }
            )
        );
      }

      navigate(`/novels/${continueNovelId}`);
    } catch (err) {
      console.error(err);
      setError(
        err.message || t({ ja: "投稿中にエラーが発生しました。", en: "An error occurred while posting." })
      );
    } finally {
      setPosting(false);
    }
  };

  const handleCopyToClipboard = async () => {
    if (!result) return;
    const text = `${result.generated_title}\n\n${getCombinedBody()}`;
    try {
      await navigator.clipboard.writeText(text);
      alert(t({ ja: "クリップボードにコピーしました。", en: "Copied to clipboard." }));
    } catch (e) {
      alert(
        t({
          ja: "コピーに失敗しました。手動で選択してコピーしてください。",
          en: "Copy failed. Please select the text and copy manually.",
        })
      );
    }
  };

  const handleFixJsonOutput = () => {
    if (!result?.body) return;
    const raw = (result.body || "").trim();
    const stripFence = (s) => {
      const t = (s || "").trim();
      if (!t.startsWith("```")) return t;
      const lines = t.split("\n");
      if (lines.length && lines[0].startsWith("```")) lines.shift();
      if (lines.length && lines[lines.length - 1].trim() === "```") lines.pop();
      return lines.join("\n").trim();
    };

    const tryParse = (s) => {
      const cleaned = stripFence(s);
      if (!cleaned.startsWith("{")) return null;
      try {
        const parsed = JSON.parse(cleaned);
        if (parsed && typeof parsed === "object") return parsed;
      } catch {
        return null;
      }
      return null;
    };

    let parsed = tryParse(raw);
    if (!parsed && raw.includes('\\"')) {
      parsed = tryParse(raw.replace(/\\"/g, '"'));
    }
    if (!parsed) {
      const m = raw.match(/\{[\s\S]*\}/);
      if (m) parsed = tryParse(m[0]);
    }

    if (!parsed) {
      setError(
        t({ ja: "JSON形式の修正に失敗しました。", en: "Failed to fix JSON output." })
      );
      return;
    }

    const nextTitle =
      parsed.title ||
      parsed.generated_title ||
      parsed.generatedTitle ||
      result.generated_title;
    const nextBody =
      parsed.body ||
      parsed.text ||
      parsed.content ||
      parsed.story ||
      result.body;

    setResult((prev) => ({
      ...(prev || {}),
      generated_title: nextTitle || t({ ja: "タイトル未設定", en: "Untitled" }),
      body: nextBody || "",
    }));
  };

  const handleAutoFill = async () => {
    const q = (genre || "").trim();
    const liveCharactersRaw = charactersInputRef.current?.value ?? characters ?? "";
    const c = liveCharactersRaw.trim();
    if (liveCharactersRaw !== (characters || "")) {
      setCharacters(liveCharactersRaw);
    }
    const titleQuery = (titleHint || "").trim();
    if (!q && !c && !titleQuery) {
      setAutoFillError(
        t({
          ja: "タイトルのイメージ、ジャンル、登場人物・設定のいずれかを入力してください。",
          en: "Enter a title idea, genre, or characters/settings.",
        })
      );
      return;
    }
    markUserInput();
    setAutoFillLoading(true);
    setAutoFillError("");
    try {
      const payload = {
        query: q || titleQuery || "",
        characters: c || "",
      };
      const res = await fetchWithTimeout(
        "/api/ai/novels/auto-fill",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
        20000
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data.detail ||
            t(
              { ja: "自動補完に失敗しました (status={{status}})", en: "Auto-fill failed (status={{status}})" },
              { status: res.status }
            )
        );
      }
      const appendGenre = (data.genre_append || "").trim();
      const appendCharacters = (data.characters_append || "").trim();
      if (appendGenre && !isContinueMode) {
        setGenre((prev) => {
          const base = (prev || "").trim();
          return base ? `${base} / ${appendGenre}` : appendGenre;
        });
      }
      if (appendCharacters) {
        setCharacters((prev) => {
          const base = (charactersInputRef.current?.value ?? prev ?? "").trim();
          return base ? `${base}\n\n${appendCharacters}` : appendCharacters;
        });
      }
      if (!appendGenre && !appendCharacters) {
        setAutoFillError(
          t({
            ja: "検索結果から補完できる要素が見つかりませんでした。",
            en: "No elements were found to auto-fill.",
          })
        );
      }
      setAutoFillPreview({
        query: data.query || q,
        charactersQuery: data.characters_query || c,
        terms: Array.isArray(data.terms) ? data.terms : [],
        genreAppend: appendGenre,
        charactersAppend: appendCharacters,
        sources: Array.isArray(data.sources) ? data.sources : [],
      });
    } catch (e) {
      console.error(e);
      if (isAbortError(e)) {
        setAutoFillError(
          t({
            ja: "自動補完のリクエストがタイムアウトしました。通信環境を確認してもう一度お試しください。",
            en: "The auto-fill request timed out. Please check your connection and try again.",
          })
        );
      } else {
        setAutoFillError(
          e.message || t({ ja: "自動補完中にエラーが発生しました。", en: "An error occurred during auto-fill." })
        );
      }
    } finally {
      setAutoFillLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto", padding: "1.5rem" }}>
      <h1 style={{ fontSize: "1.8rem", marginBottom: "1rem" }}>
        {isEditMode
          ? t({ ja: "AI小説：エピソード編集", en: "AI Novel: Edit an Episode" })
          : isContinueMode
          ? t({ ja: "AI小説：エピソードの続き生成", en: "AI Novel: Continue an Episode" })
          : t({ ja: "AI小説生成（未ログインは10回まで）", en: "AI Novel Generation (up to 10 for guests)" })}
      </h1>

      {isEditMode ? (
        <p style={{ marginBottom: "1.5rem", color: "var(--ai-desc-text)" }}>
          {t({
            ja: "選択したエピソードの本文を、AIが読みやすく整えます。",
            en: "AI will polish the selected episode text for readability.",
          })}
        </p>
      ) : isContinueMode ? (
        <p style={{ marginBottom: "1.5rem", color: "var(--ai-desc-text)" }}>
          {lang === "ja" ? (
            <>
              選択したエピソードの<strong>続き</strong>を AI が生成します。
            </>
          ) : (
            <>
              AI will generate a <strong>continuation</strong> of the selected episode.
            </>
          )}
          <br />
          {t({
            ja: "必要であれば、雰囲気や追加したい展開を下のフォームに書き足してから「AI小説を生成する」を押してください。",
            en: "If needed, add tone or plot details below, then click “Generate AI novel.”",
          })}
        </p>
      ) : (
        <p style={{ marginBottom: "1.5rem", color: "var(--ai-desc-text)" }}>
          {t({
            ja: "お題や登場人物を入力して、「AI小説を生成する」を押すとお試し小説を生成します。",
            en: "Enter a theme and characters, then click “Generate AI novel” to create a sample story.",
          })}
          <br />
          {t({
            ja: "生成結果は後から自分で編集して、小説やエピソードとして投稿してもOKです。",
            en: "You can edit the result later and post it as a novel or episode.",
          })}
        </p>
      )}

      {typeof guestRemaining === "number" && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.5rem 0.75rem",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            backgroundColor: "var(--ai-result-surface)",
            fontSize: "0.9rem",
          }}
        >
          <div>
            {t(
              { ja: "ゲストの AI生成 残り回数: {{count}}", en: "Guest AI generations left: {{count}}" },
              { count: guestRemaining }
            )}
          </div>
          <div style={{ marginTop: "0.25rem", color: "var(--muted-text)" }}>
            {t({
              ja: "プレミアム会員になると、AI小説生成は1日80回まで利用できます。",
              en: "Premium members can generate AI novels up to 80 times per day.",
            })}
          </div>
          <div style={{ marginTop: "0.5rem" }}>
            <Link to="/mypage" className="btn btn-border">
              {t({ ja: "プレミアム会員になる", en: "Become Premium" })}
            </Link>
          </div>
        </div>
      )}
      {typeof userRemaining === "number" && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.5rem 0.75rem",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            backgroundColor: "var(--ai-result-surface)",
            fontSize: "0.9rem",
          }}
        >
          {t(
            { ja: "ユーザーの AI生成 残り回数: {{count}}", en: "User AI generations left: {{count}}" },
            { count: userRemaining }
          )}
        </div>
      )}
      {isPushDebugUser && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.6rem 0.75rem",
            border: "1px dashed var(--border)",
            borderRadius: "6px",
            backgroundColor: "var(--ai-result-surface)",
            fontSize: "0.85rem",
          }}
        >
          <div style={{ fontWeight: "bold", marginBottom: "0.2rem" }}>
            {t({ ja: "Push登録デバッグ", en: "Push registration debug" })}
          </div>
          <div>
            {t({ ja: "状態", en: "Status" })}: {String(pushDebugInfo.stage || "idle")}
          </div>
          <div>
            {t({ ja: "詳細", en: "Detail" })}: {pushDebugInfo.detail ? String(pushDebugInfo.detail) : "-"}
          </div>
          <div>
            OK:{" "}
            {pushDebugInfo.ok === null ? "-" : pushDebugInfo.ok ? "true" : "false"}
          </div>
        </div>
      )}

      <form
        onSubmit={handleGenerate}
        style={{
          display: "grid",
          gap: "0.75rem",
          marginBottom: "1.5rem",
          padding: "1rem",
          border: "1px solid var(--border)",
          borderRadius: "8px",
        }}
      >
        <div
          style={{
            padding: "0.75rem",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            backgroundColor: "var(--ai-result-surface)",
          }}
        >
          <div style={{ fontWeight: "bold", marginBottom: "0.5rem" }}>
            {t({ ja: "保存データ", en: "Saved drafts" })}
          </div>
          {hasAuthToken ? (
            <>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                <select
                  value={selectedDraftId}
                  onChange={(e) => handleSelectDraftSlot(e.target.value)}
                  style={{ padding: "0.45rem", minWidth: "220px" }}
                >
                  <option value="">{t({ ja: "保存データを選択", en: "Select a saved draft" })}</option>
                  {draftSlots.map((item) => (
                    <option key={item.id} value={String(item.id)}>
                      {item.title}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={handleLoadDraftSlot}
                  disabled={!selectedDraftId || draftSlotsLoading}
                  className="btn btn-border"
                >
                  {t({ ja: "反映", en: "Apply" })}
                </button>
                <button
                  type="button"
                  onClick={() => fetchDraftSlots()}
                  disabled={draftSlotsLoading}
                  className="btn btn-border"
                >
                  {draftSlotsLoading ? t({ ja: "更新中...", en: "Refreshing..." }) : t({ ja: "更新", en: "Refresh" })}
                </button>
              </div>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.6rem" }}>
                <input
                  type="text"
                  value={draftTitle}
                  onChange={(e) => setDraftTitle(e.target.value)}
                  placeholder={t({ ja: "保存タイトル", en: "Save title" })}
                  style={{ padding: "0.5rem", minWidth: "240px", flex: "1 1 240px" }}
                />
                <button
                  type="button"
                  onClick={handleSaveDraftSlot}
                  disabled={draftSlotsLoading}
                  className="btn btn-border"
                >
                  {t({ ja: "新規保存", en: "Save new" })}
                </button>
                <button
                  type="button"
                  onClick={handleOverwriteDraftSlot}
                  disabled={!selectedDraftId || draftSlotsLoading}
                  className="btn btn-border"
                >
                  {t({ ja: "上書き保存", en: "Overwrite" })}
                </button>
                <button
                  type="button"
                  onClick={handleDeleteDraftSlot}
                  disabled={!selectedDraftId || draftSlotsLoading}
                  className="btn btn-border"
                >
                  {t({ ja: "削除", en: "Delete" })}
                </button>
              </div>
              {draftSlotsError && (
                <div style={{ marginTop: "0.5rem", color: "#842029", fontSize: "0.9rem" }}>
                  {draftSlotsError}
                </div>
              )}
            </>
          ) : (
            <div style={{ fontSize: "0.9rem", color: "var(--muted-text)" }}>
              {t({ ja: "ログインすると保存データを使えます。", en: "Log in to use saved drafts." })}
            </div>
          )}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.5rem" }}>
          <button
            type="button"
            onClick={handleResetAll}
            className="btn btn-border"
          >
            {t({ ja: "入力内容をリセット", en: "Reset inputs" })}
          </button>
        </div>

        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
            {isEditMode
              ? t({ ja: "編集方針・指示（任意）", en: "Edit direction (optional)" })
              : t({ ja: "タイトルのイメージ（任意）", en: "Title idea (optional)" })}
          </label>
          <input
            type="text"
            value={titleHint}
            onChange={(e) => {
              markUserInput();
              setTitleHint(e.target.value);
            }}
            placeholder={
              isEditMode
                ? t({
                    ja: "例: テンポを良くして、語尾の重複を減らす など",
                    en: "e.g., Improve pacing and reduce repetitive endings",
                  })
                : isContinueMode
                ? t({
                    ja: "例: 前話の雰囲気を引き継ぎつつ、二人の関係をもう一歩進めてほしい など",
                    en: "e.g., Keep the previous episode's mood and advance their relationship one step",
                  })
                : t({
                    ja: "例: 月夜の喫茶店で始まる物語",
                    en: "e.g., A story that begins in a moonlit cafe",
                  })
            }
            style={{ width: "100%", padding: "0.5rem" }}
          />
          <div style={{ fontSize: "0.8rem", color: "var(--muted-text)", marginTop: "0.25rem" }}>
            {t({ ja: "現在の文字数", en: "Current chars" })}: {countChars(titleHint)}
          </div>
        </div>

        <div>
          {!isContinueMode && (
            <>
            <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
              {t({ ja: "ジャンル（任意）", en: "Genre (optional)" })}
            </label>
            <input
              type="text"
              value={genre}
              onChange={(e) => {
                markUserInput();
                setGenre(e.target.value);
              }}
              placeholder={t({
                ja: "例: ファンタジー / 日常 / SF / ラブコメ",
                en: "e.g., Fantasy / Slice of Life / Sci-Fi / Romcom",
              })}
              style={{ width: "100%", padding: "0.5rem" }}
            />
            <div style={{ fontSize: "0.8rem", color: "var(--muted-text)", marginTop: "0.25rem" }}>
              {t({ ja: "現在の文字数", en: "Current chars" })}: {countChars(genre)}
            </div>
            </>
          )}
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.5rem" }}>
              <button
                type="button"
                onClick={handleAutoFill}
                disabled={autoFillLoading || loading}
                className="btn btn-border"
              >
                {autoFillLoading
                  ? t({ ja: "調査中...", en: "Searching..." })
                  : isContinueMode
                  ? t({ ja: "設定を自動補完", en: "Auto-fill settings" })
                  : t({ ja: "ジャンル/設定を自動補完", en: "Auto-fill genre/settings" })}
              </button>
              <span style={{ fontSize: "0.85rem", color: "var(--muted-text)" }}>
                {isContinueMode
                  ? t({ ja: "入力した内容を検索して登場人物・設定に追記", en: "Search and append to characters/settings" })
                  : t({ ja: "入力したジャンルを検索して反映", en: "Search and apply the genre you entered" })}
              </span>
            </div>
            <div style={{ marginTop: "0.4rem", fontSize: "0.8rem", color: "var(--muted-text)" }}>
              {t({
                ja: "※ 登場人物・設定で「\"キャラ名\"」のようにダブルクォートで囲むと、分割せずそのまま検索します。",
                en: "Tip: Wrap character names in double quotes to search without splitting.",
              })}
            </div>
            {autoFillError && (
              <div style={{ marginTop: "0.5rem", color: "#842029", fontSize: "0.9rem" }}>
                {autoFillError}
              </div>
            )}
            {autoFillPreview && (
              <div
                style={{
                  marginTop: "0.75rem",
                  padding: "0.75rem",
                  border: "1px solid var(--border)",
                  borderRadius: "6px",
                  backgroundColor: "var(--ai-result-surface)",
                }}
                >
                  <div style={{ fontWeight: "bold", marginBottom: "0.5rem" }}>
                  {t({ ja: "自動補完で追加した内容", en: "Added by auto-fill" })}
                  </div>
                {autoFillPreview.terms && autoFillPreview.terms.length > 0 && (
                  <div style={{ fontSize: "0.85rem", color: "var(--muted-text)", marginBottom: "0.5rem" }}>
                    {t(
                      { ja: "検索語: {{terms}}", en: "Search terms: {{terms}}" },
                      { terms: autoFillPreview.terms.join(" / ") }
                    )}
                  </div>
                )}
                {autoFillPreview.charactersQuery && (
                  <div style={{ fontSize: "0.85rem", color: "var(--muted-text)", marginBottom: "0.5rem" }}>
                    {t(
                      { ja: "登場人物・設定の検索元: {{query}}", en: "Characters/settings search: {{query}}" },
                      { query: autoFillPreview.charactersQuery }
                    )}
                  </div>
                )}
                {autoFillPreview.genreAppend && !isContinueMode && (
                  <div style={{ marginBottom: "0.5rem" }}>
                    <strong>{t({ ja: "ジャンルに追加:", en: "Added to genre:" })}</strong>{" "}
                    {autoFillPreview.genreAppend}
                  </div>
                )}
                {autoFillPreview.charactersAppend && (
                  <div style={{ marginBottom: "0.5rem" }}>
                    <strong>{t({ ja: "登場人物・設定に追加:", en: "Added to characters/settings:" })}</strong>
                    <pre
                      style={{
                        marginTop: "0.35rem",
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                        backgroundColor: "#fff",
                        padding: "0.5rem",
                        borderRadius: "4px",
                        border: "1px solid var(--border)",
                        maxHeight: "240px",
                        overflowY: "auto",
                      }}
                    >
                      {autoFillPreview.charactersAppend}
                    </pre>
                  </div>
                )}
                {autoFillPreview.sources && autoFillPreview.sources.length > 0 && (
                  <div style={{ fontSize: "0.85rem", color: "var(--muted-text)" }}>
                    {t({ ja: "参照:", en: "Sources:" })}
                    <ul style={{ marginTop: "0.35rem", paddingLeft: "1.2rem" }}>
                      {autoFillPreview.sources.map((s, idx) => (
                        <li key={`${s.link || s.title || "source"}-${idx}`}>
                          <a href={s.link} target="_blank" rel="noreferrer">
                            {s.title || s.link}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
            {isContinueMode
              ? t({ ja: "登場人物・設定（変更/追加したい場合）", en: "Characters & settings (optional changes)" })
              : t({ ja: "登場人物・設定", en: "Characters & settings" })}
          </label>
          <textarea
            ref={charactersInputRef}
            value={characters}
            onChange={(e) => {
              markUserInput();
              setCharacters(e.target.value);
            }}
            rows={3}
            placeholder={
              isContinueMode
                ? t({
                    ja: "例: 新キャラ「◯◯」を追加。主人公は「◯◯」とは旧知の仲。口調は丁寧に。など",
                    en: "e.g., Add a new character “XX”. The protagonist already knows them. Use polite speech.",
                  })
                : t({
                    ja: "例: 大学生の主人公と、不思議な店主がいる深夜の喫茶店。主人公は最近よく見る夢の話を打ち明ける。",
                    en: "e.g., A college student visits a midnight cafe run by a mysterious owner and shares recurring dreams.",
                  })
            }
            style={{ width: "100%", padding: "0.5rem", resize: "vertical" }}
          />
          <div style={{ fontSize: "0.8rem", color: "var(--muted-text)", marginTop: "0.25rem" }}>
            {t({ ja: "現在の文字数", en: "Current chars" })}: {countChars(characters)}
          </div>
        </div>

        {!isContinueMode && (
          <div>
            <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
              {t({ ja: "雰囲気・トーン（任意）", en: "Tone (optional)" })}
            </label>
            <input
              type="text"
              value={tone}
              onChange={(e) => {
                markUserInput();
                setTone(e.target.value);
              }}
              placeholder={t({
                ja: "例: ほのぼの / 少し切ない / ダーク寄り など",
                en: "e.g., Lighthearted / A little bittersweet / Dark",
              })}
              style={{ width: "100%", padding: "0.5rem" }}
            />
            <div style={{ fontSize: "0.8rem", color: "var(--muted-text)", marginTop: "0.25rem" }}>
              {t({ ja: "現在の文字数", en: "Current chars" })}: {countChars(tone)}
            </div>
          </div>
        )}

        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
            {t({ ja: "長さ", en: "Length" })}
          </label>
          <select
            value={length}
            onChange={(e) => {
              markUserInput();
              setLength(e.target.value);
            }}
            style={{ width: "100%", padding: "0.5rem" }}
          >
            <option value="short">{t({ ja: "短め（800〜1200文字程度）", en: "Short (800–1200 chars)" })}</option>
            <option value="medium">{t({ ja: "ふつう（2000〜3000文字程度）", en: "Medium (2000–3000 chars)" })}</option>
            <option value="long">{t({ ja: "長め（4000〜6000文字程度）", en: "Long (4000–6000 chars)" })}</option>
            <option value="xlong">{t({ ja: "すごく長め（6000〜8000文字程度）", en: "Very long (6000–8000 chars)" })}</option>
            <option value="xxlong">{t({ ja: "超長め（8000〜10000文字程度）", en: "Ultra long (8000–10000 chars)" })}</option>
          </select>
        </div>

        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
            {t({ ja: "年齢区分", en: "Age rating" })}
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <input
              type="checkbox"
              checked={isR18}
              onChange={(e) => {
                markUserInput();
                setIsR18(e.target.checked);
              }}
            />
            {t({ ja: "R-18（成人向け・性的描写あり）", en: "R-18 (adult content, sexual depictions)" })}
          </label>
        </div>

        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
            {t({ ja: "使用モデル", en: "Model" })}
          </label>
          <select
            value={model}
            onChange={(e) => {
              markUserInput();
              setModel(e.target.value);
            }}
            style={{ width: "100%", padding: "0.5rem" }}
          >
            <option value="gpt-4.1-mini">{t({ ja: "GPT-4.1 Mini（高速・低コスト）", en: "GPT-4.1 Mini (fast, low cost)" })}</option>
            <option value="gpt-4.1">{t({ ja: "GPT-4.1（高品質）", en: "GPT-4.1 (high quality)" })}</option>
            <option value="gpt-4.1-preview">{t({ ja: "GPT-4.1 Preview（長文向け）", en: "GPT-4.1 Preview (long-form)" })}</option>
            <option value="gpt-4o-mini">GPT-4o Mini</option>
            <option value="gpt-4o">GPT-4o</option>
            <option value="openai/chatgpt-4o-latest">{t({ ja: "ChatGPT（OpenRouter / chatgpt-4o-latest）", en: "ChatGPT (OpenRouter / chatgpt-4o-latest)" })}</option>
            <option value="z-ai/glm-4.6">{t({ ja: "GLM 4.6（OpenRouter / z-ai/glm-4.6）", en: "GLM 4.6 (OpenRouter / z-ai/glm-4.6)" })}</option>
            <option value="moonshotai/kimi-k2">{t({ ja: "Kimi（OpenRouter / kimi-k2）", en: "Kimi (OpenRouter / kimi-k2)" })}</option>
            <option value="deepseek/deepseek-chat">{t({ ja: "DeepSeek（OpenRouter / deepseek-chat）", en: "DeepSeek (OpenRouter / deepseek-chat)" })}</option>
            <option value="deepseek:deepseek-chat">{t({ ja: "DeepSeek（公式 / deepseek-chat）", en: "DeepSeek (official / deepseek-chat)" })}</option>
            <option value="deepseek:deepseek-reasoner">{t({ ja: "DeepSeek（公式 / deepseek-reasoner）", en: "DeepSeek (official / deepseek-reasoner)" })}</option>
            <option value="google/gemini-2.0-flash-001">{t({ ja: "Gemini（OpenRouter / gemini-2.0-flash）", en: "Gemini (OpenRouter / gemini-2.0-flash)" })}</option>
            <option value="anthropic/claude-3.5-sonnet">{t({ ja: "Claude（OpenRouter / claude-3.5-sonnet）", en: "Claude (OpenRouter / claude-3.5-sonnet)" })}</option>
          </select>
        </div>

        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
            {t({ ja: "再試行モード", en: "Retry mode" })}
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <input
              type="checkbox"
              checked={retryMode}
              onChange={(e) => {
                markUserInput();
                setRetryMode(e.target.checked);
              }}
            />
            {t({
              ja: "AIの返答が空/JSON不正のときに再試行する",
              en: "Retry when AI response is empty or invalid JSON",
            })}
          </label>
          <div style={{ marginTop: "0.5rem" }}>
            <label style={{ fontSize: "0.9rem", color: "var(--muted-text)" }}>
              {t({ ja: "最大再試行回数", en: "Max retries" })}
            </label>
            <input
              type="number"
              min={0}
              max={99}
              value={retryMax}
              onChange={(e) => {
                markUserInput();
                const next = Number.parseInt(e.target.value, 10);
                if (!Number.isFinite(next)) return;
                const clamped = Math.max(0, Math.min(99, next));
                setRetryMax(clamped);
              }}
              style={{ width: "120px", marginLeft: "0.5rem", padding: "0.4rem" }}
              disabled={!retryMode}
            />
          </div>
          {showRetryStatus && (
            <div
              style={{
                marginTop: "0.4rem",
                color: "#c00000",
                fontWeight: "bold",
                fontSize: "0.9rem",
              }}
            >
              {t({ ja: "再試行回数", en: "Retry attempts" })}: {retryAttempts}
              {typeof displayRetryMax === "number" ? ` / ${displayRetryMax}` : ""}
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{
            marginTop: "0.5rem",
            padding: "0.7rem 1.2rem",
            fontWeight: "bold",
            borderRadius: "6px",
            border: "none",
            cursor: loading ? "default" : "pointer",
            opacity: loading ? 0.7 : 1,
          }}
        >
          {loading
            ? t({ ja: "生成中...", en: "Generating..." })
            : isEditMode
            ? t({ ja: "AIで編集する", en: "Edit with AI" })
            : isContinueMode
            ? t({ ja: "AIで次話を作成", en: "Create next episode with AI" })
            : t({ ja: "AI小説を生成する", en: "Generate AI novel" })}
        </button>
        <button
          type="button"
          className="btn btn-border"
          onClick={() => navigate("/ai-logs")}
        >
          {t({ ja: "利用履歴を見る", en: "View usage history" })}
        </button>
      </form>

      {premiumError && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            backgroundColor: "#fff5f5",
            border: "1px solid #f5c2c7",
            borderRadius: "6px",
            color: "#842029",
          }}
        >
          {premiumError}
        </div>
      )}

      {quotaError && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            backgroundColor: "#fff8e1",
            border: "1px solid #ffecb5",
            borderRadius: "6px",
            color: "#8a6d3b",
          }}
        >
          {quotaError}
        </div>
      )}

      {error && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            backgroundColor: "#f8d7da",
            border: "1px solid #f5c2c7",
            borderRadius: "6px",
            color: "#842029",
          }}
        >
          {error}
        </div>
      )}

      {result && (
        <div
          style={{
            marginTop: "1.5rem",
            padding: "1rem",
            border: "1px solid var(--ai-result-border)",
            borderRadius: "8px",
            backgroundColor: "var(--ai-result-bg)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
            <h2 style={{ fontSize: "1.4rem", marginBottom: "0.5rem" }}>
              {result.generated_title || t({ ja: "生成された小説", en: "Generated Novel" })}
            </h2>
            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
              <div style={{ minWidth: "180px" }}>
                <div style={{ fontSize: "0.8rem", color: "var(--muted-text)", marginBottom: "0.2rem" }}>
                  {t({ ja: "AI添削の強さ", en: "Polish intensity" })}
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={polishIntensity}
                  onChange={(e) => setPolishIntensity(Number(e.target.value))}
                  style={{ width: "180px" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--muted-text)" }}>
                  <span>{t({ ja: "軽め", en: "Light" })}</span>
                  <span>{t({ ja: "強め", en: "Heavy" })}</span>
                </div>
              </div>
              {hasActiveSelection && (
                <span style={{ fontSize: "0.85rem", color: "var(--muted-text)" }}>
                  {t({ ja: "選択部分を添削します", en: "Polishing selection only" })}
                </span>
              )}
              <button
                type="button"
                onClick={() => handlePolishText()}
                disabled={polishing || loading || continuing}
                style={{
                  height: "2.2rem",
                  alignSelf: "center",
                  padding: "0.3rem 0.8rem",
                  borderRadius: "4px",
                  border: "1px solid var(--border)",
                  cursor: polishing ? "default" : "pointer",
                  opacity: polishing ? 0.7 : 1,
                }}
              >
                {polishing
                  ? t({ ja: "AI添削中...", en: "Polishing..." })
                  : t({ ja: "AI添削", en: "Polish with AI" })}
              </button>
              <button
                type="button"
                onClick={() => handlePolishText(lastPolishContext)}
                disabled={polishing || loading || continuing || !lastPolishContext}
                style={{
                  height: "2.2rem",
                  alignSelf: "center",
                  padding: "0.3rem 0.8rem",
                  borderRadius: "4px",
                  border: "1px solid var(--border)",
                  cursor: polishing ? "default" : "pointer",
                  opacity: polishing ? 0.7 : 1,
                }}
              >
                {t({ ja: "添削し直す", en: "Redo polish" })}
              </button>
              <button
                type="button"
                onClick={handleFixJsonOutput}
                style={{
                  height: "2.2rem",
                  alignSelf: "center",
                  padding: "0.3rem 0.8rem",
                  borderRadius: "4px",
                  border: "1px solid var(--border)",
                  cursor: "pointer",
                }}
              >
                {t({ ja: "JSON出力を修正", en: "Fix JSON output" })}
              </button>
              <button
                type="button"
                onClick={handleCopyToClipboard}
                style={{
                  height: "2.2rem",
                  alignSelf: "center",
                  padding: "0.3rem 0.8rem",
                  borderRadius: "4px",
                  border: "1px solid var(--border)",
                  cursor: "pointer",
                }}
              >
                {t({ ja: "文章をコピー", en: "Copy text" })}
              </button>
              {!textEditMode ? (
                <button
                  type="button"
                  onClick={startTextEditMode}
                  style={{
                    height: "2.2rem",
                    alignSelf: "center",
                    padding: "0.3rem 0.8rem",
                    borderRadius: "4px",
                    border: "1px solid var(--border)",
                    cursor: "pointer",
                  }}
                >
                  {t({ ja: "編集モード", en: "Edit mode" })}
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={applyTextEditMode}
                    style={{
                      height: "2.2rem",
                      alignSelf: "center",
                      padding: "0.3rem 0.8rem",
                      borderRadius: "4px",
                      border: "1px solid var(--border)",
                      cursor: "pointer",
                    }}
                  >
                    {t({ ja: "編集を反映", en: "Apply edits" })}
                  </button>
                  <button
                    type="button"
                    onClick={cancelTextEditMode}
                    style={{
                      height: "2.2rem",
                      alignSelf: "center",
                      padding: "0.3rem 0.8rem",
                      borderRadius: "4px",
                      border: "1px solid var(--border)",
                      cursor: "pointer",
                    }}
                  >
                    {t({ ja: "編集を終了", en: "Exit edit mode" })}
                  </button>
                </>
              )}
            </div>
          </div>

          <div style={{ fontSize: "0.85rem", color: "var(--muted-text)", marginBottom: "0.5rem" }}>
            {result.model && <span>{t({ ja: "モデル", en: "Model" })}: {result.model}</span>}
            {typeof result.used_tokens === "number" && (
              <span>
                {`${result.model ? " / " : ""}${t({ ja: "使用トークン", en: "Tokens used" })}: ${result.used_tokens}`}
              </span>
            )}
            <span>
              {`${result.model || typeof result.used_tokens === "number" ? " / " : ""}${t({ ja: "文字数", en: "Chars" })}: ${countChars(result.body)}`}
            </span>
            {continuationBody && (
              <span>
                {` / ${t({ ja: "続き文字数", en: "Continuation chars" })}: ${countChars(continuationBody)} / ${t({ ja: "合計文字数", en: "Total chars" })}: ${countChars(getCombinedBody())}`}
              </span>
            )}
          </div>

          {textEditMode ? (
            <textarea
              value={textEditValue}
              onChange={(e) => setTextEditValue(e.target.value)}
              rows={18}
              style={{
                width: "100%",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                backgroundColor: "var(--ai-result-surface)",
                padding: "0.75rem",
                borderRadius: "6px",
                border: "1px solid var(--border)",
                lineHeight: 1.6,
                resize: "vertical",
              }}
            />
          ) : (
            <pre
              ref={resultBodyRef}
              className="ai-result-body"
              style={{
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                backgroundColor: "var(--ai-result-surface)",
                padding: "0.75rem",
                borderRadius: "6px",
                border: "1px solid var(--border)",
                maxHeight: "600px",
                overflowY: "auto",
                lineHeight: 1.6,
              }}
            >
              <span>{result.body}</span>
              {continuationBody && (
                <span style={{ color: "#1b7f2a" }}>{`\n\n${continuationBody}`}</span>
              )}
            </pre>
          )}

          <div style={{ marginTop: "1rem", display: "grid", gap: "0.75rem" }}>
            {polishPreview && (
              <div
                style={{
                  padding: "0.75rem",
                  borderRadius: "6px",
                  border: "1px solid var(--border)",
                  backgroundColor: "var(--ai-result-surface)",
                }}
              >
                <div style={{ fontWeight: "bold", marginBottom: "0.5rem" }}>
                  {t({ ja: "AI添削の比較", en: "Polish comparison" })}
                </div>
                <div style={{ fontSize: "0.85rem", color: "var(--muted-text)", marginBottom: "0.5rem" }}>
                  {t({ ja: "選択部分の変更内容を確認してください。", en: "Review the changes for the selected text." })}
                </div>
                <div style={{ display: "grid", gap: "0.5rem" }}>
                  <div>
                    <div style={{ fontSize: "0.8rem", color: "var(--muted-text)", marginBottom: "0.25rem" }}>
                      {t({ ja: "元の文章", en: "Original" })}
                    </div>
                    <pre
                      style={{
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                        backgroundColor: "var(--ai-result-bg)",
                        padding: "0.5rem",
                        borderRadius: "6px",
                        border: "1px solid var(--border)",
                        maxHeight: "200px",
                        overflowY: "auto",
                      }}
                    >
                      {polishPreview.context?.selectedText || ""}
                    </pre>
                  </div>
                  <div>
                    <div style={{ fontSize: "0.8rem", color: "var(--muted-text)", marginBottom: "0.25rem" }}>
                      {t({ ja: "AI添削後", en: "Polished" })}
                    </div>
                    <pre
                      style={{
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                        backgroundColor: "var(--ai-result-bg)",
                        padding: "0.5rem",
                        borderRadius: "6px",
                        border: "1px solid var(--border)",
                        maxHeight: "200px",
                        overflowY: "auto",
                      }}
                    >
                      {polishPreview.proposedText || ""}
                    </pre>
                  </div>
                </div>
                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
                  <button
                    type="button"
                    className="btn btn-border"
                    onClick={handleApplyPolishPreview}
                  >
                    {t({ ja: "差し替える", en: "Apply changes" })}
                  </button>
                  <button
                    type="button"
                    className="btn btn-border"
                    onClick={handleCancelPolishPreview}
                  >
                    {t({ ja: "キャンセル", en: "Cancel" })}
                  </button>
                </div>
              </div>
            )}
            {(!isContinueMode || isEditMode) && (
              <div
                style={{
                  padding: "0.75rem",
                  borderRadius: "6px",
                  border: "1px solid var(--border)",
                  backgroundColor: "var(--ai-result-surface)",
                }}
              >
                <div style={{ fontWeight: "bold", marginBottom: "0.5rem" }}>
                  {t({ ja: "続きを作成する", en: "Generate continuation" })}
                </div>
                <div style={{ fontSize: "0.9rem", color: "var(--muted-text)", marginBottom: "0.5rem" }}>
                  {t({
                    ja: "直前の生成結果と入力項目（タイトルのイメージ〜使用モデル）を使って続き部分を生成します。",
                    en: "Generate a continuation using the latest result and input fields.",
                  })}
                </div>
                <button
                  type="button"
                  onClick={handleGenerateContinuation}
                  disabled={continuing || loading}
                  style={{
                    padding: "0.6rem 1rem",
                    fontWeight: "bold",
                    borderRadius: "6px",
                    border: "1px solid #ccc",
                    cursor: continuing ? "default" : "pointer",
                    opacity: continuing ? 0.7 : 1,
                  }}
                >
                  {continuing
                    ? t({ ja: "続き作成中...", en: "Creating continuation..." })
                    : t({ ja: "続きを作成する", en: "Generate continuation" })}
                </button>
                {result?.body && (
                  <button
                    type="button"
                    onClick={handleRedoContinuation}
                    disabled={continuing || loading}
                    style={{
                      padding: "0.6rem 1rem",
                      fontWeight: "bold",
                      borderRadius: "6px",
                      border: "1px solid #ccc",
                      cursor: continuing ? "default" : "pointer",
                      opacity: continuing ? 0.7 : 1,
                      marginLeft: "0.5rem",
                    }}
                  >
                    {t({ ja: "続き作成をやり直す", en: "Redo continuation" })}
                  </button>
                )}
              </div>
            )}
            <div
              style={{
                padding: "0.75rem",
                borderRadius: "6px",
                border: "1px solid var(--border)",
                backgroundColor: "var(--ai-result-surface)",
              }}
            >
              <div style={{ fontWeight: "bold", marginBottom: "0.5rem" }}>
                {t({ ja: "投稿する", en: "Post" })}
              </div>

              {(isContinueMode || isEditMode) && (
                <div style={{ marginBottom: "0.5rem" }}>
                  <div
                    style={{
                      fontSize: "0.9rem",
                      color: "var(--muted-text)",
                      marginBottom: "0.25rem",
                    }}
                  >
                    {t({
                      ja: "既存小説に最新話として投稿します。",
                      en: "Post this as the latest episode to the existing novel.",
                    })}
                  </div>
                  {continueInfoError && (
                    <div style={{ fontSize: "0.9rem", color: "#842029", marginBottom: "0.5rem" }}>
                      {continueInfoError}
                    </div>
                  )}
                  <label style={{ display: "block", fontSize: "0.9rem", marginBottom: "0.25rem" }}>
                    {t({ ja: "エピソードタイトル（任意）", en: "Episode title (optional)" })}
                  </label>
                  <input
                    type="text"
                    value={postEpisodeTitle}
                    onChange={(e) => setPostEpisodeTitle(e.target.value)}
                    placeholder={t({ ja: "例: ふたりの約束", en: "e.g., A Promise Between Two" })}
                    style={{ width: "100%", padding: "0.5rem" }}
                    disabled={posting}
                  />
                  <div style={{ fontSize: "0.8rem", color: "var(--muted-text)", marginTop: "0.25rem" }}>
                    {t({ ja: "現在の文字数", en: "Current chars" })}: {countChars(postEpisodeTitle)}
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "var(--muted-text)", marginTop: "0.25rem" }}>
                    {continueNovelId ? (
                      <span>
                        {t({ ja: "投稿先", en: "Destination" })}: novel_id={continueNovelId}
                        {typeof continueEpisodeNumber === "number"
                          ? t(
                              { ja: "（前話: 第{{num}}話）", en: " (Previous: Episode {{num}})" },
                              { num: continueEpisodeNumber }
                            )
                          : ""}
                      </span>
                    ) : (
                      <span>{t({ ja: "投稿先: 読み込み中...", en: "Destination: loading..." })}</span>
                    )}
                  </div>
                </div>
              )}

              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                {(isContinueMode || isEditMode) && (
                  <button
                    type="button"
                    onClick={handlePostAsNextEpisode}
                    disabled={posting || !continueNovelId || canPostToContinueNovel === false}
                    style={{
                      padding: "0.6rem 1rem",
                      fontWeight: "bold",
                      borderRadius: "6px",
                      border: "1px solid #ccc",
                      cursor: posting ? "default" : "pointer",
                    opacity: posting ? 0.7 : 1,
                  }}
                >
                    {posting
                      ? t({ ja: "投稿中...", en: "Posting..." })
                      : t({ ja: "最新話として投稿", en: "Post as latest episode" })}
                  </button>
                )}
                <button
                  type="button"
                  onClick={handlePostAsNewNovel}
                  disabled={posting}
                  style={{
                    padding: "0.6rem 1rem",
                    fontWeight: "bold",
                    borderRadius: "6px",
                    border: "1px solid #ccc",
                    cursor: posting ? "default" : "pointer",
                    opacity: posting ? 0.7 : 1,
                  }}
                >
                  {posting
                    ? t({ ja: "投稿中...", en: "Posting..." })
                    : t({ ja: "新しい小説として投稿（第1話）", en: "Post as a new novel (Episode 1)" })}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
