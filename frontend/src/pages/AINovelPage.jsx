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
const AI_NOVEL_SEGMENT_PREFS_KEY = "ai_novel_segment_prefs_v1";
const PENDING_AI_JOB_KEY = "pending_ai_job_v1";
const DEFAULT_AI_NOVEL_MODEL = "gpt-5-mini";
const REVISION_CHUNK_MAX_CHARS = 3200;
const COMMENT_REVISION_OUTPUT_RETRY_MAX = 5;
const SEGMENT_TARGET_CHARS = 2000;
const SEGMENT_COUNT_MIN = 1;
const SEGMENT_COUNT_MAX = 30;
const CHUNK_BLOCK_TIMEOUT_MS = 5 * 60 * 1000;

function clampSegmentCount(value) {
  const n = Number.parseInt(String(value), 10);
  if (!Number.isFinite(n)) return SEGMENT_COUNT_MIN;
  return Math.max(SEGMENT_COUNT_MIN, Math.min(SEGMENT_COUNT_MAX, n));
}

function makeSegmentPlanItem(index) {
  return {
    id: `seg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}-${index}`,
    instruction: "",
  };
}

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

function buildLineDiffSegments(beforeText, afterText) {
  const beforeLines = String(beforeText || "").split("\n");
  const afterLines = String(afterText || "").split("\n");
  const n = beforeLines.length;
  const m = afterLines.length;
  const dp = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0));

  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      if (beforeLines[i] === afterLines[j]) {
        dp[i][j] = dp[i + 1][j + 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  const unchangedAfterIndexes = new Set();
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (beforeLines[i] === afterLines[j]) {
      unchangedAfterIndexes.add(j);
      i += 1;
      j += 1;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      i += 1;
    } else {
      j += 1;
    }
  }

  return afterLines.map((line, idx) => ({
    text: idx === afterLines.length - 1 ? line : `${line}\n`,
    changed: !unchangedAfterIndexes.has(idx),
  }));
}

function splitTextForRevision(text, maxChars = 7000) {
  const source = String(text || "");
  if (!source) return [];
  if (source.length <= maxChars) {
    return [{ start: 0, end: source.length, text: source }];
  }

  const chunks = [];
  let start = 0;
  while (start < source.length) {
    let end = Math.min(start + maxChars, source.length);
    if (end < source.length) {
      const windowText = source.slice(start, end);
      const minCut = Math.floor(maxChars * 0.6);
      const candidates = [
        windowText.lastIndexOf("\n\n"),
        windowText.lastIndexOf("\n"),
        windowText.lastIndexOf("。"),
        windowText.lastIndexOf("！"),
        windowText.lastIndexOf("？"),
      ].filter((idx) => idx >= minCut);
      if (candidates.length > 0) {
        const cut = Math.max(...candidates);
        const markerLen = windowText.slice(cut, cut + 2) === "\n\n" ? 2 : 1;
        end = start + cut + markerLen;
      }
    }
    if (end <= start) {
      end = Math.min(start + maxChars, source.length);
    }
    chunks.push({
      start,
      end,
      text: source.slice(start, end),
    });
    start = end;
  }
  return chunks;
}

function getCommentRevisionOutputIssue(text) {
  const raw = String(text || "");
  if (!raw.trim()) return "empty";

  const stripFence = (s) => {
    const t = (s || "").trim();
    if (!t.startsWith("```")) return t;
    const lines = t.split("\n");
    if (lines.length && lines[0].startsWith("```")) lines.shift();
    if (lines.length && lines[lines.length - 1].trim() === "```") lines.pop();
    return lines.join("\n").trim();
  };

  const cleaned = stripFence(raw);
  const looksLikeJson =
    cleaned.startsWith("{")
    || cleaned.startsWith("[")
    || cleaned.includes('"body"')
    || cleaned.includes("'body'");
  if (!looksLikeJson) return "";

  try {
    const parsed = JSON.parse(cleaned);
    if (!parsed || typeof parsed !== "object") return "json_invalid";
    const extracted =
      (typeof parsed.body === "string" && parsed.body)
      || (typeof parsed.text === "string" && parsed.text)
      || (typeof parsed.content === "string" && parsed.content)
      || (typeof parsed.story === "string" && parsed.story)
      || "";
    if (!String(extracted || "").trim()) return "json_empty_body";
    return "";
  } catch {
    return "json_parse_error";
  }
}

function getGenerateOutputIssue(payload) {
  const rawBody = String(payload?.body || "");
  const rawIssue = getCommentRevisionOutputIssue(rawBody);
  const normalized = normalizeAINovelResponse(payload || {});
  const normalizedBody = String(normalized?.body || "");
  if (!normalizedBody.trim()) return "empty";
  if (rawIssue) return rawIssue;
  return "";
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
  const [model, setModel] = useState(DEFAULT_AI_NOVEL_MODEL);
  const [isR18, setIsR18] = useState(false);
  const [retryMode, setRetryMode] = useState(false);
  const [retryMax, setRetryMax] = useState(2);
  const [retryAttempts, setRetryAttempts] = useState(0);
  const [activeRetryMax, setActiveRetryMax] = useState(null);
  const [chunkedGenerationEnabled, setChunkedGenerationEnabled] = useState(false);
  const [chunkedGenerationCount, setChunkedGenerationCount] = useState(2);
  const [chunkedGenerationPlans, setChunkedGenerationPlans] = useState([
    makeSegmentPlanItem(1),
    makeSegmentPlanItem(2),
  ]);
  const [chunkedProgressActive, setChunkedProgressActive] = useState(false);
  const [chunkedProgressBlock, setChunkedProgressBlock] = useState(1);
  const [chunkedProgressPercent, setChunkedProgressPercent] = useState(0);
  const [chunkedCompletedBlocks, setChunkedCompletedBlocks] = useState(0);

  // ★ ここが「続き生成モード」用の state
  const [isContinueMode, setIsContinueMode] = useState(false);
  const [episodeId, setEpisodeId] = useState(null);
  const [continueNovelId, setContinueNovelId] = useState(null);
  const [continueEpisodeNumber, setContinueEpisodeNumber] = useState(null);
  const [canPostToContinueNovel, setCanPostToContinueNovel] = useState(null); // null=判定中, true/false
  const [continueInfoError, setContinueInfoError] = useState("");
  const [isEditMode, setIsEditMode] = useState(false);
  const [editSourceBody, setEditSourceBody] = useState("");
  const [editEpisodeId, setEditEpisodeId] = useState(null);

  const [loading, setLoading] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const [autoFillLoading, setAutoFillLoading] = useState(false);
  const [posting, setPosting] = useState(false);
  const [polishing, setPolishing] = useState(false);
  const [polishIntensity, setPolishIntensity] = useState(50);
  const [lastPolishContext, setLastPolishContext] = useState(null);
  const [lastPolishScope, setLastPolishScope] = useState("full");
  const [hasActiveSelection, setHasActiveSelection] = useState(false);
  const [polishPreview, setPolishPreview] = useState(null);
  const [revisionCommentInput, setRevisionCommentInput] = useState("");
  const [revisionComments, setRevisionComments] = useState([]);
  const [lastRevisionTargetInfo, setLastRevisionTargetInfo] = useState(null);
  const [revisingByComment, setRevisingByComment] = useState(false);
  const [revisionChatScope, setRevisionChatScope] = useState("full");
  const [commentRevisionDiffSegments, setCommentRevisionDiffSegments] = useState([]);
  const [commentRevisionUndoStack, setCommentRevisionUndoStack] = useState([]);
  const [commentRevisionHasActiveDiff, setCommentRevisionHasActiveDiff] = useState(false);
  const [error, setError] = useState("");
  const [quotaError, setQuotaError] = useState("");
  const [premiumError, setPremiumError] = useState("");
  const [autoFillError, setAutoFillError] = useState("");
  const [autoFillPreview, setAutoFillPreview] = useState(null);
  const [guestRemaining, setGuestRemaining] = useState(null);
  const [userRemaining, setUserRemaining] = useState(null);
  const [userPaidRemaining, setUserPaidRemaining] = useState(0);
  const [addonUnitGenerations, setAddonUnitGenerations] = useState(80);
  const [addonUnitPriceYen, setAddonUnitPriceYen] = useState(1000);
  const [addonCheckoutLoading, setAddonCheckoutLoading] = useState(false);
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
  const targetTotalChars = chunkedGenerationCount * SEGMENT_TARGET_CHARS;
  const canUseChunkedGeneration = !isContinueMode && !isEditMode;
  const isLengthOverriddenByChunkedGeneration = canUseChunkedGeneration && chunkedGenerationEnabled;
  const activeProgressInstruction = (
    chunkedGenerationPlans[chunkedProgressBlock - 1]?.instruction || ""
  ).trim();
  const showRetryStatus =
    (loading || continuing || polishing || revisingByComment || retryAttempts > 0) &&
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
  const chunkedGenerateRetryRef = useRef({
    enabled: false,
    attempts: 0,
    max: 0,
    endpoint: "",
    requestBody: null,
  });
  const localDraftRef = useRef(null);
  const draftSaveTimerRef = useRef(null);
  const hasUserInputRef = useRef(false);
  const segmentPrefsLoadedRef = useRef(false);
  const chunkedProgressTimerRef = useRef(null);
  const [pendingJob, setPendingJob] = useState(null);
  const hasAuthToken = Boolean(getAuthToken());
  const markUserInput = () => {
    hasUserInputRef.current = true;
  };

  const setChunkPlanCount = (nextCountRaw) => {
    const nextCount = clampSegmentCount(nextCountRaw);
    setChunkedGenerationCount(nextCount);
    setChunkedGenerationPlans((prev) => {
      const safePrev = Array.isArray(prev) ? prev : [];
      if (safePrev.length === nextCount) return safePrev;
      if (safePrev.length > nextCount) return safePrev.slice(0, nextCount);
      const appended = [...safePrev];
      for (let i = safePrev.length; i < nextCount; i += 1) {
        appended.push(makeSegmentPlanItem(i + 1));
      }
      return appended;
    });
  };

  const stopChunkedProgress = (complete = false) => {
    if (chunkedProgressTimerRef.current) {
      clearInterval(chunkedProgressTimerRef.current);
      chunkedProgressTimerRef.current = null;
    }
    setChunkedProgressActive(false);
    if (complete) {
      setChunkedProgressPercent(100);
      setChunkedProgressBlock(chunkedGenerationCount);
      setChunkedCompletedBlocks(chunkedGenerationCount);
    } else {
      setChunkedProgressPercent(0);
      setChunkedProgressBlock(1);
      setChunkedCompletedBlocks(0);
    }
  };

  const resetChunkedGenerateRetryContext = () => {
    resetChunkedGenerateRetryContext();
  };

  const startChunkedProgress = (count) => {
    const safeCount = clampSegmentCount(count);
    stopChunkedProgress(false);
    setChunkedProgressActive(true);
    setChunkedProgressBlock(1);
    setChunkedProgressPercent(3);
    setChunkedCompletedBlocks(0);
    let tick = 0;
    chunkedProgressTimerRef.current = setInterval(() => {
      tick += 1;
      const uiBlock = Math.min(safeCount, Math.floor(tick / 5) + 1);
      const uiPercent = Math.min(95, 3 + Math.floor((tick / (safeCount * 6)) * 90));
      setChunkedProgressBlock(uiBlock);
      setChunkedProgressPercent(uiPercent);
      setChunkedCompletedBlocks(Math.max(0, uiBlock - 1));
    }, 1000);
  };

  useEffect(() => () => {
    if (chunkedProgressTimerRef.current) {
      clearInterval(chunkedProgressTimerRef.current);
      chunkedProgressTimerRef.current = null;
    }
  }, []);

  const handleAddChunkPlan = () => {
    markUserInput();
    if (chunkedGenerationCount >= SEGMENT_COUNT_MAX) return;
    setChunkPlanCount(chunkedGenerationCount + 1);
  };

  const handleRemoveChunkPlan = (index) => {
    markUserInput();
    if (chunkedGenerationCount <= SEGMENT_COUNT_MIN) return;
    setChunkedGenerationPlans((prev) => {
      const safePrev = Array.isArray(prev) ? prev : [];
      const next = safePrev.filter((_, i) => i !== index);
      return next.length > 0 ? next : [makeSegmentPlanItem(1)];
    });
    setChunkedGenerationCount((prev) => Math.max(SEGMENT_COUNT_MIN, Number(prev || 1) - 1));
  };

  const handleChangeChunkPlanInstruction = (index, value) => {
    markUserInput();
    setChunkedGenerationPlans((prev) =>
      (prev || []).map((item, i) => (i === index ? { ...item, instruction: value } : item))
    );
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
        if (typeof data?.user_paid_remaining === "number") {
          setUserPaidRemaining(Math.max(0, Number(data.user_paid_remaining || 0)));
        } else {
          setUserPaidRemaining(0);
        }
        if (typeof data?.addon_unit_generations === "number") {
          setAddonUnitGenerations(Math.max(1, Number(data.addon_unit_generations || 0)));
        }
        if (typeof data?.addon_unit_price_yen === "number") {
          setAddonUnitPriceYen(Math.max(1, Number(data.addon_unit_price_yen || 0)));
        }
      } catch (e) {
        console.error("failed to load ai remaining", e);
      }
    };

    fetchRemaining();
  }, []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(AI_NOVEL_SEGMENT_PREFS_KEY);
      if (!raw) {
        segmentPrefsLoadedRef.current = true;
        return;
      }
      const parsed = JSON.parse(raw);
      if (typeof parsed?.enabled === "boolean") {
        setChunkedGenerationEnabled(parsed.enabled);
      }
      const savedCount = clampSegmentCount(
        typeof parsed?.count === "number" ? parsed.count : SEGMENT_COUNT_MIN
      );
      setChunkedGenerationCount(savedCount);
      if (Array.isArray(parsed?.plans) && parsed.plans.length > 0) {
        const normalized = parsed.plans
          .filter((item) => item && typeof item === "object")
          .map((item, idx) => ({
            id: typeof item.id === "string" && item.id ? item.id : makeSegmentPlanItem(idx + 1).id,
            instruction: String(item.instruction || ""),
          }));
        if (normalized.length >= savedCount) {
          setChunkedGenerationPlans(normalized.slice(0, savedCount));
        } else {
          const padded = [...normalized];
          for (let i = normalized.length; i < savedCount; i += 1) {
            padded.push(makeSegmentPlanItem(i + 1));
          }
          setChunkedGenerationPlans(padded);
        }
      }
    } catch (e) {
      console.error("failed to load ai segment prefs", e);
    } finally {
      segmentPrefsLoadedRef.current = true;
    }
  }, []);

  useEffect(() => {
    if (!segmentPrefsLoadedRef.current) return;
    try {
      const payload = {
        enabled: chunkedGenerationEnabled,
        count: clampSegmentCount(chunkedGenerationCount),
        plans: (chunkedGenerationPlans || [])
          .slice(0, clampSegmentCount(chunkedGenerationCount))
          .map((item, idx) => ({
            id: typeof item?.id === "string" && item.id ? item.id : makeSegmentPlanItem(idx + 1).id,
            instruction: String(item?.instruction || ""),
          })),
      };
      localStorage.setItem(AI_NOVEL_SEGMENT_PREFS_KEY, JSON.stringify(payload));
    } catch (e) {
      console.error("failed to save ai segment prefs", e);
    }
  }, [chunkedGenerationEnabled, chunkedGenerationCount, chunkedGenerationPlans]);

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

  const hasUrlModeOverride = () => {
    if (typeof window === "undefined") return false;
    const params = new URLSearchParams(window.location.search);
    return Boolean(params.get("episode_id") || params.get("edit_episode_id"));
  };

  const applyDraft = (draft, options = {}) => {
    if (!draft || typeof draft !== "object") return;
    const preserveUrlMode = Boolean(options?.preserveUrlMode);
    const skipModeOverwrite = preserveUrlMode && hasUrlModeOverride();
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
    if (typeof draft.chunkedGenerationEnabled === "boolean") {
      setChunkedGenerationEnabled(draft.chunkedGenerationEnabled);
    }
    const draftChunkCount = clampSegmentCount(
      typeof draft.chunkedGenerationCount === "number" ? draft.chunkedGenerationCount : 2
    );
    setChunkedGenerationCount(draftChunkCount);
    if (Array.isArray(draft.chunkedGenerationPlans) && draft.chunkedGenerationPlans.length > 0) {
      const normalizedPlans = draft.chunkedGenerationPlans
        .filter((item) => item && typeof item === "object")
        .map((item, idx) => ({
          id: typeof item.id === "string" && item.id ? item.id : makeSegmentPlanItem(idx + 1).id,
          instruction: String(item.instruction || ""),
        }));
      if (normalizedPlans.length >= draftChunkCount) {
        setChunkedGenerationPlans(normalizedPlans.slice(0, draftChunkCount));
      } else {
        const padded = [...normalizedPlans];
        for (let i = normalizedPlans.length; i < draftChunkCount; i += 1) {
          padded.push(makeSegmentPlanItem(i + 1));
        }
        setChunkedGenerationPlans(padded);
      }
    } else {
      setChunkedGenerationPlans(Array.from({ length: draftChunkCount }, (_, idx) => makeSegmentPlanItem(idx + 1)));
    }
    if (!skipModeOverwrite && typeof draft.isContinueMode === "boolean") {
      setIsContinueMode(Boolean(draft.isContinueMode && draftEpisodeId !== null));
    }
    if (!skipModeOverwrite) {
      setEpisodeId(draftEpisodeId);
    }
    if (!skipModeOverwrite && (typeof draft.continueNovelId === "number" || draft.continueNovelId === null))
      setContinueNovelId(draft.continueNovelId);
    if (
      !skipModeOverwrite
      && (typeof draft.continueEpisodeNumber === "number" || draft.continueEpisodeNumber === null)
    )
      setContinueEpisodeNumber(draft.continueEpisodeNumber);
    if (!skipModeOverwrite && typeof draft.isEditMode === "boolean") setIsEditMode(draft.isEditMode);
    if (!skipModeOverwrite && typeof draft.editSourceBody === "string") setEditSourceBody(draft.editSourceBody);
    if (
      !skipModeOverwrite
      && (typeof draft.editEpisodeId === "number" || draft.editEpisodeId === null)
    ) {
      setEditEpisodeId(draft.editEpisodeId);
    }
    if (draft.result && typeof draft.result === "object") setResult(draft.result);
    if (typeof draft.continuationBody === "string") setContinuationBody(draft.continuationBody);
    if (typeof draft.postEpisodeTitle === "string") setPostEpisodeTitle(draft.postEpisodeTitle);
    if (draft.lastGenerateParams && typeof draft.lastGenerateParams === "object") {
      setLastGenerateParams(draft.lastGenerateParams);
    }
    if (typeof draft.lastPolishScope === "string") {
      setLastPolishScope(draft.lastPolishScope === "selection" ? "selection" : "full");
    }
    if (typeof draft.revisionCommentInput === "string") setRevisionCommentInput(draft.revisionCommentInput);
    if (typeof draft.revisionChatScope === "string") {
      setRevisionChatScope(draft.revisionChatScope === "selection" ? "selection" : "full");
    }
    if (Array.isArray(draft.revisionComments)) {
      setRevisionComments(
        draft.revisionComments
          .filter((item) => item && typeof item === "object")
          .map((item) => ({
            role: item.role === "assistant" ? "assistant" : "user",
            content: String(item.content || ""),
            at: typeof item.at === "string" ? item.at : new Date().toISOString(),
          }))
          .filter((item) => item.content.trim())
      );
    }
    if (Array.isArray(draft.commentRevisionUndoStack)) {
      setCommentRevisionUndoStack(
        draft.commentRevisionUndoStack
          .filter((item) => typeof item === "string")
          .map((item) => String(item))
      );
    } else if (typeof draft.commentRevisionUndoBody === "string") {
      const legacyUndoBody = String(draft.commentRevisionUndoBody || "");
      setCommentRevisionUndoStack(legacyUndoBody ? [legacyUndoBody] : []);
    }
    if (typeof draft.commentRevisionHasActiveDiff === "boolean") {
      setCommentRevisionHasActiveDiff(draft.commentRevisionHasActiveDiff);
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
    chunkedGenerationEnabled,
    chunkedGenerationCount,
    chunkedGenerationPlans,
    isContinueMode,
    episodeId,
    continueNovelId,
    continueEpisodeNumber,
    isEditMode,
    editSourceBody,
    editEpisodeId,
    result,
    continuationBody,
    postEpisodeTitle,
    lastGenerateParams,
    lastPolishScope,
    revisionCommentInput,
    revisionChatScope,
    revisionComments,
    commentRevisionUndoStack,
    commentRevisionUndoBody:
      commentRevisionUndoStack.length > 0
        ? commentRevisionUndoStack[commentRevisionUndoStack.length - 1]
        : "",
    commentRevisionHasActiveDiff,
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
    stopChunkedProgress(true);
    const normalized = normalizeAINovelResponse(payload || {});
    setResult(normalized);
    chunkedGenerateRetryRef.current = {
      enabled: false,
      attempts: 0,
      max: 0,
      endpoint: "",
      requestBody: null,
    };
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

  const retryChunkedGenerateForInvalidOutput = async (issue) => {
    const ctx = chunkedGenerateRetryRef.current || {};
    if (!ctx.enabled || !ctx.endpoint || !ctx.requestBody) return false;
    const nextAttempts = Number(ctx.attempts || 0) + 1;
    chunkedGenerateRetryRef.current = {
      ...ctx,
      attempts: nextAttempts,
    };
    setRetryAttempts(nextAttempts);
    setActiveRetryMax(null);
    setError(
      t(
        {
          ja: "分割生成の出力が不正（{{issue}}）だったため、自動で再生成しています...",
          en: "Chunked output was invalid ({{issue}}). Retrying automatically...",
        },
        { issue: String(issue || "unknown") }
      )
    );
    const token = getAuthToken();
    const res = await fetchWithTimeout(
      ctx.endpoint,
      {
        method: "POST",
        headers: token
          ? {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            }
          : { "Content-Type": "application/json" },
        body: JSON.stringify(ctx.requestBody),
      },
      20000
    );
    if (!res.ok) {
      return false;
    }
    const data = await res.json().catch(() => ({}));
    const nextJobId = Number(data?.job_id);
    if (!Number.isFinite(nextJobId) || nextJobId <= 0) {
      return false;
    }
    startJobPolling({ job_id: nextJobId, kind: "generate" });
    return true;
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
        stopChunkedProgress(false);
        setContinuing(false);
        setRetryAttempts(0);
        setActiveRetryMax(null);
        resetChunkedGenerateRetryContext();
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
        stopChunkedProgress(false);
        setContinuing(false);
        setRetryAttempts(0);
        setActiveRetryMax(null);
        resetChunkedGenerateRetryContext();
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
        if (job?.kind === "generate") {
          const outputIssue = getGenerateOutputIssue(data.response || {});
          if (outputIssue) {
            const retried = await retryChunkedGenerateForInvalidOutput(outputIssue);
            if (retried) {
              return;
            }
            if (!chunkedGenerateRetryRef.current?.enabled) {
              handleJobResult(job, data.response);
              stopJobPolling();
              clearPendingAiJob();
              setPendingJob(null);
              return;
            }
            setError(
              t(
                {
                  ja: "分割生成の出力が不正（{{issue}}）で、自動再生成ジョブの起動に失敗しました。",
                  en: "Chunked output was invalid ({{issue}}) and failed to enqueue auto-retry job.",
                },
                { issue: String(outputIssue || "unknown") }
              )
            );
            stopJobPolling();
            stopChunkedProgress(false);
            setLoading(false);
            setContinuing(false);
            resetChunkedGenerateRetryContext();
            clearPendingAiJob();
            setPendingJob(null);
            return;
          }
        }
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
        stopChunkedProgress(false);
        setContinuing(false);
        setRetryAttempts(0);
        setActiveRetryMax(null);
        resetChunkedGenerateRetryContext();
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
    setModel(DEFAULT_AI_NOVEL_MODEL);
    setIsR18(false);
    setRetryMode(false);
    setRetryMax(2);
    setChunkedGenerationEnabled(false);
    setChunkedGenerationCount(2);
    setChunkedGenerationPlans([makeSegmentPlanItem(1), makeSegmentPlanItem(2)]);
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
      applyDraft(draft, { preserveUrlMode: true });
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
          applyDraft(serverDraft, { preserveUrlMode: true });
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
    chunkedGenerationEnabled,
    chunkedGenerationCount,
    chunkedGenerationPlans,
    isContinueMode,
    episodeId,
    continueNovelId,
    continueEpisodeNumber,
    isEditMode,
    editSourceBody,
    editEpisodeId,
    result,
    continuationBody,
    postEpisodeTitle,
    lastGenerateParams,
    lastPolishScope,
    revisionCommentInput,
    revisionChatScope,
    revisionComments,
    commentRevisionUndoStack,
    commentRevisionHasActiveDiff,
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
    chunkedGenerationEnabled,
    chunkedGenerationCount,
    chunkedGenerationPlans,
    isContinueMode,
    episodeId,
    continueNovelId,
    continueEpisodeNumber,
    isEditMode,
    editSourceBody,
    editEpisodeId,
    result,
    continuationBody,
    postEpisodeTitle,
    lastGenerateParams,
    lastPolishScope,
    revisionCommentInput,
    revisionChatScope,
    revisionComments,
    commentRevisionUndoStack,
    commentRevisionHasActiveDiff,
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

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("mode") !== "new_novel") return;
    setIsContinueMode(false);
    setEpisodeId(null);
    setContinueNovelId(null);
    setContinueEpisodeNumber(null);
    setCanPostToContinueNovel(null);
    setContinueInfoError("");
    setIsEditMode(false);
    setEditSourceBody("");
    setEditEpisodeId(null);
    setPostEpisodeTitle("");
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const addon = (params.get("addon") || "").trim();
    if (!addon) return;
    if (addon === "success") {
      setQuotaError(
        t({
          ja: "追加課金が完了しました。予備回数を反映しています...",
          en: "Add-on payment completed. Refreshing your backup generations...",
        })
      );
      const token = getAuthToken();
      fetch("/api/ai/novels/remaining", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
        .then((res) => res.json().catch(() => ({})))
        .then((data) => {
          if (typeof data?.user_remaining === "number") setUserRemaining(data.user_remaining);
          if (typeof data?.user_paid_remaining === "number")
            setUserPaidRemaining(Math.max(0, Number(data.user_paid_remaining || 0)));
          if (typeof data?.addon_unit_generations === "number")
            setAddonUnitGenerations(Math.max(1, Number(data.addon_unit_generations || 0)));
          if (typeof data?.addon_unit_price_yen === "number")
            setAddonUnitPriceYen(Math.max(1, Number(data.addon_unit_price_yen || 0)));
        })
        .catch(() => {});
    } else if (addon === "cancel") {
      setQuotaError(
        t({
          ja: "追加課金はキャンセルされました。",
          en: "Add-on payment was canceled.",
        })
      );
    }
  }, []);

  // ★ URL の ?episode_id=xxx を拾って「続きモード」にする
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const eid = params.get("episode_id");
    if (!eid) return;

    setIsContinueMode(true);
    setEpisodeId(eid);
    setEditEpisodeId(null);
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
    const parsedEditEpisodeId = Number(editEid);
    const safeEditEpisodeId = Number.isFinite(parsedEditEpisodeId) ? parsedEditEpisodeId : null;

    setIsEditMode(true);
    setIsContinueMode(false);
    setEpisodeId(null);
    setEditEpisodeId(safeEditEpisodeId);
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

  const buildSegmentedNovelPrompt = (params, planItems, segmentChars = SEGMENT_TARGET_CHARS) => {
    const safePlans = (planItems || []).map((item, idx) => ({
      index: idx + 1,
      instruction: String(item?.instruction || "").trim(),
    }));
    const chunkCount = Math.max(1, safePlans.length);
    const totalChars = chunkCount * segmentChars;
    const r18Note = params.isR18
      ? "成人向けの内容を許可します。性的描写を含めても構いません。"
      : "一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。";
    const titleHintText = params.titleHint || "指定なし";
    const genreText = params.genre || "指定なし";
    const toneText = params.tone || "指定なし";
    const charactersText = params.characters || "指定なし";
    const scopeLines = safePlans.map((item) => {
      const start = (item.index - 1) * segmentChars + 1;
      const end = item.index * segmentChars;
      const label = `第${item.index}ブロック（目安 ${start}〜${end} 文字）`;
      const body = item.instruction || "（特記事項なし。前後と自然につながる展開にする）";
      return `- ${label}: ${body}`;
    });

    return [
      "あなたは日本語の小説作家です。",
      `以下の条件で、約${totalChars}文字（${segmentChars}文字×${chunkCount}ブロック）の本文を書いてください。`,
      "本文は連続した1本の小説として出力し、途中で箇条書きや見出しを出さないでください。",
      `各ブロックはおおむね ${Math.round(segmentChars * 0.85)}〜${Math.round(segmentChars * 1.15)} 文字に収めてください。`,
      "各ブロックの担当範囲を意識して、前後のつながりが自然になるように構成してください。",
      r18Note,
      "",
      "【ブロックごとの執筆範囲】",
      ...scopeLines,
      "",
      "【共通条件】",
      `- タイトルのイメージ: ${titleHintText}`,
      `- ジャンル: ${genreText}`,
      `- 雰囲気: ${toneText}`,
      `- 登場人物・設定: ${charactersText}`,
      "",
      "出力は JSON の body に本文のみを書いてください（タイトルは変更しない）。",
    ].join("\n");
  };

  const buildChunkBlockPrompt = (
    params,
    blockInstruction,
    blockIndex,
    totalBlocks,
    previousText,
    previousBlocks = [],
    segmentChars = SEGMENT_TARGET_CHARS
  ) => {
    const r18Note = params.isR18
      ? "成人向けの内容を許可します。性的描写を含めても構いません。"
      : "一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。";
    const titleHintText = params.titleHint || "指定なし";
    const genreText = params.genre || "指定なし";
    const toneText = params.tone || "指定なし";
    const charactersText = params.characters || "指定なし";
    const start = blockIndex * segmentChars + 1;
    const end = (blockIndex + 1) * segmentChars;
    const previousBlockContext = (Array.isArray(previousBlocks) ? previousBlocks : [])
      .map((block) => {
        const body = String(block?.body || "").trim();
        if (!body) return "";
        const instruction = String(block?.instruction || "").trim() || "（特記事項なし）";
        const index = Number(block?.index || 0);
        const label = index > 0 ? `第${index}ブロック` : "以前のブロック";
        return [
          `【${label}】`,
          `- このブロックの指示: ${instruction}`,
          "- 生成済み本文:",
          body,
        ].join("\n");
      })
      .filter(Boolean)
      .join("\n\n");
    const fallbackPreviousText = String(previousText || "").trim();
    const previousContext = previousBlockContext || fallbackPreviousText;
    const hasPrevious = Boolean(previousContext);

    return [
      "あなたは日本語の小説作家です。",
      hasPrevious
        ? `以下は分割生成の第${blockIndex + 1}/${totalBlocks}ブロックです。前ブロックの続きとして本文のみを書いてください。`
        : `以下は分割生成の第1/${totalBlocks}ブロックです。本文の導入から書いてください。`,
      `今回の出力は約${segmentChars}文字（目安 ${start}〜${end} 文字の範囲）にしてください。`,
      "すでに書かれた内容の要約や繰り返しは避け、物語を前進させてください。",
      r18Note,
      "",
      hasPrevious ? "【これ以前のブロック情報】" : "",
      hasPrevious ? previousContext : "",
      hasPrevious ? "" : "",
      "【このブロックで書く内容】",
      String(blockInstruction || "").trim() || "前後と自然につながる展開にする。",
      "",
      "【共通条件】",
      `- タイトルのイメージ: ${titleHintText}`,
      `- ジャンル: ${genreText}`,
      `- 雰囲気: ${toneText}`,
      `- 登場人物・設定: ${charactersText}`,
      "",
      "出力は JSON の body に本文のみを書いてください（タイトルは変更しない）。",
    ]
      .filter((line) => line !== "")
      .join("\n");
  };

  const requestGenerateJob = async (endpoint, token, bodyPayload) => {
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
        body: JSON.stringify(bodyPayload),
      },
      20000
    );
    let detail = "";
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      detail = String(data?.detail || "").trim();
    }
    if (res.status === 401 && token) {
      const e = new Error(
        t({
          ja: "ログインの有効期限が切れています。再ログインしてください。",
          en: "Your session has expired. Please log in again.",
        })
      );
      e.code = "auth_expired";
      throw e;
    }
    if (res.status === 402) {
      const e = new Error(
        t({
          ja: "この機能は有料プラン専用です。マイページからプランをご確認ください。",
          en: "This feature is for paid plans only. Check your plan on My Page.",
        })
      );
      e.code = "premium";
      throw e;
    }
    if (res.status === 429) {
      const e = new Error(
        detail ||
          t({
            ja: "本日の AI 小説生成の上限回数に達しました。明日またお試しください。",
            en: "You've reached today's AI generation limit. Please try again tomorrow.",
          })
      );
      e.code = "quota";
      throw e;
    }
    if (!res.ok) {
      const e = new Error(
        detail ||
          t(
            { ja: "生成に失敗しました (status={{status}})", en: "Generation failed (status={{status}})" },
            { status: res.status }
          )
      );
      e.code = "request_failed";
      throw e;
    }
    const data = await res.json().catch(() => ({}));
    const jobId = Number(data?.job_id);
    if (!Number.isFinite(jobId) || jobId <= 0) {
      const e = new Error(
        t({ ja: "生成ジョブの開始に失敗しました。", en: "Failed to start generation job." })
      );
      e.code = "job_start_failed";
      throw e;
    }
    return jobId;
  };

  const pollGenerateJobUntilDone = async (jobId, token) => {
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const started = Date.now();
    while (true) {
      if (Date.now() - started > CHUNK_BLOCK_TIMEOUT_MS) {
        const e = new Error(
          t({
            ja: "分割ブロック生成が5分でタイムアウトしました。次のブロックに進むか再試行してください。",
            en: "Chunk block generation timed out after 5 minutes. Retry or continue with available blocks.",
          })
        );
        e.code = "poll_timeout";
        throw e;
      }
      await sleep(800);
      const statusRes = await fetch(`/api/ai/jobs/${jobId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!statusRes.ok) {
        const data = await statusRes.json().catch(() => ({}));
        const e = new Error(
          data?.detail ||
            t(
              {
                ja: "生成ジョブの状態取得に失敗しました (status={{status}})",
                en: "Failed to get generation job status (status={{status}})",
              },
              { status: statusRes.status }
            )
        );
        e.code = "status_failed";
        throw e;
      }
      const statusData = await statusRes.json().catch(() => ({}));
      if (typeof statusData?.retry_attempts === "number") {
        setRetryAttempts(statusData.retry_attempts);
      }
      if (typeof statusData?.retry_max === "number") {
        setActiveRetryMax(statusData.retry_max);
      }
      if (statusData?.status === "succeeded") {
        return statusData?.response || {};
      }
      if (statusData?.status === "failed") {
        const e = new Error(
          statusData?.error || t({ ja: "生成に失敗しました。", en: "Generation failed." })
        );
        e.code = "job_failed";
        throw e;
      }
    }
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

  const buildRevisionPromptFromComments = (baseBody, params, comments, options = {}) => {
    const scope = options?.scope === "selection" ? "selection" : "full";
    const chunkIndex = Number(options?.chunkIndex || 0);
    const chunkTotal = Number(options?.chunkTotal || 0);
    const sourceChars = Number(options?.sourceChars || 0);
    const isChunkedRevision = chunkTotal > 1 && chunkIndex >= 1;
    const level = Math.min(100, Math.max(0, Number(polishIntensity) || 0));
    const strengthText =
      level <= 20
        ? "極めて軽い添削（誤字・表記ゆれ中心）"
        : level <= 40
        ? "軽めの添削（重複や違和感を軽く調整）"
        : level <= 60
        ? "標準の添削（読みやすさを中心に整える）"
        : level <= 80
        ? "強めのリライト（文の組み替えや表現の刷新も可）"
        : "非常に強いリライト（構成の再整理まで許可）";
    const r18Note = params.isR18
      ? "成人向けの内容を許可します。性的描写を含めても構いません。"
      : "一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。";
    const titleHintText = params.titleHint || "指定なし";
    const genreText = params.genre || "指定なし";
    const toneText = params.tone || "指定なし";
    const charactersText = params.characters || "指定なし";
    const userComments = (comments || [])
      .filter((item) => item && item.role === "user" && String(item.content || "").trim())
      .map((item, idx) => `${idx + 1}. ${String(item.content || "").trim()}`);
    return [
      "あなたは日本語の小説編集者です。",
      "以下の本文を、ユーザーコメント（修正指示）を反映して必要最小限だけ改稿してください。",
      "コメントで明示された箇所・意味的に直接関係する箇所だけを修正対象にしてください。",
      "コメントに関係しない文、場面、台詞、描写、段落構成は変更しないでください。",
      "既存の世界観・時系列・人物像は維持し、指示された範囲で自然に修正してください。",
      "矛盾する指示がある場合は、後から書かれた指示を優先してください。",
      "コメント対応に必要な場合を除き、単なる言い換え・添削・美化・要約はしないでください。",
      scope === "selection"
        ? "適用範囲は選択範囲内です。選択範囲内でも、コメントに関係しない箇所は元のまま残してください。"
        : "適用範囲は生成した文章全体ですが、全文を書き換えるのではなく、コメントに該当する箇所だけを修正してください。",
      isChunkedRevision
        ? `今回は長文を分割したうち ${chunkTotal} 分割中 ${chunkIndex} 件目の本文です。この本文内でもコメントに関係する箇所だけを修正し、他は元のまま維持してください。`
        : "",
      sourceChars > 0
        ? `分量を極端に削らないでください。出力文字数は入力本文（約${sourceChars}文字）の 85%〜120% を目安にしてください。`
        : "分量を極端に削らないでください。要点だけに短縮せず、本文の情報量を維持してください。",
      "省略記号（…）などで内容を飛ばさず、本文を最後まで改稿してください。",
      `添削の強さ: ${strengthText}`,
      level >= 70
        ? "必要なら対象箇所内で文の並び替えや言い回しの大きな変更も行ってください。対象外は変更しないでください。"
        : "対象箇所以外の大幅な改変や新規の内容追加は避けてください。",
      r18Note,
      "",
      "【本文】",
      baseBody,
      "",
      "【ユーザーコメント（修正指示）】",
      userComments.length ? userComments.join("\n") : "（指示なし）",
      "",
      "【参考情報】",
      `- 編集方針・指示: ${titleHintText}`,
      `- ジャンル: ${genreText}`,
      `- 雰囲気: ${toneText}`,
      `- 登場人物・設定: ${charactersText}`,
      "",
      "出力は JSON の body に改稿後の本文のみを書いてください（タイトルは変更しない）。",
    ].join("\n");
  };

  const handleReviseByComment = async (scope = "full") => {
    if (polishing || loading || continuing || revisingByComment) return;
    const latestComment = (revisionCommentInput || "").trim();
    if (!latestComment) {
      setError(
        t({
          ja: "修正コメントを入力してください。",
          en: "Please enter a revision comment.",
        })
      );
      return;
    }
    const generatedFullBody = getCombinedBody();
    if (!generatedFullBody) {
      setError(
        t({
          ja: "本文がありません。先にAIで本文を生成してください。",
          en: "No text available. Generate content before revising.",
        })
      );
      return;
    }
    const normalizedScope = scope === "selection" ? "selection" : "full";
    const selectionContext =
      normalizedScope === "selection"
        ? lastSelectionContextRef.current || getSelectionContext()
        : null;
    if (normalizedScope === "selection" && !selectionContext) {
      setError(
        t({
          ja: "部分修正するには、本文から修正したい範囲を選択してください。",
          en: "To partially revise, select the text range you want to edit.",
        })
      );
      return;
    }
    const token = getAuthToken();
    const params = {
      ...(lastGenerateParams || {}),
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
    const nextComments = [
      ...revisionComments,
      { role: "user", content: latestComment, at: new Date().toISOString() },
    ];
    setRevisionComments(nextComments);
    setRevisionCommentInput("");
    setRevisingByComment(true);
    setLastRevisionTargetInfo(null);
    setRetryAttempts(0);
    setActiveRetryMax(Boolean(params.retryMode) ? Number(params.retryMax || 0) : 0);
    setError("");
    setQuotaError("");
    setPremiumError("");
    setAutoFillError("");

    try {
      const userCommentTexts = nextComments
        .filter((item) => item && item.role === "user" && String(item.content || "").trim())
        .map((item) => String(item.content || "").trim());
      const baseContext =
        normalizedScope === "selection"
          ? selectionContext
          : {
              fullText: generatedFullBody,
              start: 0,
              end: generatedFullBody.length,
              selectedText: generatedFullBody,
            };
      let targetContext = baseContext;
      let usedWeaviateTargeting = false;
      if (userCommentTexts.length > 0) {
        try {
          const targetRes = await fetch("/api/ai/novels/revision-target", {
            method: "POST",
            headers: token
              ? {
                  "Content-Type": "application/json",
                  Authorization: `Bearer ${token}`,
                }
              : { "Content-Type": "application/json" },
            body: JSON.stringify({
              body: baseContext.selectedText,
              comments: userCommentTexts,
              scope: normalizedScope,
              r18: Boolean(params.isR18),
            }),
          });
          if (targetRes.ok) {
            const targetData = await targetRes.json().catch(() => ({}));
            const candidateCount = Number(targetData?.candidate_count);
            setLastRevisionTargetInfo({
              usedWeaviate: Boolean(targetData?.used_weaviate),
              attemptedWeaviate: Boolean(targetData?.attempted_weaviate),
              fallbackReason:
                typeof targetData?.fallback_reason === "string" ? targetData.fallback_reason : "",
              candidateCount: Number.isFinite(candidateCount) ? candidateCount : 0,
            });
            const relStart = Number(targetData?.start);
            const relEnd = Number(targetData?.end);
            const targetText = String(targetData?.target_text || "");
            if (
              Number.isFinite(relStart)
              && Number.isFinite(relEnd)
              && relStart >= 0
              && relEnd > relStart
              && relEnd <= baseContext.selectedText.length
              && targetText
            ) {
              targetContext = {
                fullText: baseContext.fullText,
                start: baseContext.start + relStart,
                end: baseContext.start + relEnd,
                selectedText: targetText,
              };
              usedWeaviateTargeting = Boolean(targetData?.used_weaviate);
            }
          } else {
            setLastRevisionTargetInfo({
              usedWeaviate: false,
              attemptedWeaviate: true,
              fallbackReason: "target_api_http_error",
              candidateCount: 0,
            });
          }
        } catch (targetErr) {
          console.warn("failed to locate revision target", targetErr);
          setLastRevisionTargetInfo({
            usedWeaviate: false,
            attemptedWeaviate: true,
            fallbackReason: "target_api_fetch_error",
            candidateCount: 0,
          });
        }
      }

      const targetBody = targetContext.selectedText;
      const throwHandled = () => {
        const e = new Error("handled");
        e.handled = true;
        throw e;
      };
      const runRevisionJob = async (bodyText, promptOptions = {}) => {
        const disableServerRetry = Boolean(promptOptions?.disableServerRetry);
        const prompt = buildRevisionPromptFromComments(bodyText, params, nextComments, {
          ...promptOptions,
          sourceChars: bodyText.length,
        });
        const res = await fetch("/api/ai/novels/generate_job", {
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
            length: String(bodyText.length || 0),
            model: params.model || DEFAULT_AI_NOVEL_MODEL,
            r18: params.isR18,
            retry_mode: disableServerRetry ? false : Boolean(params.retryMode),
            retry_max: disableServerRetry ? 0 : Number(params.retryMax || 0),
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
          throwHandled();
        }

        if (res.status === 402) {
          setPremiumError(
            t({
              ja: "この機能は有料プラン専用です。マイページからプランをご確認ください。",
              en: "This feature is for paid plans only. Check your plan on My Page.",
            })
          );
          throwHandled();
        }

        if (res.status === 429) {
          setQuotaError(
            errorDetail ||
              t({
                ja: "本日の AI 小説生成の上限回数に達しました。明日またお試しください。",
                en: "You've reached today's AI generation limit. Please try again tomorrow.",
              })
          );
          throwHandled();
        }

        if (!res.ok) {
          throw new Error(
            errorDetail ||
              t(
                { ja: "修正に失敗しました (status={{status}})", en: "Revision failed (status={{status}})" },
                { status: res.status }
              )
          );
        }
        const jobData = await res.json().catch(() => ({}));
        const jobId = Number(jobData?.job_id);
        if (!Number.isFinite(jobId) || jobId <= 0) {
          throw new Error(
            t({ ja: "修正ジョブの開始に失敗しました。", en: "Failed to start revision job." })
          );
        }

        const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
        const startedAt = Date.now();
        let finalPayload = null;
        while (true) {
          if (Date.now() - startedAt > 3 * 60 * 1000) {
            throw new Error(
              t({
                ja: "修正処理がタイムアウトしました。時間をおいて再度お試しください。",
                en: "Revision timed out. Please try again later.",
              })
            );
          }
          await sleep(700);
          const statusRes = await fetch(`/api/ai/jobs/${jobId}`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
          if (!statusRes.ok) {
            const statusErr = await statusRes.json().catch(() => ({}));
            throw new Error(
              statusErr?.detail ||
                t(
                  {
                    ja: "修正ジョブの状態取得に失敗しました (status={{status}})",
                    en: "Failed to get revision job status (status={{status}})",
                  },
                  { status: statusRes.status }
                )
            );
          }
          const statusData = await statusRes.json().catch(() => ({}));
          if (typeof statusData?.retry_attempts === "number") {
            setRetryAttempts(statusData.retry_attempts);
          }
          if (typeof statusData?.retry_max === "number") {
            setActiveRetryMax(statusData.retry_max);
          }
          if (statusData?.status === "succeeded") {
            finalPayload = statusData?.response || {};
            break;
          }
          if (statusData?.status === "failed") {
            const attempts = Number(statusData?.retry_attempts || 0);
            const max = Number(statusData?.retry_max || 0);
            const retrySummary = max > 0
              ? t({ ja: "再試行: {{attempts}}/{{max}}", en: "Retries: {{attempts}}/{{max}}" }, { attempts, max })
              : "";
            throw new Error(
              `${statusData?.error || t({ ja: "修正に失敗しました。", en: "Revision failed." })}${
                retrySummary ? ` (${retrySummary})` : ""
              }`
            );
          }
        }

        const data = normalizeAINovelResponse(finalPayload || {});
        const revisedChunk = String(data?.body || "");
        if (typeof data?.retry_attempts === "number") {
          setRetryAttempts(data.retry_attempts);
        }
        if (typeof data?.retry_max === "number") {
          setActiveRetryMax(data.retry_max);
        }
        if (typeof data?.guest_remaining === "number") setGuestRemaining(data.guest_remaining);
        if (typeof data?.user_remaining === "number") setUserRemaining(data.user_remaining);
        return revisedChunk;
      };

      const chunks = splitTextForRevision(targetBody, REVISION_CHUNK_MAX_CHARS);
      const useGlobalRetryAcrossChunks =
        normalizedScope === "full"
        && chunks.length > 1
        && Boolean(params.retryMode)
        && Number(params.retryMax || 0) > 0;
      const globalRetryMax = useGlobalRetryAcrossChunks ? Number(params.retryMax || 0) : 0;
      let globalRetryAttempts = 0;
      const revisedParts = [];
      for (let chunkIndex = 0; chunkIndex < chunks.length; chunkIndex += 1) {
        const chunk = chunks[chunkIndex];
        let revisedChunk = "";
        let outputRetryCount = 0;
        while (true) {
          try {
            revisedChunk = await runRevisionJob(chunk.text, {
              scope: normalizedScope,
              chunkIndex: chunks.length > 1 ? chunkIndex + 1 : 0,
              chunkTotal: chunks.length,
              disableServerRetry: useGlobalRetryAcrossChunks,
            });
            const outputIssue = getCommentRevisionOutputIssue(revisedChunk);
            if (!outputIssue) {
              break;
            }
            if (outputRetryCount < COMMENT_REVISION_OUTPUT_RETRY_MAX) {
              outputRetryCount += 1;
              continue;
            }
            throw new Error(
              t({
                ja: "コメント修正の出力が不正（JSON形式エラーまたは空）だったため、再試行上限に達しました。",
                en: "Comment revision output was invalid (JSON error or empty) and reached retry limit.",
              })
            );
            
          } catch (chunkErr) {
            if (chunkErr?.handled) throw chunkErr;
            if (!useGlobalRetryAcrossChunks || globalRetryAttempts >= globalRetryMax) {
              throw chunkErr;
            }
            globalRetryAttempts += 1;
            setRetryAttempts(globalRetryAttempts);
            setActiveRetryMax(globalRetryMax);
          }
        }
        revisedParts.push(revisedChunk);
      }
      const revisedBody = revisedParts.join("");

      const nextFullBody =
        targetContext && typeof targetContext.start === "number" && typeof targetContext.end === "number"
          ? applyPolishReplacement(
              targetContext.fullText,
              targetContext.start,
              targetContext.end,
              revisedBody
            )
          : revisedBody;
      setResult((prev) => ({
        ...(prev || {}),
        body: nextFullBody,
      }));
      setContinuationBody("");
      setCommentRevisionUndoStack((prev) => [...prev, generatedFullBody]);
      setCommentRevisionDiffSegments(buildLineDiffSegments(generatedFullBody, nextFullBody));
      setCommentRevisionHasActiveDiff(true);
      if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted") {
        try {
          new Notification(
            t({ ja: "コメント修正が完了しました", en: "Comment revision is ready" })
          );
        } catch {
          // ignore
        }
      }
      notifyAndroidAiResult({
        title: t({ ja: "コメント修正が完了しました", en: "Comment revision is ready" }),
        body: revisedBody.slice(0, 120),
        url: "/ai-novel",
      });
      setRevisionComments((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            normalizedScope === "selection"
              ? t({
                  ja: usedWeaviateTargeting
                    ? "コメント内容を反映して、選択範囲内の関連箇所を更新しました。"
                    : "コメント内容を反映して、選択範囲のみ更新しました。",
                  en: usedWeaviateTargeting
                    ? "Applied your comment and updated the related part in the selected range."
                    : "Applied your comment and updated only the selected range.",
                })
              : t({
                  ja: usedWeaviateTargeting
                    ? "コメント内容を反映して、生成した文章全体から関連箇所を検索して更新しました。"
                    : "コメント内容を反映して生成した文章全体を更新しました。",
                  en: usedWeaviateTargeting
                    ? "Applied your comment and updated the searched related part in the generated text."
                    : "Applied your comment and updated the entire generated text.",
                }),
          at: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      if (err?.handled) return;
      console.error(err);
      setError(
        err.message ||
          t({
            ja: "コメント反映中にエラーが発生しました。",
            en: "An error occurred while applying your comment.",
          })
      );
    } finally {
      setRevisingByComment(false);
    }
  };

  const handleUndoCommentRevision = () => {
    if (!commentRevisionUndoStack.length) return;
    const restoreBody = commentRevisionUndoStack[commentRevisionUndoStack.length - 1];
    setResult((prev) => ({
      ...(prev || {}),
      body: restoreBody,
    }));
    setContinuationBody("");
    setCommentRevisionUndoStack((prev) => prev.slice(0, -1));
    setCommentRevisionDiffSegments([]);
    setCommentRevisionHasActiveDiff(false);
    setRevisionComments((prev) => [
      ...prev,
      {
        role: "assistant",
        content: t({
          ja: "直前のコメント修正を元に戻しました。",
          en: "Reverted the latest comment-based revision.",
        }),
        at: new Date().toISOString(),
      },
    ]);
  };

  const handleStartNovelAddonCheckout = async () => {
    const token = getAuthToken();
    if (!token) {
      setError(
        t({
          ja: "ログインが必要です。ログイン画面へ移動します。",
          en: "Login required. Redirecting to the login page.",
        })
      );
      setTimeout(() => navigate("/login"), 800);
      return;
    }

    try {
      setAddonCheckoutLoading(true);
      setError("");
      setPremiumError("");
      const res = await fetchWithTimeout(
        "/api/ai/novels/addon/checkout",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ units: 1 }),
        },
        15000
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          String(
            data?.detail ||
              t({ ja: "追加課金Checkoutの作成に失敗しました。", en: "Failed to start add-on checkout." })
          )
        );
      }
      const url = String(data?.checkout_url || "").trim();
      if (!url) {
        throw new Error(
          t({ ja: "決済URLが取得できませんでした。", en: "Could not get checkout URL." })
        );
      }
      window.location.href = url;
    } catch (e) {
      setError(
        e?.message ||
          t({ ja: "追加課金Checkoutの開始中にエラーが発生しました。", en: "Failed to start add-on checkout." })
      );
    } finally {
      setAddonCheckoutLoading(false);
    }
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
    stopChunkedProgress(false);
    setError("");
    setQuotaError("");
    setPremiumError("");
    setAutoFillError("");
    const baseBodyForEdit = isEditMode
      ? (result?.body || editSourceBody || "").trim()
      : "";
    setResult(null);
    setLastGenerateParams(null);
    setLastPolishScope("full");
    setContinuationBody("");
    setRevisionCommentInput("");
    setRevisionChatScope("full");
    setRevisionComments([]);
    setCommentRevisionUndoStack([]);
    setCommentRevisionDiffSegments([]);
    setCommentRevisionHasActiveDiff(false);
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
      stopChunkedProgress(false);
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
      stopChunkedProgress(false);
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
      chunkedGenerationEnabled,
      chunkedGenerationCount,
      chunkedGenerationPlans,
    };
    // ★ ここで「通常の新規生成」と「エピソード続き生成」を切り替える
    const endpoint = episodeId
      ? `/api/ai/episodes/${episodeId}/continue_job`
      : "/api/ai/novels/generate_job";
    const activeChunkCount = clampSegmentCount(chunkedGenerationCount);
    const activeChunkPlans = (chunkedGenerationPlans || []).slice(0, activeChunkCount);
    const useChunkedGeneration =
      !episodeId
      && !isEditMode
      && canUseChunkedGeneration
      && Boolean(chunkedGenerationEnabled)
      && activeChunkCount >= 1;
    chunkedGenerateRetryRef.current = {
      enabled: useChunkedGeneration,
      attempts: 0,
      max: useChunkedGeneration ? Math.max(1, Number(retryMode ? retryMax : 2)) : 0,
      endpoint,
      requestBody: null,
    };
    const prompt = isEditMode && baseBodyForEdit
      ? buildEditPrompt(baseBodyForEdit, params)
      : useChunkedGeneration
      ? buildSegmentedNovelPrompt(params, activeChunkPlans, SEGMENT_TARGET_CHARS)
      : null;
    const requestBody = {
      title_hint: titleHint || null,
      genre: genre || null,
      characters: characters || null,
      tone: tone || null,
      length: useChunkedGeneration ? String(activeChunkCount * SEGMENT_TARGET_CHARS) : (length || "medium"),
      model: model || DEFAULT_AI_NOVEL_MODEL,
      r18: isR18,
      prompt,
      retry_mode: retryMode,
      retry_max: retryMax,
    };
    if (useChunkedGeneration) {
      chunkedGenerateRetryRef.current = {
        ...chunkedGenerateRetryRef.current,
        requestBody,
      };
      let combinedChunkText = "";
      const generatedChunkBlocks = [];
      let finalTitle = "";
      try {
        startChunkedProgress(activeChunkCount);
        setRetryAttempts(0);
        setActiveRetryMax(null);
        for (let blockIdx = 0; blockIdx < activeChunkCount; blockIdx += 1) {
          const blockInstruction = activeChunkPlans[blockIdx]?.instruction || "";
          setChunkedProgressBlock(blockIdx + 1);
          setChunkedCompletedBlocks(blockIdx);
          while (true) {
            const chunkPrompt = buildChunkBlockPrompt(
              params,
              blockInstruction,
              blockIdx,
              activeChunkCount,
              combinedChunkText,
              generatedChunkBlocks,
              SEGMENT_TARGET_CHARS
            );
            const chunkBodyPayload = {
              ...requestBody,
              prompt: chunkPrompt,
              length: String(SEGMENT_TARGET_CHARS),
            };
            const blockJobId = await requestGenerateJob(endpoint, token, chunkBodyPayload);
            const blockPayload = await pollGenerateJobUntilDone(blockJobId, token);
            const outputIssue = getGenerateOutputIssue(blockPayload || {});
            if (outputIssue) {
              setError(
                t(
                  {
                    ja: "第{{block}}ブロックの出力が不正（{{issue}}）のため再生成しています...",
                    en: "Block {{block}} output was invalid ({{issue}}). Retrying...",
                  },
                  { block: blockIdx + 1, issue: String(outputIssue || "unknown") }
                )
              );
              continue;
            }
            const normalizedBlock = normalizeAINovelResponse(blockPayload || {});
            const nextChunkBody = String(normalizedBlock?.body || "").trim();
            if (!nextChunkBody) {
              setError(
                t(
                  {
                    ja: "第{{block}}ブロックの出力が空だったため再生成しています...",
                    en: "Block {{block}} output was empty. Retrying...",
                  },
                  { block: blockIdx + 1 }
                )
              );
              continue;
            }
            if (!finalTitle) {
              finalTitle = String(normalizedBlock?.generated_title || "").trim();
            }
            combinedChunkText = combinedChunkText
              ? `${combinedChunkText}\n\n${nextChunkBody}`
              : nextChunkBody;
            generatedChunkBlocks.push({
              index: blockIdx + 1,
              instruction: blockInstruction,
              body: nextChunkBody,
            });
            setResult({
              generated_title: finalTitle || titleHint || t({ ja: "生成された小説", en: "Generated Novel" }),
              body: combinedChunkText,
            });
            if (typeof normalizedBlock?.guest_remaining === "number") {
              setGuestRemaining(normalizedBlock.guest_remaining);
            }
            if (typeof normalizedBlock?.user_remaining === "number") {
              setUserRemaining(normalizedBlock.user_remaining);
            }
            setChunkedCompletedBlocks(blockIdx + 1);
            setChunkedProgressPercent(Math.min(95, Math.round(((blockIdx + 1) / activeChunkCount) * 100)));
            break;
          }
        }
        stopChunkedProgress(true);
        setLastGenerateParams(params);
        setRetryAttempts(0);
        setActiveRetryMax(null);
        setError("");
        setLoading(false);
        resetChunkedGenerateRetryContext();
      } catch (err) {
        console.error(err);
        setLoading(false);
        setChunkedProgressActive(false);
        resetChunkedGenerateRetryContext();
        if (combinedChunkText.trim()) {
          setResult((prev) => ({
            ...(prev || {}),
            generated_title:
              (prev?.generated_title || finalTitle || titleHint || t({ ja: "生成された小説", en: "Generated Novel" })),
            body: combinedChunkText,
          }));
          const baseMessage =
            err?.message ||
            t({ ja: "分割生成中にエラーが発生しました。", en: "An error occurred during chunked generation." });
          setError(
            t(
              {
                ja: "途中まで生成した本文を表示しています。理由: {{reason}}",
                en: "Showing partially generated text. Reason: {{reason}}",
              },
              { reason: baseMessage }
            )
          );
        } else if (err?.code === "premium") {
          setPremiumError(err.message);
        } else if (err?.code === "quota") {
          setQuotaError(err.message);
        } else if (err?.code === "auth_expired") {
          setError(err.message);
          setTimeout(() => navigate("/login"), 800);
        } else {
          setError(
            err?.message || t({ ja: "生成中にエラーが発生しました。", en: "An error occurred during generation." })
          );
        }
      }
      return;
    }

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
          body: JSON.stringify(requestBody),
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
        resetChunkedGenerateRetryContext();
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
        resetChunkedGenerateRetryContext();
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
        resetChunkedGenerateRetryContext();
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
      if (useChunkedGeneration) {
        startChunkedProgress(activeChunkCount);
      } else {
        stopChunkedProgress(false);
      }
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
      stopChunkedProgress(false);
      resetChunkedGenerateRetryContext();
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
            model: params.model || DEFAULT_AI_NOVEL_MODEL,
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

  const handlePolishText = async (overrideContext = null, options = {}) => {
    const scope = options?.scope === "selection" ? "selection" : "full";
    const safeOverride =
      overrideContext && typeof overrideContext === "object" && "selectedText" in overrideContext
        ? overrideContext
        : null;
    const selectionContext =
      scope === "selection"
        ? safeOverride || lastSelectionContextRef.current || getSelectionContext()
        : null;
    const combinedBody = combinedBodyRef.current || getCombinedBody();
    if (!combinedBody) return;
    if (scope === "selection" && !selectionContext) {
      setError(
        t({
          ja: "部分修正するには、本文から修正したい範囲を選択してください。",
          en: "To partially revise, select the text range you want to edit.",
        })
      );
      return;
    }
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
      setLastPolishScope(scope);
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
          model: params.model || DEFAULT_AI_NOVEL_MODEL,
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

  const handleUpdateEditedEpisode = async () => {
    if (!result?.body) return;
    if (!editEpisodeId) {
      setError(
        t({
          ja: "更新対象のエピソードIDが取得できませんでした。",
          en: "Could not get the target episode ID for update.",
        })
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
      setError(
        t({
          ja: "更新にはログインが必要です。ログイン画面へ移動します。",
          en: "Login required to update. Redirecting to the login page.",
        })
      );
      setTimeout(() => navigate("/login"), 200);
      setPosting(false);
      return;
    }

    try {
      const payload = {
        title: (result.generated_title || "").trim() || t({ ja: "タイトル未設定", en: "Untitled" }),
        body: combinedBody,
      };
      const res = await fetch(`/api/episodes/${editEpisodeId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 403) {
        throw new Error(
          t({
            ja: "このエピソードを更新する権限がありません。",
            en: "You don't have permission to update this episode.",
          })
        );
      }
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t(
              { ja: "エピソード更新に失敗しました (status={{status}})", en: "Failed to update episode (status={{status}})" },
              { status: res.status }
            )
        );
      }
      navigate(`/episodes/${editEpisodeId}`);
    } catch (err) {
      console.error(err);
      setError(
        err.message || t({ ja: "更新中にエラーが発生しました。", en: "An error occurred while updating." })
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
            <Link to="/premium" className="btn btn-border">
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
          <div>
            {t(
              { ja: "ユーザーの AI生成 残り回数: {{count}}", en: "User AI generations left: {{count}}" },
              { count: userRemaining }
            )}
          </div>
          <div style={{ marginTop: "0.25rem", color: "var(--muted-text)" }}>
            {t(
              { ja: "予備回数（追加課金分）: {{count}}", en: "Backup generations (paid add-on): {{count}}" },
              { count: userPaidRemaining }
            )}
          </div>
          {userRemaining <= 0 && (
            <div style={{ marginTop: "0.5rem" }}>
              <button
                type="button"
                className="btn btn-border"
                onClick={handleStartNovelAddonCheckout}
                disabled={addonCheckoutLoading}
              >
                {addonCheckoutLoading
                  ? t({ ja: "Checkout準備中...", en: "Preparing checkout..." })
                  : t(
                      {
                        ja: "{{price}}円で予備{{count}}回を追加",
                        en: "Add {{count}} backup generations for ¥{{price}}",
                      },
                      { price: Number(addonUnitPriceYen || 0), count: Number(addonUnitGenerations || 0) }
                    )}
              </button>
            </div>
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
            disabled={isLengthOverriddenByChunkedGeneration}
            style={{ width: "100%", padding: "0.5rem" }}
          >
            <option value="short">{t({ ja: "短め（800〜1200文字程度）", en: "Short (800–1200 chars)" })}</option>
            <option value="medium">{t({ ja: "ふつう（2000〜3000文字程度）", en: "Medium (2000–3000 chars)" })}</option>
            <option value="long">{t({ ja: "長め（4000〜6000文字程度）", en: "Long (4000–6000 chars)" })}</option>
            <option value="xlong">{t({ ja: "すごく長め（6000〜8000文字程度）", en: "Very long (6000–8000 chars)" })}</option>
            <option value="xxlong">{t({ ja: "超長め（8000〜10000文字程度）", en: "Ultra long (8000–10000 chars)" })}</option>
          </select>
          {isLengthOverriddenByChunkedGeneration && (
            <div style={{ marginTop: "0.35rem", fontSize: "0.82rem", color: "var(--muted-text)" }}>
              {t({
                ja: "分割生成ON中はこの長さ指定は無効です。2000文字×ブロック数が優先されます。",
                en: "Length selection is ignored while chunked generation is ON. 2000 chars × block count is used.",
              })}
            </div>
          )}
        </div>

        {canUseChunkedGeneration && (
          <div
            style={{
              padding: "0.75rem",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              backgroundColor: "var(--ai-result-surface)",
            }}
          >
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontWeight: "bold" }}>
              <input
                type="checkbox"
                checked={chunkedGenerationEnabled}
                onChange={(e) => {
                  markUserInput();
                  setChunkedGenerationEnabled(e.target.checked);
                }}
              />
              {t({ ja: "2000文字単位で分割生成する", en: "Generate in 2000-char chunks" })}
            </label>
            <div style={{ marginTop: "0.45rem", fontSize: "0.85rem", color: "var(--muted-text)" }}>
              {t(
                {
                  ja: "目標文字数: 約{{per}}文字 × {{count}}ブロック = 約{{total}}文字",
                  en: "Target length: about {{per}} chars × {{count}} blocks = about {{total}} chars",
                },
                { per: SEGMENT_TARGET_CHARS, count: chunkedGenerationCount, total: targetTotalChars }
              )}
            </div>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center", marginTop: "0.5rem" }}>
              <label style={{ fontSize: "0.9rem", color: "var(--muted-text)" }}>
                {t({ ja: "ブロック数", en: "Block count" })}
              </label>
              <input
                type="number"
                min={SEGMENT_COUNT_MIN}
                max={SEGMENT_COUNT_MAX}
                value={chunkedGenerationCount}
                onChange={(e) => {
                  markUserInput();
                  setChunkPlanCount(e.target.value);
                }}
                disabled={!chunkedGenerationEnabled}
                style={{ width: "110px", padding: "0.4rem" }}
              />
              <button
                type="button"
                className="btn btn-border"
                onClick={handleAddChunkPlan}
                disabled={!chunkedGenerationEnabled || chunkedGenerationCount >= SEGMENT_COUNT_MAX}
              >
                {t({ ja: "+ 次の2000文字を追加", en: "+ Add next 2000-char block" })}
              </button>
            </div>
            {chunkedGenerationEnabled && (
              <div style={{ marginTop: "0.7rem", display: "grid", gap: "0.6rem" }}>
                {chunkedGenerationPlans.slice(0, chunkedGenerationCount).map((item, idx) => {
                  const start = idx * SEGMENT_TARGET_CHARS + 1;
                  const end = (idx + 1) * SEGMENT_TARGET_CHARS;
                  const blockNumber = idx + 1;
                  const isBlockCompleted = chunkedCompletedBlocks >= blockNumber;
                  const isBlockCurrent = chunkedProgressActive && loading && blockNumber === chunkedProgressBlock;
                  const blockStatusLabel = isBlockCompleted
                    ? t({ ja: "生成済み", en: "Completed" })
                    : isBlockCurrent
                    ? t({ ja: "生成中", en: "Generating" })
                    : t({ ja: "未着手", en: "Pending" });
                  const blockStatusStyle = isBlockCompleted
                    ? { color: "#065f46", backgroundColor: "#dcfce7", border: "1px solid #86efac" }
                    : isBlockCurrent
                    ? { color: "#1e3a8a", backgroundColor: "#dbeafe", border: "1px solid #93c5fd" }
                    : { color: "#6b7280", backgroundColor: "#f3f4f6", border: "1px solid #d1d5db" };
                  return (
                    <div
                      key={item.id || `seg-${idx}`}
                      style={{
                        border: "1px solid var(--border)",
                        borderRadius: "6px",
                        padding: "0.55rem",
                        backgroundColor: "var(--ai-result-bg)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", flexWrap: "wrap" }}>
                        <div style={{ fontWeight: "bold", fontSize: "0.92rem" }}>
                          {t(
                            { ja: "第{{n}}ブロック（{{start}}〜{{end}}文字 目安）", en: "Block {{n}} (about {{start}}–{{end}} chars)" },
                            { n: idx + 1, start, end }
                          )}
                        </div>
                        <span
                          style={{
                            fontSize: "0.78rem",
                            borderRadius: "999px",
                            padding: "0.12rem 0.5rem",
                            ...blockStatusStyle,
                          }}
                        >
                          {blockStatusLabel}
                        </span>
                        <button
                          type="button"
                          className="btn btn-border"
                          onClick={() => handleRemoveChunkPlan(idx)}
                          disabled={chunkedGenerationCount <= SEGMENT_COUNT_MIN}
                        >
                          {t({ ja: "このブロックを削除", en: "Remove block" })}
                        </button>
                      </div>
                      <textarea
                        value={item.instruction || ""}
                        onChange={(e) => handleChangeChunkPlanInstruction(idx, e.target.value)}
                        rows={2}
                        placeholder={t({
                          ja: "この2000文字で書きたい内容（例: 導入、主人公の葛藤を描く、伏線を置く）",
                          en: "What to write in this 2000-char block (e.g., opening, conflict, foreshadowing)",
                        })}
                        style={{
                          width: "100%",
                          marginTop: "0.45rem",
                          padding: "0.5rem",
                          borderRadius: "4px",
                          border: "1px solid var(--border)",
                          resize: "vertical",
                        }}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

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
            <option value="gpt-5.2">{t({ ja: "GPT-5.2（最高品質）", en: "GPT-5.2 (highest quality)" })}</option>
            <option value="gpt-5">{t({ ja: "GPT-5（高品質）", en: "GPT-5 (high quality)" })}</option>
            <option value="gpt-5-mini">{t({ ja: "GPT-5 Mini（推奨・高速）", en: "GPT-5 Mini (recommended, fast)" })}</option>
            <option value="gpt-4.1-mini">{t({ ja: "GPT-4.1 Mini（高速・低コスト）", en: "GPT-4.1 Mini (fast, low cost)" })}</option>
            <option value="gpt-4.1">{t({ ja: "GPT-4.1（高品質）", en: "GPT-4.1 (high quality)" })}</option>
            <option value="gpt-4.1-preview">{t({ ja: "GPT-4.1 Preview（長文向け）", en: "GPT-4.1 Preview (long-form)" })}</option>
            <option value="gpt-4o-mini">GPT-4o Mini</option>
            <option value="gpt-4o">GPT-4o</option>
            <option value="openai/chatgpt-4o-latest">{t({ ja: "ChatGPT（OpenRouter / chatgpt-4o-latest）", en: "ChatGPT (OpenRouter / chatgpt-4o-latest)" })}</option>
            <option value="x-ai/grok-4">{t({ ja: "Grok 4（OpenRouter）", en: "Grok 4 (OpenRouter)" })}</option>
            <option value="x-ai/grok-4.1-fast">{t({ ja: "Grok 4.1 Fast（OpenRouter）", en: "Grok 4.1 Fast (OpenRouter)" })}</option>
            <option value="x-ai/grok-4-fast">{t({ ja: "Grok 4 Fast（OpenRouter）", en: "Grok 4 Fast (OpenRouter)" })}</option>
            <option value="x-ai/grok-3">{t({ ja: "Grok 3（OpenRouter）", en: "Grok 3 (OpenRouter)" })}</option>
            <option value="x-ai/grok-3-mini">{t({ ja: "Grok 3 Mini（OpenRouter）", en: "Grok 3 Mini (OpenRouter)" })}</option>
            <option value="x-ai/grok-code-fast-1">{t({ ja: "Grok Code Fast 1（OpenRouter）", en: "Grok Code Fast 1 (OpenRouter)" })}</option>
            <option value="z-ai/glm-4.6">{t({ ja: "GLM 4.6（OpenRouter / z-ai/glm-4.6）", en: "GLM 4.6 (OpenRouter / z-ai/glm-4.6)" })}</option>
            <option value="google/gemini-3-pro-preview">{t({ ja: "Gemini 3 Pro Preview（OpenRouter）", en: "Gemini 3 Pro Preview (OpenRouter)" })}</option>
            <option value="google/gemini-3-flash-preview">{t({ ja: "Gemini 3 Flash Preview（OpenRouter）", en: "Gemini 3 Flash Preview (OpenRouter)" })}</option>
            <option value="google/gemini-2.5-pro">{t({ ja: "Gemini 2.5 Pro（OpenRouter）", en: "Gemini 2.5 Pro (OpenRouter)" })}</option>
            <option value="google/gemini-2.5-flash">{t({ ja: "Gemini 2.5 Flash（OpenRouter）", en: "Gemini 2.5 Flash (OpenRouter)" })}</option>
            <option value="google/gemini-2.5-flash-lite">{t({ ja: "Gemini 2.5 Flash Lite（OpenRouter）", en: "Gemini 2.5 Flash Lite (OpenRouter)" })}</option>
            <option value="moonshotai/kimi-k2">{t({ ja: "Kimi（OpenRouter / kimi-k2）", en: "Kimi (OpenRouter / kimi-k2)" })}</option>
            <option value="moonshotai/kimi-k2-thinking">{t({ ja: "Kimi K2 Thinking（OpenRouter）", en: "Kimi K2 Thinking (OpenRouter)" })}</option>
            <option value="moonshotai/kimi-k2-thinking-turbo">{t({ ja: "Kimi K2 Thinking Turbo（OpenRouter）", en: "Kimi K2 Thinking Turbo (OpenRouter)" })}</option>
            <option value="deepseek/deepseek-chat">{t({ ja: "DeepSeek（OpenRouter / deepseek-chat）", en: "DeepSeek (OpenRouter / deepseek-chat)" })}</option>
            <option value="deepseek/deepseek-reasoner">{t({ ja: "DeepSeek Reasoner（OpenRouter）", en: "DeepSeek Reasoner (OpenRouter)" })}</option>
            <option value="deepseek:deepseek-chat">{t({ ja: "DeepSeek（公式 / deepseek-chat）", en: "DeepSeek (official / deepseek-chat)" })}</option>
            <option value="deepseek:deepseek-reasoner">{t({ ja: "DeepSeek（公式 / deepseek-reasoner）", en: "DeepSeek (official / deepseek-reasoner)" })}</option>
            <option value="google/gemini-2.0-flash-001">{t({ ja: "Gemini（OpenRouter / gemini-2.0-flash）", en: "Gemini (OpenRouter / gemini-2.0-flash)" })}</option>
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
        {chunkedProgressActive && loading && canUseChunkedGeneration && (
          <div
            style={{
              marginTop: "0.5rem",
              padding: "0.65rem 0.75rem",
              borderRadius: "6px",
              border: "1px solid var(--border)",
              backgroundColor: "var(--ai-result-surface)",
            }}
          >
            <div style={{ fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.35rem" }}>
              {t(
                { ja: "分割生成中: 第{{current}}/{{total}}ブロック", en: "Chunked generation: block {{current}}/{{total}}" },
                { current: chunkedProgressBlock, total: chunkedGenerationCount }
              )}
            </div>
            <div
              style={{
                width: "100%",
                height: "9px",
                borderRadius: "999px",
                backgroundColor: "var(--ai-result-bg)",
                overflow: "hidden",
                border: "1px solid var(--border)",
              }}
            >
              <div
                style={{
                  width: `${chunkedProgressPercent}%`,
                  height: "100%",
                  backgroundColor: "#3b82f6",
                  transition: "width 0.6s ease",
                }}
              />
            </div>
            <div style={{ marginTop: "0.3rem", fontSize: "0.82rem", color: "var(--muted-text)" }}>
              {t({ ja: "進捗目安", en: "Estimated progress" })}: {chunkedProgressPercent}%
            </div>
            <div style={{ marginTop: "0.2rem", fontSize: "0.82rem", color: "var(--muted-text)" }}>
              {t(
                { ja: "生成済みブロック: {{done}} / {{total}}", en: "Completed blocks: {{done}} / {{total}}" },
                { done: chunkedCompletedBlocks, total: chunkedGenerationCount }
              )}
            </div>
            {activeProgressInstruction && (
              <div style={{ marginTop: "0.2rem", fontSize: "0.82rem", color: "var(--muted-text)" }}>
                {t({ ja: "このブロックの指示", en: "Current block note" })}: {activeProgressInstruction}
              </div>
            )}
          </div>
        )}
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
          <div>{quotaError}</div>
          {hasAuthToken && typeof userRemaining === "number" && (
            <div style={{ marginTop: "0.6rem" }}>
              <button
                type="button"
                className="btn btn-border"
                onClick={handleStartNovelAddonCheckout}
                disabled={addonCheckoutLoading}
              >
                {addonCheckoutLoading
                  ? t({ ja: "Checkout準備中...", en: "Preparing checkout..." })
                  : t(
                      {
                        ja: "{{price}}円で予備{{count}}回を追加",
                        en: "Add {{count}} backup generations for ¥{{price}}",
                      },
                      { price: Number(addonUnitPriceYen || 0), count: Number(addonUnitGenerations || 0) }
                    )}
              </button>
            </div>
          )}
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
              <span
                style={{
                  fontSize: "0.8rem",
                  color: lastPolishScope === "selection" ? "#065f46" : "#6b7280",
                  backgroundColor: lastPolishScope === "selection" ? "#dcfce7" : "#f3f4f6",
                  border: lastPolishScope === "selection" ? "1px solid #86efac" : "1px solid #d1d5db",
                  boxShadow:
                    lastPolishScope === "selection" ? "0 0 0.55rem rgba(34,197,94,0.38)" : "none",
                  borderRadius: "999px",
                  padding: "0.2rem 0.55rem",
                }}
              >
                {t({ ja: "部分添削", en: "Partial polish" })}
              </span>
              <button
                type="button"
                onClick={() => handlePolishText(null, { scope: "selection" })}
                disabled={polishing || loading || continuing || !hasActiveSelection}
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
                  ? t({ ja: "部分添削中...", en: "Partially polishing..." })
                  : t({ ja: "選択範囲を部分添削", en: "Partially polish selection" })}
              </button>
              <span
                style={{
                  fontSize: "0.8rem",
                  color: lastPolishScope === "full" ? "#1e3a8a" : "#6b7280",
                  backgroundColor: lastPolishScope === "full" ? "#dbeafe" : "#f3f4f6",
                  border: lastPolishScope === "full" ? "1px solid #93c5fd" : "1px solid #d1d5db",
                  boxShadow:
                    lastPolishScope === "full" ? "0 0 0.55rem rgba(59,130,246,0.35)" : "none",
                  borderRadius: "999px",
                  padding: "0.2rem 0.55rem",
                }}
              >
                {t({ ja: "全体添削", en: "Full polish" })}
              </span>
              <button
                type="button"
                onClick={() => handlePolishText(null, { scope: "full" })}
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
                  ? t({ ja: "全体添削中...", en: "Polishing full text..." })
                  : t({ ja: "文章全体を添削", en: "Polish full text" })}
              </button>
              <button
                type="button"
                onClick={() => handlePolishText(lastPolishContext, { scope: lastPolishScope })}
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
          <div style={{ fontSize: "0.85rem", color: "var(--muted-text)", marginBottom: "0.45rem" }}>
            {hasActiveSelection
                  ? t({
                      ja: "現在: テキスト選択あり（部分添削が使えます）",
                      en: "Current: text selected (partial polish is available)",
                    })
                  : t({
                      ja: "現在: テキスト未選択（部分添削は無効、全体添削は利用可能）",
                      en: "Current: no text selected (partial polish disabled, full polish available)",
                    })}
            {` / ${t({ ja: "前回の添削モード", en: "Last polish mode" })}: ${
              lastPolishScope === "selection"
                ? t({ ja: "部分添削", en: "Partial polish" })
                : t({ ja: "全体添削", en: "Full polish" })
            }`}
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
            <div
              style={{
                padding: "0.75rem",
                borderRadius: "6px",
                border: "1px solid var(--border)",
                backgroundColor: "var(--ai-result-surface)",
              }}
            >
              <div style={{ fontWeight: "bold", marginBottom: "0.5rem" }}>
                {t({ ja: "修正チャット / コメント", en: "Revision chat / comments" })}
              </div>
              <div style={{ fontSize: "0.9rem", color: "var(--muted-text)", marginBottom: "0.5rem" }}>
                {t({
                  ja: "コメント指示を送ると、Weaviateで関連箇所を検索し、部分修正（選択範囲内）または全体修正（生成した文章全体内）として反映できます。",
                  en: "Send a comment to search related parts with Weaviate, then apply as partial revise (inside selection) or full revise (inside generated text).",
                })}
              </div>
              {lastRevisionTargetInfo && (
                <div style={{ fontSize: "0.82rem", color: "var(--muted-text)", marginBottom: "0.5rem" }}>
                  {lastRevisionTargetInfo.usedWeaviate
                    ? t(
                        {
                          ja: "対象抽出: Weaviate検索を使用（候補 {{count}} 件）",
                          en: "Targeting: used Weaviate search ({{count}} candidates)",
                        },
                        { count: String(lastRevisionTargetInfo.candidateCount || 0) }
                      )
                    : t(
                        {
                          ja: "対象抽出: フォールバック（理由: {{reason}}）",
                          en: "Targeting: fallback (reason: {{reason}})",
                        },
                        {
                          reason:
                            lastRevisionTargetInfo.fallbackReason ||
                            (lastRevisionTargetInfo.attemptedWeaviate
                              ? "unknown"
                              : "not_attempted"),
                        }
                      )}
                </div>
              )}
              <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginBottom: "0.5rem" }}>
                <span
                  style={{
                    fontSize: "0.8rem",
                    color: revisionChatScope === "selection" ? "#065f46" : "#6b7280",
                    backgroundColor: revisionChatScope === "selection" ? "#dcfce7" : "#f3f4f6",
                    border: revisionChatScope === "selection" ? "1px solid #86efac" : "1px solid #d1d5db",
                    boxShadow:
                      revisionChatScope === "selection" ? "0 0 0.5rem rgba(34,197,94,0.35)" : "none",
                    borderRadius: "999px",
                    padding: "0.15rem 0.55rem",
                  }}
                >
                  {t({ ja: "部分修正", en: "Partial revise" })}
                </span>
                <span
                  style={{
                    fontSize: "0.8rem",
                    color: revisionChatScope === "full" ? "#1e3a8a" : "#6b7280",
                    backgroundColor: revisionChatScope === "full" ? "#dbeafe" : "#f3f4f6",
                    border: revisionChatScope === "full" ? "1px solid #93c5fd" : "1px solid #d1d5db",
                    boxShadow:
                      revisionChatScope === "full" ? "0 0 0.5rem rgba(59,130,246,0.35)" : "none",
                    borderRadius: "999px",
                    padding: "0.15rem 0.55rem",
                  }}
                >
                  {t({ ja: "全体修正", en: "Full revise" })}
                </span>
                <span style={{ fontSize: "0.8rem", color: "var(--muted-text)" }}>
                  {hasActiveSelection
                    ? t({
                        ja: "現在: 選択あり（部分修正が使えます）",
                        en: "Current: selection exists (partial revise available)",
                      })
                    : t({
                        ja: "現在: 選択なし（全体修正: 生成した文章全体）",
                        en: "Current: no selection (full revise: entire generated text)",
                      })}
                  {` / ${t({ ja: "前回モード", en: "Last mode" })}: ${
                    revisionChatScope === "selection"
                      ? t({ ja: "部分修正", en: "Partial" })
                      : t({ ja: "全体修正", en: "Full" })
                  }`}
                </span>
              </div>
              <div
                style={{
                  maxHeight: "180px",
                  overflowY: "auto",
                  border: "1px solid var(--border)",
                  borderRadius: "6px",
                  backgroundColor: "var(--ai-result-bg)",
                  padding: "0.5rem",
                  marginBottom: "0.5rem",
                }}
              >
                {revisionComments.length === 0 ? (
                  <div style={{ color: "var(--muted-text)", fontSize: "0.85rem" }}>
                    {t({
                      ja: "まだコメントはありません。修正したい内容を送信してください。",
                      en: "No comments yet. Send instructions to revise the text.",
                    })}
                  </div>
                ) : (
                  revisionComments.map((item, idx) => (
                    <div
                      key={`${item.role}-${item.at}-${idx}`}
                      style={{
                        marginBottom: idx === revisionComments.length - 1 ? 0 : "0.4rem",
                        fontSize: "0.9rem",
                        lineHeight: 1.5,
                      }}
                    >
                      <strong>
                        {item.role === "assistant"
                          ? t({ ja: "AI", en: "AI" })
                          : t({ ja: "あなた", en: "You" })}
                        :
                      </strong>{" "}
                      <span style={{ whiteSpace: "pre-wrap" }}>{item.content}</span>
                    </div>
                  ))
                )}
              </div>
              <textarea
                value={revisionCommentInput}
                onChange={(e) => {
                  markUserInput();
                  setRevisionCommentInput(e.target.value);
                }}
                rows={3}
                placeholder={t({
                  ja: "例: 三人称で統一して、終盤の会話をもっと短くしてください",
                  en: "e.g. Keep third-person POV and shorten the dialogue near the end.",
                })}
                style={{
                  width: "100%",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  backgroundColor: "var(--ai-result-bg)",
                  padding: "0.6rem",
                  borderRadius: "6px",
                  border: "1px solid var(--border)",
                  lineHeight: 1.5,
                  resize: "vertical",
                  marginBottom: "0.5rem",
                }}
              />
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => {
                    setRevisionChatScope("selection");
                    handleReviseByComment("selection");
                  }}
                  disabled={revisingByComment || polishing || loading || continuing || !hasActiveSelection}
                >
                  {revisingByComment
                    ? t({ ja: "コメント反映中...", en: "Applying comment..." })
                    : t({ ja: "部分修正で送信", en: "Send as partial revise" })}
                </button>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => {
                    setRevisionChatScope("full");
                    handleReviseByComment("full");
                  }}
                  disabled={revisingByComment || polishing || loading || continuing}
                >
                  {revisingByComment
                    ? t({ ja: "コメント反映中...", en: "Applying comment..." })
                    : t({ ja: "全体修正で送信", en: "Send as full revise" })}
                </button>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => setRevisionComments([])}
                  disabled={revisingByComment || revisionComments.length === 0}
                >
                  {t({ ja: "履歴をクリア", en: "Clear history" })}
                </button>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={handleUndoCommentRevision}
                  disabled={revisingByComment || commentRevisionUndoStack.length === 0}
                >
                  {t({ ja: "修正を戻す", en: "Undo revision" })}
                </button>
              </div>
            </div>
            {commentRevisionHasActiveDiff && commentRevisionDiffSegments.length > 0 && (
              <div
                style={{
                  padding: "0.75rem",
                  borderRadius: "6px",
                  border: "1px solid var(--border)",
                  backgroundColor: "var(--ai-result-surface)",
                }}
              >
                <div style={{ fontWeight: "bold", marginBottom: "0.5rem" }}>
                  {t({ ja: "コメント修正の差分", en: "Comment revision diff" })}
                </div>
                <div style={{ fontSize: "0.85rem", color: "var(--muted-text)", marginBottom: "0.4rem" }}>
                  {t({
                    ja: "変更された行は赤文字で表示されます。",
                    en: "Changed lines are shown in red.",
                  })}
                </div>
                <pre
                  style={{
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    backgroundColor: "var(--ai-result-bg)",
                    padding: "0.6rem",
                    borderRadius: "6px",
                    border: "1px solid var(--border)",
                    maxHeight: "260px",
                    overflowY: "auto",
                    lineHeight: 1.6,
                  }}
                >
                  {commentRevisionDiffSegments.map((seg, idx) => (
                    <span
                      key={`comment-diff-${idx}`}
                      style={seg.changed ? { color: "#c53030", fontWeight: 700 } : undefined}
                    >
                      {seg.text}
                    </span>
                  ))}
                </pre>
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
                {isEditMode && (
                  <button
                    type="button"
                    onClick={handleUpdateEditedEpisode}
                    disabled={posting || !editEpisodeId}
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
                      ? t({ ja: "更新中...", en: "Updating..." })
                      : t({ ja: "このエピソードを更新", en: "Update this episode" })}
                  </button>
                )}
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
