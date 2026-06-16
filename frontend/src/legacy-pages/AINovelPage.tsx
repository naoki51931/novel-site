// frontend/src/pages/AINovelPage.jsx
import React, { useState, useEffect, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { getStoredLanguage, translate, useI18n } from "../lib/i18n";
import {
  applyPolishReplacement,
  buildPolishPrompt,
  describePolishIntensity,
} from "../lib/aiPolish.mjs";

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
const DEFAULT_AI_NOVEL_MODEL = "google/gemini-3-flash-preview";
const AI_NOVEL_RETRY_SETTINGS_VERSION = 2;
const DEFAULT_RETRY_MODE = true;
const DEFAULT_RETRY_MAX = 30;
const MAX_RETRY_MAX = 9999;
const REVISION_CHUNK_MAX_CHARS = 3200;
const COMMENT_REVISION_LIVE_PREVIEW_CHUNK_MAX_CHARS = 1200;
const COMMENT_REVISION_OUTPUT_RETRY_MAX = 5;
const COMMENT_REVISION_LIVE_PREVIEW_LINGER_MS = 15000;
const SEGMENT_TARGET_CHARS = 2000;
const SEGMENT_COUNT_MIN = 1;
const SEGMENT_COUNT_MAX = 30;
const CHUNK_BLOCK_TIMEOUT_MS = 5 * 60 * 1000;

type GeneratedChunkBlock = {
  index: number;
  instruction: string;
  body: string;
};

type StoryAgentMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
  appendedText?: string;
  appliedTitleHint?: string;
  appliedGenre?: string;
  appliedTone?: string;
  appliedIsR18?: boolean | null;
  appliedModel?: string;
  appliedChunkedGenerationEnabled?: boolean | null;
  appliedChunkedGenerationCount?: number | null;
  appliedChunkedGenerationPlans?: string[];
};

function clampSegmentCount(value: any) {
  const n = Number.parseInt(String(value), 10);
  if (!Number.isFinite(n)) return SEGMENT_COUNT_MIN;
  return Math.max(SEGMENT_COUNT_MIN, Math.min(SEGMENT_COUNT_MAX, n));
}

function makeSegmentPlanItem(index: any) {
  return {
    id: `seg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}-${index}`,
    instruction: "",
  };
}

function normalizeRetryMax(value: any) {
  const parsed = Number.parseInt(String(value), 10);
  if (!Number.isFinite(parsed)) return DEFAULT_RETRY_MAX;
  return Math.max(0, Math.min(MAX_RETRY_MAX, parsed));
}

function normalizeDraftRetrySettings(draft: any) {
  const version = Number.parseInt(String(draft?.retrySettingsVersion ?? 0), 10) || 0;
  const retryMode = typeof draft?.retryMode === "boolean" ? draft.retryMode : DEFAULT_RETRY_MODE;
  const retryMax = normalizeRetryMax(
    typeof draft?.retryMax === "number" ? draft.retryMax : DEFAULT_RETRY_MAX
  );
  if (version < AI_NOVEL_RETRY_SETTINGS_VERSION && retryMode === false && retryMax === 2) {
    return {
      retryMode: DEFAULT_RETRY_MODE,
      retryMax: DEFAULT_RETRY_MAX,
    };
  }
  return { retryMode, retryMax };
}

function savePendingAiPost(data: any) {
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

function savePendingAiJob(data: any) {
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

function normalizeAINovelResponse(data: any) {
  if (!data || typeof data !== "object") return data;
  if (typeof data.body !== "string") return data;

  const raw = data.body.trim();
  if (!raw) return data;

  const stripFence = (s: any) => {
    const t = (s || "").trim();
    if (!t.startsWith("```")) return t;
    const lines = t.split("\n");
    if (lines.length && lines[0].startsWith("```")) lines.shift();
    if (lines.length && lines[lines.length - 1].trim() === "```") lines.pop();
    return lines.join("\n").trim();
  };

  const tryParse = (s: any) => {
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

function mergeCharactersFieldText(baseValue: any, nextChunk: any) {
  const base = String(baseValue || "").trim();
  const addition = String(nextChunk || "").trim();
  if (!addition) {
    return { value: String(baseValue || ""), appended: "" };
  }
  if (base.includes(addition)) {
    return { value: String(baseValue || ""), appended: "" };
  }
  if (!base) {
    return { value: addition, appended: addition };
  }
  return {
    value: `${base}\n\n${addition}`,
    appended: addition,
  };
}

function getJwtUserId(token: any) {
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

function urlBase64ToUint8Array(base64String: any) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i += 1) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

function uint8ArrayToBase64Url(bytes: any) {
  if (!bytes || !bytes.length) return "";
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function buildLineDiffSegments(beforeText: any, afterText: any) {
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

  let i = 0;
  let j = 0;
  const segments: any[] = [];
  while (i < n && j < m) {
    if (beforeLines[i] === afterLines[j]) {
      segments.push({
        text: j === afterLines.length - 1 && i === beforeLines.length - 1 ? afterLines[j] : `${afterLines[j]}\n`,
        changed: false,
        kind: "unchanged",
      });
      i += 1;
      j += 1;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      segments.push({
        text: `- ${beforeLines[i]}\n`,
        changed: true,
        kind: "removed",
      });
      i += 1;
    } else {
      segments.push({
        text: `${j === afterLines.length - 1 ? `+ ${afterLines[j]}` : `+ ${afterLines[j]}\n`}`,
        changed: true,
        kind: "added",
      });
      j += 1;
    }
  }

  while (i < n) {
    segments.push({
      text: `- ${beforeLines[i]}${i === n - 1 ? "" : "\n"}`,
      changed: true,
      kind: "removed",
    });
    i += 1;
  }

  while (j < m) {
    segments.push({
      text: `${j === m - 1 ? `+ ${afterLines[j]}` : `+ ${afterLines[j]}\n`}`,
      changed: true,
      kind: "added",
    });
    j += 1;
  }

  return segments;
}

function getCommentDiffTint(depth: any, fadeEnabled: any) {
  if (!fadeEnabled) {
    return "rgba(197, 48, 48, 1)";
  }
  const level = Math.max(1, Number(depth) || 1);
  const alpha = Math.max(0.28, 0.96 - (level - 1) * 0.14);
  return `rgba(197, 48, 48, ${alpha})`;
}

function splitTextForRevision(text: any, maxChars = 7000) {
  const source = String(text || "");
  if (!source) return [];
  if (source.length <= maxChars) {
    return [{ start: 0, end: source.length, text: source }];
  }

  const chunks: any[] = [];
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
      ].filter((idx: any) => idx >= minCut);
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

function getCommentRevisionOutputIssue(text: any) {
  const raw = String(text || "");
  if (!raw.trim()) return "empty";

  const stripFence = (s: any) => {
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

function getGenerateOutputIssue(payload: any) {
  const rawBody = String(payload?.body || "");
  const rawIssue = getCommentRevisionOutputIssue(rawBody);
  const normalized = normalizeAINovelResponse(payload || {});
  const normalizedBody = String(normalized?.body || "");
  if (!normalizedBody.trim()) return "empty";
  if (rawIssue) return rawIssue;
  return "";
}

async function pushDebug(token: any, stage: any, detail: any = "") {
  try {
    const headers: Record<string, string> = {
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

async function ensureWebPushSubscription(token: any, onStatus: any = null) {
  const report = (stage: any, detail: any = "", ok: any = null) => {
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
      let lastErr: any = null;
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
        } catch (e: any) {
          lastErr = e;
          if (e?.name !== "AbortError" && e?.name !== "TypeError") break;
          await pushDebug(token, "subscribe_abort_retry", `attempt=${i + 1}`);
          report("subscribe_abort_retry", `attempt=${i + 1}`, null);
          await new Promise((resolve: any) => setTimeout(resolve, 1000));
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

    const headers: Record<string, string> = {
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
  } catch (e: any) {
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
  const [retryMode, setRetryMode] = useState(DEFAULT_RETRY_MODE);
  const [retryMax, setRetryMax] = useState(DEFAULT_RETRY_MAX);
  const [retryAttempts, setRetryAttempts] = useState(0);
  const [activeRetryMax, setActiveRetryMax] = useState<number | null>(null);
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
  const [episodeId, setEpisodeId] = useState<any>(null);
  const [continueNovelId, setContinueNovelId] = useState<any>(null);
  const [continueEpisodeNumber, setContinueEpisodeNumber] = useState<any>(null);
  const [canPostToContinueNovel, setCanPostToContinueNovel] = useState<boolean | null>(null); // null=判定中, true/false
  const [continueInfoError, setContinueInfoError] = useState("");
  const [isEditMode, setIsEditMode] = useState(false);
  const [editSourceBody, setEditSourceBody] = useState("");
  const [editEpisodeId, setEditEpisodeId] = useState<any>(null);

  const [loading, setLoading] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const [autoFillLoading, setAutoFillLoading] = useState(false);
  const [posting, setPosting] = useState(false);
  const [polishing, setPolishing] = useState(false);
  const [polishIntensity, setPolishIntensity] = useState(50);
  const [lastPolishContext, setLastPolishContext] = useState<any>(null);
  const [lastPolishScope, setLastPolishScope] = useState("full");
  const [hasActiveSelection, setHasActiveSelection] = useState(false);
  const [polishPreview, setPolishPreview] = useState<any>(null);
  const [revisionCommentInput, setRevisionCommentInput] = useState("");
  const [revisionComments, setRevisionComments] = useState<any[]>([]);
  const [lastRevisionTargetInfo, setLastRevisionTargetInfo] = useState<any>(null);
  const [revisingByComment, setRevisingByComment] = useState(false);
  const [revisionChatScope, setRevisionChatScope] = useState("full");
  const [commentRevisionDiffSegments, setCommentRevisionDiffSegments] = useState<any[]>([]);
  const [commentRevisionUndoStack, setCommentRevisionUndoStack] = useState<any[]>([]);
  const [commentRevisionHasActiveDiff, setCommentRevisionHasActiveDiff] = useState(false);
  const [commentRevisionLivePreviewEnabled, setCommentRevisionLivePreviewEnabled] = useState(false);
  const [commentRevisionLivePreviewBody, setCommentRevisionLivePreviewBody] = useState("");
  const [commentRevisionLiveDiffSegments, setCommentRevisionLiveDiffSegments] = useState<any[]>([]);
  const [commentRevisionLiveProgress, setCommentRevisionLiveProgress] = useState<any>({
    completed: 0,
    total: 0,
  });
  const [error, setError] = useState("");
  const [quotaError, setQuotaError] = useState("");
  const [premiumError, setPremiumError] = useState("");
  const [autoFillError, setAutoFillError] = useState("");
  const [autoFillPreview, setAutoFillPreview] = useState<any>(null);
  const [guestRemaining, setGuestRemaining] = useState<any>(null);
  const [userRemaining, setUserRemaining] = useState<any>(null);
  const [userPaidRemaining, setUserPaidRemaining] = useState(0);
  const [addonUnitGenerations, setAddonUnitGenerations] = useState(80);
  const [addonUnitPriceYen, setAddonUnitPriceYen] = useState(1000);
  const [addonCheckoutLoading, setAddonCheckoutLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [continuationBody, setContinuationBody] = useState("");
  const [postEpisodeTitle, setPostEpisodeTitle] = useState("");
  const [lastGenerateParams, setLastGenerateParams] = useState<any>(null);
  const [draftSlots, setDraftSlots] = useState<any[]>([]);
  const [draftSlotsLoading, setDraftSlotsLoading] = useState(false);
  const [draftSlotsError, setDraftSlotsError] = useState("");
  const [selectedDraftId, setSelectedDraftId] = useState("");
  const [draftTitle, setDraftTitle] = useState("");
  const [hasContinuationAttempted, setHasContinuationAttempted] = useState(false);
  const [redoContinuationArmed, setRedoContinuationArmed] = useState(false);
  const [aiCommentRevisionModel, setAiCommentRevisionModel] = useState("");
  const [textEditMode, setTextEditMode] = useState(false);
  const [textEditValue, setTextEditValue] = useState("");
  const [textEditOriginal, setTextEditOriginal] = useState("");
  const [isPushDebugUser, setIsPushDebugUser] = useState(false);
  const [pushDebugInfo, setPushDebugInfo] = useState<any>({
    stage: "idle",
    detail: "",
    ok: null,
    at: 0,
  });
  const [storyAgentOpen, setStoryAgentOpen] = useState(true);
  const [storyAgentVisible, setStoryAgentVisible] = useState(true);
  const [storyAgentInput, setStoryAgentInput] = useState("");
  const [storyAgentLoading, setStoryAgentLoading] = useState(false);
  const [storyAgentError, setStoryAgentError] = useState("");
  const [storyAgentMessages, setStoryAgentMessages] = useState<StoryAgentMessage[]>([
    {
      id: "story-agent-welcome",
      role: "assistant",
      content: t({
        ja: "小説案を書いてください。プロット、キャラクター、舞台設定の相談ができます。会話しながら、使えそうな案を「登場人物・設定」欄に追記しつつ、タイトルのイメージやジャンル、雰囲気、分割案も反映できます。",
        en: "Ask for a novel idea. I can help with plot, characters, and setting, append useful notes to the Characters & settings field, and also update the title idea, genre, tone, and segmented plan.",
      }),
    },
  ]);

  const fetchWithTimeout = async (url: any, options: any, timeoutMs: any) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { ...options, signal: controller.signal });
    } finally {
      clearTimeout(timeoutId);
    }
  };

  const isAbortError = (err: any) => err && (err.name === "AbortError" || err.code === "ABORT_ERR");

  const countChars = (value: any) => (value || "").length;
  const targetTotalChars = chunkedGenerationCount * SEGMENT_TARGET_CHARS;
  const canUseChunkedGeneration = !isEditMode;
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
  const effectiveCommentRevisionModel = aiCommentRevisionModel || model || DEFAULT_AI_NOVEL_MODEL;
  const effectiveCommentRevisionModelSource = aiCommentRevisionModel
    ? t({ ja: "マイページ設定", en: "My Page setting" })
    : t({ ja: "AI小説ページの現在モデル", en: "Current AI novel page model" });
  const committedCommentDiffDepth = Math.max(1, commentRevisionUndoStack.length);
  const liveCommentDiffDepth = Math.max(1, commentRevisionUndoStack.length + 1);
  const committedCommentDiffColor = getCommentDiffTint(
    committedCommentDiffDepth,
    commentRevisionLivePreviewEnabled
  );
  const liveCommentDiffColor = getCommentDiffTint(
    liveCommentDiffDepth,
    commentRevisionLivePreviewEnabled
  );

  const navigate = useNavigate();
  const location = useLocation();
  const resultBodyRef = useRef<HTMLPreElement | null>(null);
  const charactersInputRef = useRef<HTMLTextAreaElement | null>(null);
  const storyAgentMessagesRef = useRef<HTMLDivElement | null>(null);
  const combinedBodyRef = useRef("");
  const lastSelectionContextRef = useRef<any>(null);
  const jobPollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeJobSessionRef = useRef(0);
  const chunkedGenerateRetryRef = useRef<any>({
    enabled: false,
    attempts: 0,
    max: 0,
    endpoint: "",
    requestBody: null,
  });
  const localDraftRef = useRef<any>(null);
  const draftSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasUserInputRef = useRef(false);
  const segmentPrefsLoadedRef = useRef(false);
  const chunkedProgressTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const commentRevisionLivePreviewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [pendingJob, setPendingJob] = useState<any>(null);
  const hasAuthToken = Boolean(getAuthToken());
  const markUserInput = () => {
    hasUserInputRef.current = true;
  };

  const setChunkPlanCount = (nextCountRaw: any) => {
    const nextCount = clampSegmentCount(nextCountRaw);
    setChunkedGenerationCount(nextCount);
    setChunkedGenerationPlans((prev: any) => {
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
    chunkedGenerateRetryRef.current = {
      enabled: false,
      attempts: 0,
      max: 0,
      endpoint: "",
      requestBody: null,
    };
  };

  const startChunkedProgress = (count: any) => {
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

  const clearCommentRevisionLivePreviewTimer = () => {
    if (commentRevisionLivePreviewTimerRef.current) {
      clearTimeout(commentRevisionLivePreviewTimerRef.current);
      commentRevisionLivePreviewTimerRef.current = null;
    }
  };

  const resetCommentRevisionLivePreview = () => {
    clearCommentRevisionLivePreviewTimer();
    setCommentRevisionLivePreviewBody("");
    setCommentRevisionLiveDiffSegments([]);
    setCommentRevisionLiveProgress({ completed: 0, total: 0 });
  };

  const lingerCommentRevisionLivePreview = () => {
    clearCommentRevisionLivePreviewTimer();
    commentRevisionLivePreviewTimerRef.current = setTimeout(() => {
      setCommentRevisionLivePreviewBody("");
      setCommentRevisionLiveDiffSegments([]);
      setCommentRevisionLiveProgress({ completed: 0, total: 0 });
      commentRevisionLivePreviewTimerRef.current = null;
    }, COMMENT_REVISION_LIVE_PREVIEW_LINGER_MS);
  };

  useEffect(() => () => {
    if (chunkedProgressTimerRef.current) {
      clearInterval(chunkedProgressTimerRef.current);
      chunkedProgressTimerRef.current = null;
    }
    clearCommentRevisionLivePreviewTimer();
  }, []);

  useEffect(() => {
    if (!storyAgentOpen) return;
    if (!storyAgentMessagesRef.current) return;
    storyAgentMessagesRef.current.scrollTop = storyAgentMessagesRef.current.scrollHeight;
  }, [storyAgentMessages, storyAgentOpen, storyAgentLoading]);

  const handleAddChunkPlan = () => {
    markUserInput();
    if (chunkedGenerationCount >= SEGMENT_COUNT_MAX) return;
    setChunkPlanCount(chunkedGenerationCount + 1);
  };

  const handleInsertChunkPlanBelow = (index: any) => {
    markUserInput();
    if (chunkedGenerationCount >= SEGMENT_COUNT_MAX) return;
    setChunkedGenerationPlans((prev: any) => {
      const safePrev = Array.isArray(prev) ? prev : [];
      const insertAt = Math.max(0, Math.min(safePrev.length, Number(index) + 1));
      const next = [...safePrev];
      next.splice(insertAt, 0, makeSegmentPlanItem(insertAt + 1));
      return next;
    });
    setChunkedGenerationCount((prev: any) => Math.min(SEGMENT_COUNT_MAX, Number(prev || 0) + 1));
  };

  const handleRemoveChunkPlan = (index: any) => {
    markUserInput();
    if (chunkedGenerationCount <= SEGMENT_COUNT_MIN) return;
    setChunkedGenerationPlans((prev: any) => {
      const safePrev = Array.isArray(prev) ? prev : [];
      const next = safePrev.filter((_: any, i: any) => i !== index);
      return next.length > 0 ? next : [makeSegmentPlanItem(1)];
    });
    setChunkedGenerationCount((prev: any) => Math.max(SEGMENT_COUNT_MIN, Number(prev || 1) - 1));
  };

  const handleChangeChunkPlanInstruction = (index: any, value: any) => {
    markUserInput();
    setChunkedGenerationPlans((prev: any) =>
      (prev || []).map((item: any, i: any) => (i === index ? { ...item, instruction: value } : item))
    );
  };

  useEffect(() => {
    const fetchRemaining = async () => {
      try {
        const token = getAuthToken();
        const res = await fetch("/api/ai/novels/remaining", {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
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
      } catch (e: any) {
        console.error("failed to load ai remaining", e);
      }
    };

    fetchRemaining();
  }, []);

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      setAiCommentRevisionModel("");
      return;
    }
    const loadProfilePrefs = async () => {
      try {
        const res = await fetch("/api/users/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return;
        const data = await res.json().catch(() => ({}));
        setAiCommentRevisionModel(
          typeof data?.ai_comment_revision_model === "string"
            ? data.ai_comment_revision_model
            : ""
        );
      } catch (e: any) {
        console.error("failed to load ai comment revision model", e);
      }
    };
    loadProfilePrefs();
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
          .filter((item: any) => item && typeof item === "object")
          .map((item: any, idx: any) => ({
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
    } catch (e: any) {
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
          .map((item: any, idx: any) => ({
            id: typeof item?.id === "string" && item.id ? item.id : makeSegmentPlanItem(idx + 1).id,
            instruction: String(item?.instruction || ""),
          })),
      };
      localStorage.setItem(AI_NOVEL_SEGMENT_PREFS_KEY, JSON.stringify(payload));
    } catch (e: any) {
      console.error("failed to save ai segment prefs", e);
    }
  }, [chunkedGenerationEnabled, chunkedGenerationCount, chunkedGenerationPlans]);

  const stopJobPolling = () => {
    if (jobPollTimerRef.current) {
      clearTimeout(jobPollTimerRef.current);
      jobPollTimerRef.current = null;
    }
  };

  const extractDraftTimestamp = (draft: any) => {
    if (!draft) return 0;
    const raw = draft.saved_at || draft.savedAt || null;
    if (!raw) return 0;
    const ts = Date.parse(raw);
    return Number.isFinite(ts) ? ts : 0;
  };

  const hasUrlModeOverride = () => {
    if (typeof window === "undefined") return false;
    const params = new URLSearchParams(window.location.search);
    return Boolean(
      params.get("episode_id")
      || params.get("edit_episode_id")
      || params.get("mode") === "new_novel"
    );
  };

  const resetToNewNovelMode = () => {
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
  };

  const applyDraft = (draft: any, options: any = {}) => {
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
    const normalizedRetry = normalizeDraftRetrySettings(draft);
    setRetryMode(normalizedRetry.retryMode);
    setRetryMax(normalizedRetry.retryMax);
    if (typeof draft.chunkedGenerationEnabled === "boolean") {
      setChunkedGenerationEnabled(draft.chunkedGenerationEnabled);
    }
    const draftChunkCount = clampSegmentCount(
      typeof draft.chunkedGenerationCount === "number" ? draft.chunkedGenerationCount : 2
    );
    setChunkedGenerationCount(draftChunkCount);
    if (Array.isArray(draft.chunkedGenerationPlans) && draft.chunkedGenerationPlans.length > 0) {
      const normalizedPlans = draft.chunkedGenerationPlans
        .filter((item: any) => item && typeof item === "object")
        .map((item: any, idx: any) => ({
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
      setChunkedGenerationPlans(Array.from({ length: draftChunkCount }, (_: any, idx: any) => makeSegmentPlanItem(idx + 1)));
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
          .filter((item: any) => item && typeof item === "object")
          .map((item: any) => ({
            role: item.role === "assistant" ? "assistant" : "user",
            content: String(item.content || ""),
            at: typeof item.at === "string" ? item.at : new Date().toISOString(),
          }))
          .filter((item: any) => item.content.trim())
      );
    }
    if (Array.isArray(draft.commentRevisionUndoStack)) {
      setCommentRevisionUndoStack(
        draft.commentRevisionUndoStack
          .filter((item: any) => typeof item === "string")
          .map((item: any) => String(item))
      );
    } else if (typeof draft.commentRevisionUndoBody === "string") {
      const legacyUndoBody = String(draft.commentRevisionUndoBody || "");
      setCommentRevisionUndoStack(legacyUndoBody ? [legacyUndoBody] : []);
    }
    if (typeof draft.commentRevisionHasActiveDiff === "boolean") {
      setCommentRevisionHasActiveDiff(draft.commentRevisionHasActiveDiff);
    }
    if (typeof draft.commentRevisionLivePreviewEnabled === "boolean") {
      setCommentRevisionLivePreviewEnabled(draft.commentRevisionLivePreviewEnabled);
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
    retrySettingsVersion: AI_NOVEL_RETRY_SETTINGS_VERSION,
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
    commentRevisionLivePreviewEnabled,
    saved_at: new Date().toISOString(),
  });

  const buildDefaultDraftTitle = () => {
    const base = (draftTitle || "").trim() || (result?.generated_title || "").trim() || (titleHint || "").trim();
    if (base) return base;
    const stamp = new Date().toISOString().slice(0, 16).replace("T", " ");
    return t({ ja: `AI生成 ${stamp}`, en: `AI Draft ${stamp}` });
  };

  const handleSelectDraftSlot = (value: any) => {
    setSelectedDraftId(value);
    const match = draftSlots.find((item: any) => String(item.id) === String(value));
    if (match && typeof match.title === "string") {
      setDraftTitle(match.title);
    }
  };

  const handleJobResult = (job: any, payload: any) => {
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
        setContinuationBody((prev: any) => (prev ? `${prev}\n\n${nextBody}` : nextBody));
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

  const applyChunkedProgressPayload = (payload: any) => {
    const normalized = normalizeAINovelResponse(payload || {});
    const meta = normalized?.chunked_generation;
    if (!meta?.enabled) return;
    if (chunkedProgressTimerRef.current) {
      clearInterval(chunkedProgressTimerRef.current);
      chunkedProgressTimerRef.current = null;
    }
    const totalBlocks = clampSegmentCount(meta.total_blocks || chunkedGenerationCount || 1);
    const completedBlocks = Math.max(0, Math.min(totalBlocks, Number(meta.completed_blocks || 0)));
    const currentBlock = Math.max(
      1,
      Math.min(totalBlocks, Number(meta.current_block || completedBlocks || 1))
    );
    const percent = Math.max(1, Math.min(100, Number(meta.percent || 0)));
    setChunkedProgressActive(!meta.done);
    setChunkedProgressBlock(currentBlock);
    setChunkedCompletedBlocks(completedBlocks);
    setChunkedProgressPercent(percent);
    if (String(normalized?.body || "").trim()) {
      setResult({
        generated_title:
          normalized?.generated_title || titleHint || t({ ja: "生成された小説", en: "Generated Novel" }),
        body: normalized.body,
      });
    }
    if (typeof normalized?.guest_remaining === "number") {
      setGuestRemaining(normalized.guest_remaining);
    }
    if (typeof normalized?.user_remaining === "number") {
      setUserRemaining(normalized.user_remaining);
    }
  };

  const retryChunkedGenerateForInvalidOutput = async (issue: any) => {
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

  const pollAiJob = async (job: any, sessionId = activeJobSessionRef.current) => {
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
        { headers: token ? { Authorization: `Bearer ${token}` } : undefined },
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
      if (job?.kind === "generate" && data?.response?.chunked_generation?.enabled) {
        applyChunkedProgressPayload(data.response);
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
        if (job?.kind === "generate" && data?.response?.chunked_generation?.enabled) {
          applyChunkedProgressPayload(data.response);
        }
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
    } catch (err: any) {
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

  const startJobPolling = (job: any) => {
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

  const resumePendingJobIfAny = (kind: any) => {
    const job = pendingJob || loadPendingAiJob();
    if (!job || job.kind !== kind || !job.job_id) return false;
    startJobPolling(job);
    return true;
  };

  const fetchDraftSlots = async (selectId: any = null) => {
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
    } catch (e: any) {
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
    } catch (e: any) {
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
    } catch (e: any) {
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
    } catch (e: any) {
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
    const target = draftSlots.find((item: any) => String(item.id) === String(selectedDraftId));
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
    } catch (e: any) {
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
    setResult((prev: any) => ({
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
    setRetryMode(DEFAULT_RETRY_MODE);
    setRetryMax(DEFAULT_RETRY_MAX);
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
          setStoryAgentVisible(true);
          return;
        }
        const data = await res.json().catch(() => ({}));
        setIsPushDebugUser((data?.username || "") === "demo02");
        setStoryAgentVisible(data?.ai_story_agent_visible !== false);
      } catch {
        setIsPushDebugUser(false);
        setStoryAgentVisible(true);
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
    } catch (e: any) {
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
      } catch (e: any) {
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
      } catch (e: any) {
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
    commentRevisionLivePreviewEnabled,
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
      }).catch((e: any) => {
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
    commentRevisionLivePreviewEnabled,
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
    const params = new URLSearchParams(location.search);
    if (params.get("mode") !== "new_novel") return;
    resetToNewNovelMode();
  }, [location.search]);

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
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      })
        .then((res: any) => res.json().catch(() => ({})))
        .then((data: any) => {
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
    const params = new URLSearchParams(location.search);
    if (params.get("mode") === "new_novel") return;
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
      } catch (e: any) {
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
  }, [location.search]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("mode") === "new_novel") return;
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
      } catch (e: any) {
        console.error(e);
        setError(
          e.message ||
            t({ ja: "編集用エピソードの読み込み中にエラーが発生しました。", en: "Failed to load episode for edit." })
        );
      }
    })();
  }, [location.search]);

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

  const getSelectionContext = (selectionOverride: any = null) => {
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

  const buildSegmentedNovelPrompt = (params: any, planItems: any, segmentChars = SEGMENT_TARGET_CHARS) => {
    const safePlans = (planItems || []).map((item: any, idx: any) => ({
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
    const scopeLines = safePlans.map((item: any) => {
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
    params: any,
    blockInstruction: any,
    blockIndex: any,
    totalBlocks: any,
    previousText: any,
    previousBlocks: GeneratedChunkBlock[] = [],
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
      .map((block: any) => {
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
        : params.isContinueMode
        ? `以下は分割生成の第1/${totalBlocks}ブロックです。前のエピソード本文の続きとして本文のみを書いてください。`
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
      .filter((line: any) => line !== "")
      .join("\n");
  };

  const requestGenerateJob = async (endpoint: any, token: any, bodyPayload: any) => {
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

  const pollGenerateJobUntilDone = async (jobId: any, token: any) => {
    const sleep = (ms: any) => new Promise((resolve: any) => setTimeout(resolve, ms));
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
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
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

  const buildContinuationPrompt = (baseBody: any, params: any) => {
    const lengthMap: Record<string, string> = {
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

  const buildEditPrompt = (baseBody: any, params: any) => {
    const lengthMap: Record<string, string> = {
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

  const buildRevisionPromptFromComments = (baseBody: any, params: any, comments: any, options: any = {}) => {
    const scope = options?.scope === "selection" ? "selection" : "full";
    const chunkIndex = Number(options?.chunkIndex || 0);
    const chunkTotal = Number(options?.chunkTotal || 0);
    const sourceChars = Number(options?.sourceChars || 0);
    const isChunkedRevision = chunkTotal > 1 && chunkIndex >= 1;
    const { level, strengthText } = describePolishIntensity(polishIntensity);
    const r18Note = params.isR18
      ? "成人向けの内容を許可します。性的描写を含めても構いません。"
      : "一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。";
    const titleHintText = params.titleHint || "指定なし";
    const genreText = params.genre || "指定なし";
    const toneText = params.tone || "指定なし";
    const charactersText = params.characters || "指定なし";
    const userComments = (comments || [])
      .filter((item: any) => item && item.role === "user" && String(item.content || "").trim())
      .map((item: any, idx: any) => `${idx + 1}. ${String(item.content || "").trim()}`);
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
      `添削の強さ: ${strengthText} (${level}/100)`,
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
    const latestUserCommentFromHistory = [...revisionComments]
      .reverse()
      .find((item: any) => item && item.role === "user" && String(item.content || "").trim());
    const effectiveComment = latestComment || String(latestUserCommentFromHistory?.content || "").trim();
    if (!effectiveComment) {
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
    const nextComments = latestComment
      ? [
          ...revisionComments,
          { role: "user", content: effectiveComment, at: new Date().toISOString() },
        ]
      : revisionComments;
    setRevisionComments(nextComments);
    setRevisionCommentInput("");
    setRevisingByComment(true);
    setLastRevisionTargetInfo(null);
    setRetryAttempts(0);
    setActiveRetryMax(Boolean(params.retryMode) ? Number(params.retryMax || 0) : 0);
    resetCommentRevisionLivePreview();
    setError("");
    setQuotaError("");
    setPremiumError("");
    setAutoFillError("");

    try {
      const userCommentTexts = nextComments
        .filter((item: any) => item && item.role === "user" && String(item.content || "").trim())
        .map((item: any) => String(item.content || "").trim());
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
              normalizedScope === "selection"
              && Number.isFinite(relStart)
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
        } catch (targetErr: any) {
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
      const runRevisionJob = async (bodyText: any, promptOptions: any = {}) => {
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
            model: aiCommentRevisionModel || params.model || DEFAULT_AI_NOVEL_MODEL,
            r18: params.isR18,
            retry_mode: disableServerRetry ? false : Boolean(params.retryMode),
            retry_max: disableServerRetry ? 0 : Number(params.retryMax || 0),
            prompt,
          }),
        });

        let errorDetail: any = null;
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

        const sleep = (ms: any) => new Promise((resolve: any) => setTimeout(resolve, ms));
        const startedAt = Date.now();
        let finalPayload: any = null;
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
            headers: token ? { Authorization: `Bearer ${token}` } : undefined,
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

      const revisionChunkMaxChars = commentRevisionLivePreviewEnabled
        ? COMMENT_REVISION_LIVE_PREVIEW_CHUNK_MAX_CHARS
        : REVISION_CHUNK_MAX_CHARS;
      const chunks = splitTextForRevision(targetBody, revisionChunkMaxChars);
      if (commentRevisionLivePreviewEnabled) {
        setCommentRevisionLiveProgress({ completed: 0, total: chunks.length });
      }
      const useGlobalRetryAcrossChunks =
        normalizedScope === "full"
        && chunks.length > 1
        && Boolean(params.retryMode)
        && Number(params.retryMax || 0) > 0;
      const globalRetryMax = useGlobalRetryAcrossChunks ? Number(params.retryMax || 0) : 0;
      let globalRetryAttempts = 0;
      const revisedParts: any[] = [];
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
            
          } catch (chunkErr: any) {
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
        if (commentRevisionLivePreviewEnabled) {
          const provisionalTargetBody = revisedParts
            .concat(chunks.slice(chunkIndex + 1).map((pendingChunk: any) => pendingChunk.text))
            .join("");
          const provisionalFullBody =
            targetContext && typeof targetContext.start === "number" && typeof targetContext.end === "number"
              ? applyPolishReplacement(
                  targetContext.fullText,
                  targetContext.start,
                  targetContext.end,
                  provisionalTargetBody
                )
              : provisionalTargetBody;
          setCommentRevisionLivePreviewBody(provisionalFullBody);
          setCommentRevisionLiveDiffSegments(buildLineDiffSegments(generatedFullBody, provisionalFullBody));
          setCommentRevisionLiveProgress({ completed: chunkIndex + 1, total: chunks.length });
        }
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
      setResult((prev: any) => ({
        ...(prev || {}),
        body: nextFullBody,
      }));
      setContinuationBody("");
      setCommentRevisionUndoStack((prev: any) => [...prev, generatedFullBody]);
      setCommentRevisionDiffSegments(buildLineDiffSegments(generatedFullBody, nextFullBody));
      setCommentRevisionHasActiveDiff(true);
      lingerCommentRevisionLivePreview();
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
      setRevisionComments((prev: any) => [
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
    } catch (err: any) {
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
    setResult((prev: any) => ({
      ...(prev || {}),
      body: restoreBody,
    }));
    setContinuationBody("");
    setCommentRevisionUndoStack((prev: any) => prev.slice(0, -1));
    setCommentRevisionDiffSegments([]);
    setCommentRevisionHasActiveDiff(false);
    resetCommentRevisionLivePreview();
    setRevisionComments((prev: any) => [
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
    } catch (e: any) {
      setError(
        e?.message ||
          t({ ja: "追加課金Checkoutの開始中にエラーが発生しました。", en: "Failed to start add-on checkout." })
      );
    } finally {
      setAddonCheckoutLoading(false);
    }
  };

  const handleGenerate = async (e: any) => {
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
    setCommentRevisionLivePreviewBody("");
    setCommentRevisionLiveDiffSegments([]);
    setCommentRevisionLiveProgress({ completed: 0, total: 0 });
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
      isContinueMode,
    };
    // ★ ここで「通常の新規生成」と「エピソード続き生成」を切り替える
    const endpoint = episodeId
      ? `/api/ai/episodes/${episodeId}/continue_job`
      : "/api/ai/novels/generate_job";
    const activeChunkCount = clampSegmentCount(chunkedGenerationCount);
    const activeChunkPlans = (chunkedGenerationPlans || []).slice(0, activeChunkCount);
    const useChunkedGeneration =
      !isEditMode
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
      ...(useChunkedGeneration
        ? {
            chunked_generation_enabled: true,
            chunked_generation_count: activeChunkCount,
            chunked_generation_plans: activeChunkPlans.map((item: any) => ({
              instruction: String(item?.instruction || ""),
            })),
          }
        : {}),
    };
    if (useChunkedGeneration) {
      chunkedGenerateRetryRef.current = {
        ...chunkedGenerateRetryRef.current,
        requestBody,
      };
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
    } catch (err: any) {
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

  const handleGenerateContinuation = async (baseBodyOverride: any = null) => {
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
    } catch (err: any) {
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

  const handlePolishText = async (overrideContext: any = null, options: any = {}) => {
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

      let errorDetail: any = null;
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
    } catch (err: any) {
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
    setResult((prev: any) => ({
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
    } catch (err: any) {
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
        ? listData.map((e: any) => (typeof e?.number === "number" ? e.number : null)).filter((n: any) => n !== null)
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
    } catch (err: any) {
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
    } catch (err: any) {
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
    } catch (e: any) {
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
    const stripFence = (s: any) => {
      const t = (s || "").trim();
      if (!t.startsWith("```")) return t;
      const lines = t.split("\n");
      if (lines.length && lines[0].startsWith("```")) lines.shift();
      if (lines.length && lines[lines.length - 1].trim() === "```") lines.pop();
      return lines.join("\n").trim();
    };

    const tryParse = (s: any) => {
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

    setResult((prev: any) => ({
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
        setGenre((prev: any) => {
          const base = (prev || "").trim();
          return base ? `${base} / ${appendGenre}` : appendGenre;
        });
      }
      if (appendCharacters) {
        setCharacters((prev: any) => {
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
    } catch (e: any) {
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

  const buildStoryAgentPrompt = (history: StoryAgentMessage[]) => {
    return {
      mode: isEditMode
        ? "episode_edit"
        : isContinueMode
          ? "continue_episode"
          : "new_novel",
      title_hint: titleHint || "",
      genre: genre || "",
      characters: characters || "",
      tone: tone || "",
      is_r18: isR18,
      selected_model: model || "",
      chunked_generation_enabled: chunkedGenerationEnabled,
      chunked_generation_count: chunkedGenerationCount,
      chunked_generation_plans: (chunkedGenerationPlans || [])
        .slice(0, chunkedGenerationCount)
        .map((item: any) => String(item?.instruction || "").trim())
        .filter(Boolean),
      conversation: history.slice(-8).map((item) => ({
        role: item.role,
        content: item.content,
      })),
    };
  };

  const handleStoryAgentSend = async () => {
    const message = String(storyAgentInput || "").trim();
    if (!message || storyAgentLoading) return;

    markUserInput();
    setStoryAgentOpen(true);
    setStoryAgentError("");
    setStoryAgentInput("");

    const userMessage: StoryAgentMessage = {
      id: `story-agent-user-${Date.now()}`,
      role: "user",
      content: message,
    };
    const conversation = [...storyAgentMessages, userMessage];
    setStoryAgentMessages(conversation);
    setStoryAgentLoading(true);

    try {
      const token = getAuthToken();
      const res = await fetchWithTimeout(
        "/api/ai/novels/story-agent",
        {
          method: "POST",
          headers: token
            ? {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
              }
            : { "Content-Type": "application/json" },
          body: JSON.stringify(buildStoryAgentPrompt(conversation)),
        },
        30000
      );
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          String(payload?.detail || "").trim()
            || t({
              ja: "AIエージェントの返答取得に失敗しました。",
              en: "Failed to get a response from the AI agent.",
            })
        );
      }
      const reply = String(payload?.reply || "").trim();
      if (!reply) {
        throw new Error(
          t({
            ja: "AIエージェントの返答が空でした。",
            en: "The AI agent reply was empty.",
          })
        );
      }
      const merged = mergeCharactersFieldText(
        charactersInputRef.current?.value ?? characters ?? "",
        payload?.characters_append || ""
      );

      if (typeof payload?.guest_remaining === "number") {
        setGuestRemaining(payload.guest_remaining);
      }
      if (typeof payload?.user_remaining === "number") {
        setUserRemaining(payload.user_remaining);
      }

      const nextTitleHint = typeof payload?.title_hint === "string" ? payload.title_hint.trim() : "";
      const nextGenre = typeof payload?.genre === "string" ? payload.genre.trim() : "";
      const nextTone = typeof payload?.tone === "string" ? payload.tone.trim() : "";
      const nextIsR18 = typeof payload?.is_r18 === "boolean" ? payload.is_r18 : null;
      const nextModel = typeof payload?.suggested_model === "string" ? payload.suggested_model.trim() : "";
      const nextChunkedEnabled =
        typeof payload?.chunked_generation_enabled === "boolean"
          ? payload.chunked_generation_enabled
          : null;
      const nextChunkedCount =
        typeof payload?.chunked_generation_count === "number"
          ? clampSegmentCount(payload.chunked_generation_count)
          : null;
      const nextChunkedPlans = Array.isArray(payload?.chunked_generation_plans)
        ? payload.chunked_generation_plans
            .map((item: any) => String(item || "").trim())
            .filter(Boolean)
            .slice(0, SEGMENT_COUNT_MAX)
        : [];

      if (merged.appended) {
        setCharacters(merged.value);
      }
      if (nextTitleHint) {
        setTitleHint(nextTitleHint);
      }
      if (nextGenre) {
        setGenre(nextGenre);
      }
      if (nextTone) {
        setTone(nextTone);
      }
      if (typeof nextIsR18 === "boolean") {
        setIsR18(nextIsR18);
      }
      if (nextModel) {
        setModel(nextModel);
      }
      if (typeof nextChunkedEnabled === "boolean") {
        setChunkedGenerationEnabled(nextChunkedEnabled);
      }
      if (typeof nextChunkedCount === "number") {
        setChunkedGenerationCount(nextChunkedCount);
      }
      if (nextChunkedPlans.length > 0) {
        const targetCount = typeof nextChunkedCount === "number" ? nextChunkedCount : nextChunkedPlans.length;
        const safeCount = clampSegmentCount(targetCount);
        const normalizedPlans = Array.from({ length: safeCount }, (_: any, idx: any) => ({
          ...makeSegmentPlanItem(idx + 1),
          instruction: nextChunkedPlans[idx] || "",
        }));
        setChunkedGenerationPlans(normalizedPlans);
        if (typeof nextChunkedCount !== "number") {
          setChunkedGenerationCount(safeCount);
        }
      }

      setStoryAgentMessages((prev) => [
        ...prev,
        {
          id: `story-agent-assistant-${Date.now()}`,
          role: "assistant",
          content: reply,
          appendedText: merged.appended,
          appliedTitleHint: nextTitleHint || undefined,
          appliedGenre: nextGenre || undefined,
          appliedTone: nextTone || undefined,
          appliedIsR18: nextIsR18,
          appliedModel: nextModel || undefined,
          appliedChunkedGenerationEnabled: nextChunkedEnabled,
          appliedChunkedGenerationCount: nextChunkedCount,
          appliedChunkedGenerationPlans: nextChunkedPlans,
        },
      ]);
    } catch (e: any) {
      console.error(e);
      const messageText =
        e?.message ||
        t({
          ja: "AIエージェントの返答取得に失敗しました。",
          en: "Failed to get a response from the AI agent.",
        });
      setStoryAgentError(messageText);
    } finally {
      setStoryAgentLoading(false);
    }
  };

  return (
    <>
    <div style={{ maxWidth: "900px", margin: "0 auto", padding: "1.5rem" }}>
      <h1 style={{ fontSize: "1.8rem", marginBottom: "1rem" }}>
        {isEditMode
          ? t({ ja: "AI小説：エピソード編集", en: "AI Novel: Edit an Episode" })
          : isContinueMode
          ? t({ ja: "AI小説：エピソードの続き生成", en: "AI Novel: Continue an Episode" })
          : t({ ja: "AI小説生成・小説生成AI（未ログインは10回まで）", en: "AI Novel Generator and Story Writing AI (up to 10 for guests)" })}
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
            ja: "お題、登場人物、ジャンル、文体を入力して「AI小説を生成する」を押すと、小説生成AIがプロットや会話を含む物語の下書きを作成します。",
            en: "Enter a theme, characters, genre, and style, then click “Generate AI novel” to use Lexis as an AI novel generator for a story draft with plot, dialogue, and prose.",
          })}
          <br />
          {t({
            ja: "生成結果は編集して、小説やエピソードとして投稿できます。続き生成や執筆支援にも使えます。",
            en: "You can edit the result, post it as a novel or episode, and use the same writing assistant for continuations.",
          })}
        </p>
      )}

      {!isEditMode && !isContinueMode && (
        <section
          style={{
            marginBottom: "1.25rem",
            padding: "0.9rem 1rem",
            border: "1px solid var(--border)",
            borderRadius: "8px",
            backgroundColor: "var(--ai-result-surface)",
          }}
        >
          <h2 style={{ fontSize: "1.05rem", margin: "0 0 0.6rem" }}>
            {t({ ja: "AI小説生成・小説生成AI・R18小説生成に対応", en: "AI novel generator, story writing AI, and R18 draft support" })}
          </h2>
          <p style={{ margin: "0 0 0.45rem", color: "var(--muted-text)", lineHeight: 1.7 }}>
            {t({
              ja: "Lexis の AI小説生成では、一般向けの物語作成だけでなく、R18小説生成や官能小説生成を想定した下書き作成にも対応しています。タイトル案、ジャンル、登場人物、文体を入れて、長編の叩き台や短編の導入をまとめて作れます。",
              en: "Lexis works as an AI novel generator and story writing AI for general fiction, long-form drafts, short story openings, character-driven scenes, and R18 or adult novel draft generation.",
            })}
          </p>
          <p style={{ margin: "0 0 0.45rem", color: "var(--muted-text)", lineHeight: 1.7 }}>
            {t({
              ja: "R18 を有効にすると、成人向け表現を含む小説の構成案や続き生成にも使えます。生成後はそのまま投稿せず、必要に応じてご自身で確認・編集してから公開してください。",
              en: "When R18 is enabled, you can draft adult-oriented story outlines, scenes, and episode continuations. Review and edit generated text before publishing.",
            })}
          </p>
          <ul style={{ margin: 0, paddingLeft: "1.2rem", color: "var(--muted-text)", lineHeight: 1.7 }}>
            <li>{t({ ja: "AI小説生成: プロット、導入、会話、地の文をまとめて生成", en: "AI novel generator: create plot, opening, dialogue, and prose" })}</li>
            <li>{t({ ja: "R18小説生成: 年齢区分を切り替えて成人向けの表現方針を調整", en: "R18 novel generation: adjust adult draft direction with age rating" })}</li>
            <li>{t({ ja: "続き生成: 既存エピソードの続きや次の2000文字単位の展開を作成", en: "Episode continuation generator: create the next section of an existing story" })}</li>
          </ul>
        </section>
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
                  onChange={(e: any) => handleSelectDraftSlot(e.target.value)}
                  style={{ padding: "0.45rem", minWidth: "220px" }}
                >
                  <option value="">{t({ ja: "保存データを選択", en: "Select a saved draft" })}</option>
                  {draftSlots.map((item: any) => (
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
                  onChange={(e: any) => setDraftTitle(e.target.value)}
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
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
          <button
            type="button"
            onClick={() => navigate("/ai-novel?mode=new_novel")}
            className="btn btn-border"
          >
            {t({ ja: "新規で始める", en: "Start new" })}
          </button>
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
            onChange={(e: any) => {
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
              onChange={(e: any) => {
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
                      {autoFillPreview.sources.map((s: any, idx: any) => (
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
            onChange={(e: any) => {
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
              onChange={(e: any) => {
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
            onChange={(e: any) => {
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
                onChange={(e: any) => {
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
                onChange={(e: any) => {
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
                {chunkedGenerationPlans.slice(0, chunkedGenerationCount).map((item: any, idx: any) => {
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
                        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
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
                            onClick={() => handleInsertChunkPlanBelow(idx)}
                            disabled={chunkedGenerationCount >= SEGMENT_COUNT_MAX}
                            aria-label={t({ ja: "このブロックの下に追加", en: "Add below this block" })}
                            title={t({ ja: "このブロックの下に追加", en: "Add below this block" })}
                            style={{ minWidth: "2.2rem", padding: "0.35rem 0.7rem", fontWeight: 700 }}
                          >
                            +
                          </button>
                          <button
                            type="button"
                            className="btn btn-border"
                            onClick={() => handleRemoveChunkPlan(idx)}
                            disabled={chunkedGenerationCount <= SEGMENT_COUNT_MIN}
                            aria-label={t({ ja: "このブロックを削除", en: "Remove this block" })}
                            title={t({ ja: "このブロックを削除", en: "Remove this block" })}
                            style={{ minWidth: "2.2rem", padding: "0.35rem 0.7rem", fontWeight: 700 }}
                          >
                            -
                          </button>
                        </div>
                      </div>
                      <textarea
                        value={item.instruction || ""}
                        onChange={(e: any) => handleChangeChunkPlanInstruction(idx, e.target.value)}
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
              onChange={(e: any) => {
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
            onChange={(e: any) => {
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
              onChange={(e: any) => {
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
              max={MAX_RETRY_MAX}
              value={retryMax}
              onChange={(e: any) => {
                markUserInput();
                const next = Number.parseInt(e.target.value, 10);
                if (!Number.isFinite(next)) return;
                const clamped = Math.max(0, Math.min(MAX_RETRY_MAX, next));
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
                  onChange={(e: any) => setPolishIntensity(Number(e.target.value))}
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
              onChange={(e: any) => setTextEditValue(e.target.value)}
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
                  marginBottom: "0.5rem",
                  fontSize: "0.82rem",
                  color: "var(--muted-text)",
                }}
              >
                {t({ ja: "コメント修正で使用するモデル", en: "Model used for comment revision" })}:{" "}
                <strong style={{ color: "var(--text-color)" }}>{effectiveCommentRevisionModel}</strong>
                {` (${effectiveCommentRevisionModelSource})`}
              </div>
              <label
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.45rem",
                  marginBottom: "0.6rem",
                  fontSize: "0.85rem",
                  color: "var(--text-color)",
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={commentRevisionLivePreviewEnabled}
                  onChange={(e: any) => setCommentRevisionLivePreviewEnabled(Boolean(e.target.checked))}
                />
                <span>
                  {t({
                    ja: "コメント修正中にライブ差分を表示し、修正を重ねるほど赤字を薄くする",
                    en: "Show live diff during comment revision and fade red as revisions stack",
                  })}
                </span>
              </label>
              {commentRevisionLivePreviewEnabled && (
                <div style={{ fontSize: "0.8rem", color: "var(--muted-text)", marginBottom: "0.6rem" }}>
                  {t({
                    ja: "ライブプレビューON時は約1200文字ごとに細かく分割してAIへ送り、返ってきた順に差分を更新します。",
                    en: "When live preview is ON, the text is split into about 1200-char chunks and the diff updates as each AI response returns.",
                  })}
                </div>
              )}
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
                  revisionComments.map((item: any, idx: any) => (
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
                onChange={(e: any) => {
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
            {commentRevisionLivePreviewEnabled && commentRevisionLiveDiffSegments.length > 0 && (
              <div
                style={{
                  padding: "0.75rem",
                  borderRadius: "6px",
                  border: "1px solid #f8b4b4",
                  backgroundColor: "#fff5f5",
                }}
              >
                <div style={{ fontWeight: "bold", marginBottom: "0.5rem" }}>
                  {revisingByComment
                    ? t({ ja: "コメント修正の処理中プレビュー", en: "Comment revision in-progress preview" })
                    : t({ ja: "コメント修正の直前プレビュー", en: "Latest comment revision preview" })}
                </div>
                <div style={{ fontSize: "0.85rem", color: "var(--muted-text)", marginBottom: "0.4rem" }}>
                  {revisingByComment
                    ? t(
                        {
                          ja: "修正中です。進捗: {{completed}} / {{total}}",
                          en: "Revision in progress. Progress: {{completed}} / {{total}}",
                        },
                        {
                          completed: String(commentRevisionLiveProgress.completed || 0),
                          total: String(commentRevisionLiveProgress.total || 0),
                        }
                      )
                    : t({
                        ja: "修正完了後もしばらくこのプレビューを表示しています。",
                        en: "This preview stays visible for a short time after completion.",
                      })}
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--muted-text)", marginBottom: "0.4rem" }}>
                  {t({ ja: "プレビュー文字数", en: "Preview chars" })}: {countChars(commentRevisionLivePreviewBody)}
                </div>
                <pre
                  style={{
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    backgroundColor: "var(--ai-result-bg)",
                    padding: "0.6rem",
                    borderRadius: "6px",
                    border: "1px solid var(--border)",
                    maxHeight: "240px",
                    overflowY: "auto",
                    lineHeight: 1.6,
                  }}
                >
                  {commentRevisionLiveDiffSegments.map((seg: any, idx: any) => (
                    <span
                      key={`comment-live-diff-${idx}`}
                      style={seg.changed ? { color: liveCommentDiffColor, fontWeight: 700 } : undefined}
                    >
                      {seg.text}
                    </span>
                  ))}
                </pre>
              </div>
            )}
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
                    ja: "変更行は赤字で表示され、追加は「+」、削除は「-」で表示されます。",
                    en: "Changed lines are shown in red. Additions use '+' and deletions use '-'.",
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
                  {commentRevisionDiffSegments.map((seg: any, idx: any) => (
                    <span
                      key={`comment-diff-${idx}`}
                      style={seg.changed ? { color: committedCommentDiffColor, fontWeight: 700 } : undefined}
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
                    onChange={(e: any) => setPostEpisodeTitle(e.target.value)}
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
    {storyAgentVisible && (
    <div
      style={{
        position: "fixed",
        right: 20,
        bottom: 20,
        width: "min(360px, calc(100vw - 24px))",
        zIndex: 40,
        border: "1px solid var(--border)",
        borderRadius: 14,
        overflow: "hidden",
        backgroundColor: "#fffdf7",
        boxShadow: "0 18px 40px rgba(0, 0, 0, 0.18)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "0.75rem",
          padding: "0.8rem 0.9rem",
          background: "linear-gradient(135deg, #17324d 0%, #355e3b 100%)",
          color: "#fff",
        }}
      >
        <div>
          <div style={{ fontWeight: 700 }}>
            {t({ ja: "小説相談AI", en: "Novel Helper AI" })}
          </div>
          <div style={{ fontSize: "0.78rem", opacity: 0.88 }}>
            {t({ ja: "案を整理して設定欄へ追記", en: "Organize ideas and append to settings" })}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setStoryAgentOpen((prev) => !prev)}
          style={{
            border: "1px solid rgba(255,255,255,0.35)",
            background: "transparent",
            color: "#fff",
            borderRadius: 999,
            padding: "0.3rem 0.7rem",
            cursor: "pointer",
            fontSize: "0.8rem",
          }}
        >
          {storyAgentOpen
            ? t({ ja: "閉じる", en: "Minimize" })
            : t({ ja: "開く", en: "Open" })}
        </button>
      </div>

      {storyAgentOpen && (
        <div style={{ padding: "0.8rem", backgroundColor: "#fffdf7" }}>
          <div
            ref={storyAgentMessagesRef}
            style={{
              maxHeight: "320px",
              overflowY: "auto",
              display: "grid",
              gap: "0.65rem",
              paddingRight: "0.15rem",
            }}
          >
            {storyAgentMessages.map((item) => (
              <div
                key={item.id}
                style={{
                  alignSelf: item.role === "user" ? "end" : "start",
                  backgroundColor: item.role === "user" ? "#e7f0ff" : "#f4f0e8",
                  color: "#1f2937",
                  borderRadius: 12,
                  padding: "0.7rem 0.8rem",
                  border: "1px solid rgba(0,0,0,0.08)",
                }}
              >
                <div
                  style={{
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    marginBottom: "0.3rem",
                    color: item.role === "user" ? "#1d4ed8" : "#6b4f2a",
                  }}
                >
                  {item.role === "user"
                    ? t({ ja: "あなた", en: "You" })
                    : t({ ja: "AI", en: "AI" })}
                </div>
                <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: "0.92rem", lineHeight: 1.55 }}>
                  {item.content}
                </div>
                {item.appendedText && (
                  <div
                    style={{
                      marginTop: "0.55rem",
                      paddingTop: "0.55rem",
                      borderTop: "1px dashed rgba(0,0,0,0.12)",
                    }}
                  >
                    <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#355e3b", marginBottom: "0.25rem" }}>
                      {t({ ja: "登場人物・設定に追加", en: "Added to characters/settings" })}
                    </div>
                    <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: "0.84rem", color: "#355e3b" }}>
                      {item.appendedText}
                    </div>
                  </div>
                )}
                {(item.appliedTitleHint
                  || item.appliedGenre
                  || item.appliedTone
                  || typeof item.appliedIsR18 === "boolean"
                  || item.appliedModel
                  || typeof item.appliedChunkedGenerationEnabled === "boolean"
                  || typeof item.appliedChunkedGenerationCount === "number"
                  || (item.appliedChunkedGenerationPlans && item.appliedChunkedGenerationPlans.length > 0)) && (
                  <div
                    style={{
                      marginTop: "0.55rem",
                      paddingTop: "0.55rem",
                      borderTop: "1px dashed rgba(0,0,0,0.12)",
                    }}
                  >
                    <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#7c3f00", marginBottom: "0.3rem" }}>
                      {t({ ja: "反映した設定", en: "Applied settings" })}
                    </div>
                    <div style={{ display: "grid", gap: "0.25rem", fontSize: "0.84rem", color: "#7c3f00" }}>
                      {item.appliedTitleHint && (
                        <div>
                          <strong>{t({ ja: "タイトルのイメージ:", en: "Title idea:" })}</strong> {item.appliedTitleHint}
                        </div>
                      )}
                      {item.appliedGenre && (
                        <div>
                          <strong>{t({ ja: "ジャンル:", en: "Genre:" })}</strong> {item.appliedGenre}
                        </div>
                      )}
                      {item.appliedTone && (
                        <div>
                          <strong>{t({ ja: "雰囲気:", en: "Tone:" })}</strong> {item.appliedTone}
                        </div>
                      )}
                      {typeof item.appliedIsR18 === "boolean" && (
                        <div>
                          <strong>{t({ ja: "R18:", en: "R18:" })}</strong>{" "}
                          {item.appliedIsR18 ? t({ ja: "ON", en: "On" }) : t({ ja: "OFF", en: "Off" })}
                        </div>
                      )}
                      {item.appliedModel && (
                        <div>
                          <strong>{t({ ja: "使用モデル:", en: "Model:" })}</strong> {item.appliedModel}
                        </div>
                      )}
                      {typeof item.appliedChunkedGenerationEnabled === "boolean" && (
                        <div>
                          <strong>{t({ ja: "分割生成:", en: "Segmented generation:" })}</strong>{" "}
                          {item.appliedChunkedGenerationEnabled ? t({ ja: "ON", en: "On" }) : t({ ja: "OFF", en: "Off" })}
                        </div>
                      )}
                      {typeof item.appliedChunkedGenerationCount === "number" && (
                        <div>
                          <strong>{t({ ja: "分割数:", en: "Segments:" })}</strong> {item.appliedChunkedGenerationCount}
                        </div>
                      )}
                      {item.appliedChunkedGenerationPlans && item.appliedChunkedGenerationPlans.length > 0 && (
                        <div>
                          <strong>{t({ ja: "分割案:", en: "Segment plan:" })}</strong>
                          <div style={{ marginTop: "0.2rem", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                            {item.appliedChunkedGenerationPlans.map((plan, idx) => `${idx + 1}. ${plan}`).join("\n")}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
            {storyAgentLoading && (
              <div
                style={{
                  backgroundColor: "#f4f0e8",
                  borderRadius: 12,
                  padding: "0.7rem 0.8rem",
                  border: "1px solid rgba(0,0,0,0.08)",
                  fontSize: "0.9rem",
                  color: "#6b4f2a",
                }}
              >
                {t({ ja: "案をまとめています...", en: "Organizing ideas..." })}
              </div>
            )}
          </div>

          {storyAgentError && (
            <div style={{ marginTop: "0.65rem", color: "#842029", fontSize: "0.84rem" }}>
              {storyAgentError}
            </div>
          )}

          <div style={{ marginTop: "0.75rem", fontSize: "0.8rem", color: "var(--muted-text)" }}>
            {t({
              ja: "例: 小説案を書いてください / ヒロイン案を3つ出して / 学園ミステリの導入を考えて",
              en: "Examples: Give me a novel idea / Suggest 3 heroine ideas / Plan an opening for a school mystery",
            })}
          </div>

          <div style={{ display: "grid", gap: "0.55rem", marginTop: "0.65rem" }}>
            <textarea
              value={storyAgentInput}
              onChange={(e: any) => setStoryAgentInput(e.target.value)}
              onKeyDown={(e: any) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleStoryAgentSend();
                }
              }}
              rows={3}
              placeholder={t({
                ja: "小説案を書いてください。など、気軽に相談できます。",
                en: "Ask freely, for example: Please suggest a novel idea.",
              })}
              style={{
                width: "100%",
                padding: "0.7rem",
                resize: "vertical",
                borderRadius: 10,
                border: "1px solid var(--border)",
                backgroundColor: "#fff",
              }}
            />
            <button
              type="button"
              className="btn btn-border"
              onClick={handleStoryAgentSend}
              disabled={storyAgentLoading || !String(storyAgentInput || "").trim()}
            >
              {storyAgentLoading
                ? t({ ja: "相談中...", en: "Thinking..." })
                : t({ ja: "相談する", en: "Ask AI" })}
            </button>
          </div>
        </div>
      )}
    </div>
    )}
    </>
  );
}
