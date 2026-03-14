import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faPaperPlane } from "@fortawesome/free-regular-svg-icons";
import { useI18n } from "../lib/i18n";

const AI_CHAT_CHARACTER_NAME_KEY = "ai_chat_character_name_v1";
const AI_CHAT_PERSONALITY_KEY = "ai_chat_personality_v1";
const AI_CHAT_APPEARANCE_KEY = "ai_chat_appearance_v1";
const AI_CHAT_RELATIONSHIP_MEMO_HISTORY_KEY = "ai_chat_relationship_memo_history_v1";
const AI_CHAT_RELATIONSHIP_MEMO_HISTORY_LIMIT = 30;
const AI_CHAT_GUEST_DRAFT_KEY = "ai_chat_guest_draft_v1";
const AI_CHAT_GUEST_DRAFT_BACKUP_HASH_KEY = "ai_chat_guest_draft_backup_hash_v1";
const AI_CHAT_GUEST_DRAFT_BACKUP_BYTES_KEY = "ai_chat_guest_draft_backup_bytes_v1";
const AI_CHAT_GUEST_DRAFT_BACKUP_HASHES_KEY = "ai_chat_guest_draft_backup_hashes_v1";
const AI_CHAT_GUEST_DRAFT_LAST_DOWNLOAD_AT_KEY = "ai_chat_guest_draft_last_download_at_v1";
const AI_CHAT_GUEST_DRAFT_DOWNLOAD_INTERVAL_MS = 60 * 60 * 1000;
const AI_CHAT_SELECTED_CHARACTER_ID_KEY = "ai_chat_selected_character_id_v1";
const AI_CHAT_CHARACTER_DRAFT_PREFIX = "ai_chat_character_draft_v1:";
const MYPAGE_SHOW_CHATBOT_STORAGE_KEY = "mypage_show_chatbot";
const MYPAGE_SHOW_R18_STORAGE_KEY = "mypage_show_r18";
const AUTO_DIALOGUE_STOP_WORDS = ["停止", "止める", "ストップ", "stop"];
const PREVIEW_BUBBLE_COUNT = 3;
const APPEARANCE_SECTION_HEADER = "【見た目設定】";
const AI_CHAT_IMAGE_MESSAGE_PREFIX = "__AI_CHAT_IMAGE_MSG__:";
const DEFAULT_AI_CHAT_MODEL = "gpt-5-mini";
const DEMO02_AI_CHAT_MODEL = "google/gemini-3-flash-preview";
const MOBILE_VIEWPORT_MEDIA_QUERY = "(max-width: 768px)";
const RECOMMENDED_MODEL_VALUES = new Set([
  "moonshotai/kimi-k2",
  "google/gemini-3-pro-preview",
  "google/gemini-3-flash-preview",
]);
const ABSTRACT_IMAGE_PROMPT_WORDS = new Set([
  "優しい",
  "かわいい",
  "かっこいい",
  "美しい",
  "きれい",
  "綺麗",
  "すごい",
  "素敵",
  "幻想的",
  "神秘的",
  "エモい",
  "おしゃれ",
  "最高",
  "ドラマチック",
  "ロマンチック",
  "感動的",
  "抽象的",
  "雰囲気",
  "空気感",
  "mood",
  "emotional",
  "dramatic",
  "romantic",
  "beautiful",
  "pretty",
  "cute",
  "cool",
  "amazing",
  "awesome",
  "abstract",
  "感じ",
  "気持ち",
  "思い",
  "世界観",
  "関係性",
  "日常",
  "会話",
  "シーン",
  "描写",
  "空間",
  "印象",
  "表現",
  "quality",
  "masterpiece",
  "best",
  "vibe",
  "style",
  "scene",
  "feeling",
  "emotion",
  "story",
  "daily",
  "conversation",
]);

const AI_MODELS = [
  { value: "gpt-5.2", labelJa: "GPT-5.2（OpenAI）", labelEn: "GPT-5.2 (OpenAI)" },
  { value: "gpt-5", labelJa: "GPT-5（OpenAI）", labelEn: "GPT-5 (OpenAI)" },
  { value: "gpt-5-mini", labelJa: "GPT-5 mini（OpenAI）", labelEn: "GPT-5 mini (OpenAI)" },
  { value: "gpt-4.1-mini", labelJa: "GPT-4.1 mini（OpenAI）", labelEn: "GPT-4.1 mini (OpenAI)" },
  { value: "openai/chatgpt-4o-latest", labelJa: "ChatGPT（OpenRouter）", labelEn: "ChatGPT (OpenRouter)" },
  { value: "google/gemini-3-pro-preview", labelJa: "Gemini 3 Pro Preview（OpenRouter）", labelEn: "Gemini 3 Pro Preview (OpenRouter)" },
  { value: "google/gemini-3-flash-preview", labelJa: "Gemini 3 Flash Preview（OpenRouter）", labelEn: "Gemini 3 Flash Preview (OpenRouter)" },
  { value: "google/gemini-2.5-pro", labelJa: "Gemini 2.5 Pro（OpenRouter）", labelEn: "Gemini 2.5 Pro (OpenRouter)" },
  { value: "google/gemini-2.5-flash", labelJa: "Gemini 2.5 Flash（OpenRouter）", labelEn: "Gemini 2.5 Flash (OpenRouter)" },
  { value: "google/gemini-2.5-flash-lite", labelJa: "Gemini 2.5 Flash Lite（OpenRouter）", labelEn: "Gemini 2.5 Flash Lite (OpenRouter)" },
  { value: "z-ai/glm-4.6", labelJa: "GLM 4.6（OpenRouter）", labelEn: "GLM 4.6 (OpenRouter)" },
  { value: "moonshotai/kimi-k2", labelJa: "Kimi（OpenRouter）", labelEn: "Kimi (OpenRouter)" },
  { value: "moonshotai/kimi-k2-thinking", labelJa: "Kimi K2 Thinking（OpenRouter）", labelEn: "Kimi K2 Thinking (OpenRouter)" },
  { value: "deepseek/deepseek-chat", labelJa: "DeepSeek（OpenRouter）", labelEn: "DeepSeek (OpenRouter)" },
  { value: "deepseek/deepseek-reasoner", labelJa: "DeepSeek Reasoner（OpenRouter）", labelEn: "DeepSeek Reasoner (OpenRouter)" },
  { value: "deepseek:deepseek-chat", labelJa: "DeepSeek（公式）", labelEn: "DeepSeek (official)" },
  { value: "deepseek:deepseek-reasoner", labelJa: "DeepSeek Reasoner（公式）", labelEn: "DeepSeek Reasoner (official)" },
];

const GIRLFRIEND_PRESET_POOL = [
  {
    name: "一ノ瀬 ひより",
    personality: "やさしく包み込むタイプ。共感が早く、相手の気分を言語化して安心させる。",
    appearance: "黒髪ロング、淡い色のカーディガン、穏やかな笑顔",
    speech_gender: "female",
  },
  {
    name: "桜庭 みなみ",
    personality: "明るく前向き。会話のテンポが軽快で、背中を押すのが得意。",
    appearance: "茶髪ミディアム、白ブラウス、快活な表情",
    speech_gender: "female",
  },
  {
    name: "天城 しずく",
    personality: "落ち着いた知性派。丁寧に話を整理し、的確に提案する。",
    appearance: "暗めのボブ、ネイビーワンピース、知的な雰囲気",
    speech_gender: "female",
  },
];

const BOYFRIEND_PRESET_POOL = [
  {
    name: "神谷 蓮",
    personality: "頼れる保護者タイプ。相手の不安を受け止めつつ、行動に導く。",
    appearance: "黒髪ショート、ジャケット、落ち着いた眼差し",
    speech_gender: "male",
  },
  {
    name: "朝比奈 湊",
    personality: "フレンドリーで距離が近い。冗談を交えつつ元気づける。",
    appearance: "明るい茶髪、パーカー、柔らかな笑顔",
    speech_gender: "male",
  },
  {
    name: "白峰 朔",
    personality: "静かで誠実。必要な言葉を短く丁寧に返し、安心感を出す。",
    appearance: "ダークヘア、シャツスタイル、整った雰囲気",
    speech_gender: "male",
  },
];

function modelProvider(model) {
  if (!model) return "openai";
  if (model.startsWith("deepseek:")) return "deepseek";
  return model.includes("/") ? "openrouter" : "openai";
}

function randomPick(list) {
  const source = Array.isArray(list) ? list : [];
  if (!source.length) return null;
  const idx = Math.floor(Math.random() * source.length);
  return source[idx] || null;
}

function getAiChatPresetFromLocation(locationLike) {
  const pathname = String(locationLike?.pathname || "");
  if (pathname === "/ai_chat/girlfriend") return "girlfriend";
  if (pathname === "/ai_chat/boyfriend") return "boyfriend";
  const params = new URLSearchParams(String(locationLike?.search || ""));
  const preset = String(params.get("preset") || "").trim().toLowerCase();
  if (preset === "girlfriend" || preset === "boyfriend") return preset;
  return "";
}

function normalizeSpeakerName(name) {
  return String(name || "").trim();
}

function parseGeneratedImageMessageContent(rawContent) {
  const text = String(rawContent || "");
  if (!text.startsWith(AI_CHAT_IMAGE_MESSAGE_PREFIX)) return null;
  const rawJson = text.slice(AI_CHAT_IMAGE_MESSAGE_PREFIX.length).trim();
  if (!rawJson) return null;
  try {
    const parsed = JSON.parse(rawJson);
    const rawImages = Array.isArray(parsed?.images) ? parsed.images : [];
    const images = rawImages
      .map((img) => {
        if (!img || typeof img !== "object") return null;
        const url = String(img.url || "").trim();
        if (!url) return null;
        return {
          url,
          filename: String(img.filename || "").trim(),
        };
      })
      .filter(Boolean);
    if (!images.length) return null;
    const kind = String(parsed?.kind || "generated_images").trim() || "generated_images";
    const rawDescriptions = Array.isArray(parsed?.meta?.descriptions) ? parsed.meta.descriptions : [];
    const descriptions = rawDescriptions
      .map((d) => String(d || "").trim())
      .filter(Boolean);
    return {
      images,
      prompt: String(parsed?.prompt || "").trim(),
      kind,
      descriptions,
    };
  } catch {
    return null;
  }
}

function compactText(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
}

function normalizeRelationshipMemoHistory(raw) {
  if (!Array.isArray(raw)) return [];
  const now = Date.now();
  const normalized = [];
  const seen = new Set();
  raw.forEach((item, idx) => {
    const isObject = item && typeof item === "object";
    const text = compactText(isObject ? item.text : item);
    if (!text) return;
    const key = text.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    const useCountRaw = isObject ? Number(item.use_count) : NaN;
    const lastUsedRaw = isObject ? Number(item.last_used_at) : NaN;
    normalized.push({
      text,
      use_count: Number.isFinite(useCountRaw) && useCountRaw > 0 ? Math.floor(useCountRaw) : 1,
      last_used_at: Number.isFinite(lastUsedRaw) && lastUsedRaw > 0 ? Math.floor(lastUsedRaw) : now - idx,
    });
  });
  return normalized
    .sort((a, b) => {
      if (b.use_count !== a.use_count) return b.use_count - a.use_count;
      return b.last_used_at - a.last_used_at;
    })
    .slice(0, AI_CHAT_RELATIONSHIP_MEMO_HISTORY_LIMIT);
}

function normalizeChatFetchErrorMessage(error, fallbackMessage, t) {
  const msg = String(error?.message || "").trim();
  if (!msg) return fallbackMessage;
  const lowered = msg.toLowerCase();
  if (error?.name === "AbortError" || lowered === "failed to fetch") {
    return t({
      ja: "通信が不安定なためリクエストに失敗しました。時間をおいて再試行してください。",
      en: "Request failed due to unstable network. Please retry in a moment.",
    });
  }
  return msg;
}

function isNetworkFetchError(error) {
  if (!error) return false;
  if (error?.name === "AbortError") return false;
  const msg = String(error?.message || "").trim().toLowerCase();
  return msg === "failed to fetch";
}

function resolveImageUrl(rawUrl) {
  const src = String(rawUrl || "").trim();
  if (!src) return "";
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:image/")) {
    return src;
  }
  if (src.startsWith("/")) return src;
  return `/${src}`;
}

function calcChatMessagesBytes(messages) {
  try {
    const text = JSON.stringify(Array.isArray(messages) ? messages : []);
    return new TextEncoder().encode(String(text || "")).length;
  } catch {
    return 0;
  }
}

async function fetchWithSingleRetry(url, options, retryDelayMs = 350) {
  try {
    return await fetch(url, options);
  } catch (error) {
    if (!isNetworkFetchError(error)) throw error;
    await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
    return fetch(url, options);
  }
}

function sanitizeImagePromptSourceText(text) {
  return compactText(text);
}

function extractConcreteImagePromptWords(text, limit = 8) {
  const source = sanitizeImagePromptSourceText(text)
    .replace(/[|/]/g, " ")
    .replace(/[、。！？!?;:()[\]{}"“”'`]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!source) return [];
  const chunks = source.match(/[A-Za-z0-9][A-Za-z0-9_-]{1,}|[一-龥ぁ-んァ-ヴー]{2,}/g) || [];
  const picked = [];
  const seen = new Set();
  const blocked = new Set([
    "する",
    "した",
    "して",
    "いる",
    "なる",
    "ある",
    "いる",
    "こと",
    "もの",
    "それ",
    "これ",
    "あれ",
    "よう",
    "です",
    "ます",
    "with",
    "from",
    "into",
    "about",
    "very",
    "really",
    "just",
    "like",
    "look",
    "looks",
    "feel",
    "feels",
  ]);
  for (const chunk of chunks) {
    const token = String(chunk || "").trim();
    if (!token) continue;
    const lower = token.toLowerCase();
    if (ABSTRACT_IMAGE_PROMPT_WORDS.has(token) || ABSTRACT_IMAGE_PROMPT_WORDS.has(lower)) continue;
    if (blocked.has(token) || blocked.has(lower)) continue;
    if (/^[0-9]+$/.test(token)) continue;
    if (/^(this|that|these|those|they|them|you|your|our|their)$/i.test(token)) continue;
    if (/[ぁ-ん一-龥]/.test(token) && /(的|感|性|らしさ)$/.test(token)) continue;
    if (token.length > 24) continue;
    if (seen.has(lower)) continue;
    seen.add(lower);
    picked.push(token);
    if (picked.length >= limit) break;
  }
  return picked;
}

function uniqueTokens(tokens, limit = 12) {
  const picked = [];
  const seen = new Set();
  for (const raw of tokens || []) {
    const token = compactText(raw);
    if (!token) continue;
    const key = token.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    picked.push(token);
    if (picked.length >= limit) break;
  }
  return picked;
}

function splitPersonalityAndAppearance(rawText) {
  const text = String(rawText || "").trim();
  if (!text) return { personalityText: "", appearanceText: "" };
  const idx = text.indexOf(APPEARANCE_SECTION_HEADER);
  if (idx < 0) return { personalityText: text, appearanceText: "" };
  const personalityText = text.slice(0, idx).trim();
  const appearanceText = text.slice(idx + APPEARANCE_SECTION_HEADER.length).trim();
  return { personalityText, appearanceText };
}

function mergePersonalityWithAppearance(personalityText, appearanceText) {
  const base = String(personalityText || "").trim();
  const appearance = String(appearanceText || "").trim();
  if (!appearance) return base;
  if (!base) return `${APPEARANCE_SECTION_HEADER}\n${appearance}`;
  return `${base}\n\n${APPEARANCE_SECTION_HEADER}\n${appearance}`;
}

function hashStringSeed(text) {
  const s = String(text || "");
  let h = 0;
  for (let i = 0; i < s.length; i += 1) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function pickBySeed(items, seed, offset = 0) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return "";
  const idx = Math.abs((seed + offset) % list.length);
  return String(list[idx] || "");
}

function buildRandomAppearanceText(name, speechGender = "auto") {
  const seed = hashStringSeed(`${name || "character"}::${speechGender || "auto"}`);
  const hairColors = ["black hair", "brown hair", "silver hair", "blonde hair", "navy hair"];
  const hairStyles = ["short hair", "bob cut", "long hair", "ponytail", "twin tails"];
  const eyes = ["blue eyes", "amber eyes", "green eyes", "violet eyes", "dark brown eyes"];
  const outfits = [
    "school uniform", "blazer and shirt", "hoodie and jeans", "long coat", "white shirt and slacks",
  ];
  const body = speechGender === "female"
    ? "slim build"
    : (speechGender === "male" ? "lean athletic build" : "balanced build");
  return uniqueTokens([
    pickBySeed(hairColors, seed, 3),
    pickBySeed(hairStyles, seed, 7),
    pickBySeed(eyes, seed, 11),
    pickBySeed(outfits, seed, 17),
    body,
    "clean face",
  ], 6).join(", ");
}

function deriveFanficAppearanceFromSources(characterName, sources, fallback = "") {
  const joined = (Array.isArray(sources) ? sources : [])
    .slice(0, 8)
    .map((s) => `${String(s?.title || "")} ${String(s?.snippet || "")}`)
    .join(" ");
  const text = `${characterName || ""} ${joined}`.toLowerCase();
  const keywords = [
    "black hair", "brown hair", "blonde hair", "silver hair", "pink hair", "blue hair",
    "short hair", "long hair", "ponytail", "twin tail", "ahoge",
    "blue eyes", "red eyes", "green eyes", "gold eyes", "violet eyes",
    "school uniform", "suit", "coat", "dress", "kimono", "armor", "cloak",
    "制服", "黒髪", "茶髪", "金髪", "銀髪", "青髪", "ピンク髪",
    "短髪", "長髪", "ポニーテール", "ツインテール",
    "青い目", "赤い目", "緑の目", "金色の目", "紫の目",
    "ブレザー", "シャツ", "コート", "ワンピース", "着物", "鎧",
  ];
  const matched = uniqueTokens(keywords.filter((k) => text.includes(String(k).toLowerCase())), 8);
  if (matched.length) return matched.join(", ");
  return String(fallback || "").trim();
}

function normalizeSpeechGender(value) {
  const v = String(value || "").trim().toLowerCase();
  if (v === "female" || v === "male") return v;
  return "auto";
}

function truncateText(text, max = 56) {
  const normalized = compactText(text);
  if (!normalized) return "";
  if (normalized.length <= max) return normalized;
  return `${normalized.slice(0, max)}…`;
}

function normalizeStoredToken(raw) {
  let token = String(raw || "").trim();
  if (!token) return "";
  if (
    (token.startsWith("\"") && token.endsWith("\"")) ||
    (token.startsWith("'") && token.endsWith("'"))
  ) {
    token = token.slice(1, -1).trim();
  }
  if (!token) return "";
  const lower = token.toLowerCase();
  if (lower === "null" || lower === "undefined") return "";
  return token;
}

function getStoredAuthToken() {
  if (typeof window === "undefined") return null;
  const primary = normalizeStoredToken(localStorage.getItem("access_token"));
  const fallback = normalizeStoredToken(localStorage.getItem("token"));
  const candidates = [primary, fallback].filter(Boolean);
  if (!candidates.length) return null;
  const jwtLike = candidates.find((v) => v.split(".").length === 3);
  return jwtLike || candidates[0];
}

function loadGuestChatDraft() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(AI_CHAT_GUEST_DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    return parsed;
  } catch {
    return null;
  }
}

function buildCharacterDraftStorageKey(characterId) {
  const id = String(characterId || "").trim();
  if (!id) return "";
  return `${AI_CHAT_CHARACTER_DRAFT_PREFIX}${id}`;
}

function loadCharacterChatDraft(characterId) {
  if (typeof window === "undefined") return null;
  const key = buildCharacterDraftStorageKey(characterId);
  if (!key) return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    return parsed;
  } catch {
    return null;
  }
}

function hashGuestDraftText(text) {
  const raw = String(text || "");
  if (!raw) return "";
  // FNV-1a 32-bit hash for lightweight duplicate detection in browser.
  let hash = 0x811c9dc5;
  for (let i = 0; i < raw.length; i += 1) {
    hash ^= raw.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function getByteLengthUtf8(text) {
  try {
    if (typeof TextEncoder !== "undefined") {
      return new TextEncoder().encode(String(text || "")).length;
    }
  } catch {
    // fallback below
  }
  return unescape(encodeURIComponent(String(text || ""))).length;
}

function downloadGuestChatDraftJson(draft, rawText = "") {
  if (typeof window === "undefined" || typeof document === "undefined") return false;
  try {
    const payload = typeof rawText === "string" && rawText.trim()
      ? rawText
      : JSON.stringify(draft || {}, null, 2);
    if (!payload) return false;
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const characterPart = String(draft?.character_name || "guest")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "_")
      .slice(0, 40);
    const filename = `ai-chat-guest-backup-${characterPart || "guest"}-${stamp}.json`;
    const blob = new Blob([payload], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return true;
  } catch {
    return false;
  }
}

function shouldBackupGuestDraft(rawText, options = {}) {
  if (typeof window === "undefined") return { shouldBackup: false, hash: "" };
  const force = !!options?.force;
  const nextHash = hashGuestDraftText(rawText);
  const nextBytes = getByteLengthUtf8(rawText);
  if (!nextHash) return { shouldBackup: false, hash: "" };
  const prevHash = String(localStorage.getItem(AI_CHAT_GUEST_DRAFT_BACKUP_HASH_KEY) || "").trim();
  const prevBytes = Number(localStorage.getItem(AI_CHAT_GUEST_DRAFT_BACKUP_BYTES_KEY) || 0);
  const savedHashListRaw = localStorage.getItem(AI_CHAT_GUEST_DRAFT_BACKUP_HASHES_KEY);
  let savedHashList = [];
  try {
    const parsed = JSON.parse(savedHashListRaw || "[]");
    savedHashList = Array.isArray(parsed) ? parsed.map((v) => String(v || "").trim()).filter(Boolean) : [];
  } catch {
    savedHashList = [];
  }
  const hashAlreadySaved = savedHashList.includes(nextHash);
  const isNewerByBytes = nextBytes > prevBytes;
  return {
    shouldBackup: force || (!hashAlreadySaved && (prevHash !== nextHash || isNewerByBytes)),
    hash: nextHash,
    bytes: nextBytes,
  };
}

function markGuestDraftBackedUp(hash, bytes = 0) {
  if (typeof window === "undefined") return;
  if (!hash) return;
  localStorage.setItem(AI_CHAT_GUEST_DRAFT_BACKUP_HASH_KEY, String(hash));
  let savedHashList = [];
  try {
    const parsed = JSON.parse(localStorage.getItem(AI_CHAT_GUEST_DRAFT_BACKUP_HASHES_KEY) || "[]");
    savedHashList = Array.isArray(parsed) ? parsed.map((v) => String(v || "").trim()).filter(Boolean) : [];
  } catch {
    savedHashList = [];
  }
  if (!savedHashList.includes(hash)) {
    savedHashList.push(hash);
    localStorage.setItem(
      AI_CHAT_GUEST_DRAFT_BACKUP_HASHES_KEY,
      JSON.stringify(savedHashList.slice(-80))
    );
  }
  if (Number.isFinite(Number(bytes)) && Number(bytes) > 0) {
    localStorage.setItem(AI_CHAT_GUEST_DRAFT_BACKUP_BYTES_KEY, String(Number(bytes)));
  }
}

function shouldBackupGuestDraftByInterval(nowMs = Date.now()) {
  if (typeof window === "undefined") return false;
  const lastRaw = localStorage.getItem(AI_CHAT_GUEST_DRAFT_LAST_DOWNLOAD_AT_KEY);
  const last = Number(lastRaw || 0);
  if (!Number.isFinite(last) || last <= 0) return true;
  return (nowMs - last) >= AI_CHAT_GUEST_DRAFT_DOWNLOAD_INTERVAL_MS;
}

function markGuestDraftDownloadTime(nowMs = Date.now()) {
  if (typeof window === "undefined") return;
  localStorage.setItem(AI_CHAT_GUEST_DRAFT_LAST_DOWNLOAD_AT_KEY, String(nowMs));
}

function messageDiffSignature(m) {
  const role = m?.role === "assistant" ? "assistant" : "user";
  const mode = m?.mode === "do" ? "do" : "say";
  const autoFlag = m?.is_auto_dialogue ? "1" : "0";
  const content = String(m?.content || "").trim().slice(0, 4000);
  return `${role}\t${mode}\t${autoFlag}\t${content}`;
}

function extractAppendOnlyDiffMessages(sourceMessages, existingMessages) {
  const src = Array.isArray(sourceMessages) ? sourceMessages : [];
  const existing = Array.isArray(existingMessages) ? existingMessages : [];
  const srcSig = src.map((m) => messageDiffSignature(m));
  const existingSig = existing.map((m) => messageDiffSignature(m));
  let matched = 0;
  while (
    matched < srcSig.length
    && matched < existingSig.length
    && srcSig[matched] === existingSig[matched]
  ) {
    matched += 1;
  }
  if (matched >= src.length) return [];
  return src.slice(matched);
}

function normalizeStoredGuestMessage(raw) {
  if (!raw || typeof raw !== "object") return null;
  const role = raw.role === "assistant" ? "assistant" : "user";
  const mode = raw.mode === "do" ? "do" : "say";
  const content = String(raw.content || "");
  const generatedImages = Array.isArray(raw.generated_images)
    ? raw.generated_images
        .map((img) => {
          if (!img || typeof img !== "object") return null;
          const url = String(img.url || "").trim();
          if (!url) return null;
          const filename = String(img.filename || "").trim();
          return { url, ...(filename ? { filename } : {}) };
        })
        .filter(Boolean)
    : [];
  const imageDescriptions = Array.isArray(raw.image_descriptions)
    ? raw.image_descriptions.map((d) => String(d || "").trim()).filter(Boolean)
    : [];
  return {
    id: null,
    role,
    mode,
    is_auto_dialogue: !!raw.is_auto_dialogue,
    content,
    speaker_name: String(raw.speaker_name || ""),
    model_name: String(raw.model_name || "").trim(),
    is_generated_image: !!raw.is_generated_image,
    image_message_kind: raw.image_message_kind === "uploaded_images" ? "uploaded_images" : "generated_images",
    generated_images: generatedImages,
    image_descriptions: imageDescriptions,
  };
}

function buildGuestImportMessages(rawMessages) {
  const list = Array.isArray(rawMessages) ? rawMessages : [];
  return list
    .map((m) => {
      const role = m?.role === "assistant" ? "assistant" : "user";
      const mode = m?.mode === "do" ? "do" : "say";
      let content = String(m?.content || "").trim();
      if (
        m?.is_generated_image
        && m?.image_message_kind === "uploaded_images"
        && Array.isArray(m?.image_descriptions)
        && m.image_descriptions.length > 0
      ) {
        content = `【ユーザー添付画像の説明】\n${m.image_descriptions.map((d, i) => `${i + 1}. ${String(d || "").trim()}`).filter(Boolean).join("\n")}`;
      }
      if (!content) return null;
      return {
        role,
        mode,
        is_auto_dialogue: !!m?.is_auto_dialogue && role === "assistant",
        content: content.slice(0, 4000),
      };
    })
    .filter(Boolean)
    .slice(-300);
}

function isDemo02UserLocal() {
  if (typeof window === "undefined") return false;
  return String(localStorage.getItem("username") || "").trim().toLowerCase() === "demo02";
}

export default function AiChatPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const [model, setModel] = useState(() =>
    isDemo02UserLocal() ? DEMO02_AI_CHAT_MODEL : DEFAULT_AI_CHAT_MODEL
  );
  const [recommendedModelsOnly, setRecommendedModelsOnly] = useState(() => isDemo02UserLocal());
  const [characterName, setCharacterName] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem(AI_CHAT_CHARACTER_NAME_KEY) || "";
  });
  const [personality, setPersonality] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem(AI_CHAT_PERSONALITY_KEY) || "";
  });
  const [appearance, setAppearance] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem(AI_CHAT_APPEARANCE_KEY) || "";
  });
  const [mainSpeechGender, setMainSpeechGender] = useState("auto");
  const [mode, setMode] = useState("say");
  const [autoDialogue, setAutoDialogue] = useState(false);
  const [longReply, setLongReply] = useState(false);
  const [shortReply, setShortReply] = useState(() => isDemo02UserLocal());
  const [dailyTalkMode, setDailyTalkMode] = useState(false);
  const [iq80CrudeMode, setIq80CrudeMode] = useState(() => isDemo02UserLocal());
  const [r18Mode, setR18Mode] = useState(() => isDemo02UserLocal());
  const [showR18ByDisplaySetting] = useState(() => {
    if (typeof window === "undefined") return true;
    const v = localStorage.getItem(MYPAGE_SHOW_R18_STORAGE_KEY);
    if (v === null) return true;
    return v === "1" || v === "true";
  });
  const [showChatbotByDisplaySetting] = useState(() => {
    if (typeof window === "undefined") return false;
    const v = localStorage.getItem(MYPAGE_SHOW_CHATBOT_STORAGE_KEY);
    if (v === null) return false; // default: unchecked
    return v === "1" || v === "true";
  });
  const [fanficMode, setFanficMode] = useState(false);
  const [augmentLoading, setAugmentLoading] = useState(false);
  const [augmentNotes, setAugmentNotes] = useState("");
  const [castCharacters, setCastCharacters] = useState([]);
  const [userSpeakerKey, setUserSpeakerKey] = useState("you");
  const [randomSpeakerKeys, setRandomSpeakerKeys] = useState(["main"]);
  const [autoCharacterMode, setAutoCharacterMode] = useState(false);
  const [autoRandomSpeakerKeys, setAutoRandomSpeakerKeys] = useState(["main"]);
  const [input, setInput] = useState("");
  const [selectedCharacterId, setSelectedCharacterId] = useState(() => {
    if (typeof window === "undefined") return "";
    return String(localStorage.getItem(AI_CHAT_SELECTED_CHARACTER_ID_KEY) || "").trim();
  });
  const [messages, setMessages] = useState(() => {
    if (typeof window !== "undefined") {
      const token = getStoredAuthToken();
      const selectedId = String(localStorage.getItem(AI_CHAT_SELECTED_CHARACTER_ID_KEY) || "").trim();
      if (token && selectedId) {
        const draft = loadCharacterChatDraft(selectedId);
        const raw = Array.isArray(draft?.messages) ? draft.messages : [];
        const restored = raw.map(normalizeStoredGuestMessage).filter(Boolean).slice(-300);
        if (restored.length) return restored;
      }
    }
    const draft = loadGuestChatDraft();
    const raw = Array.isArray(draft?.messages) ? draft.messages : [];
    return raw.map(normalizeStoredGuestMessage).filter(Boolean).slice(-200);
  });
  const [selectedMessageIndex, setSelectedMessageIndex] = useState(null);
  const [selectedGeneratedImageKey, setSelectedGeneratedImageKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [autoContinuing, setAutoContinuing] = useState(false);
  const [error, setError] = useState("");
  const [isResending, setIsResending] = useState(false);
  const [creatingNovelFromChat, setCreatingNovelFromChat] = useState(false);
  const [lastRequest, setLastRequest] = useState(null);
  const [resendDraft, setResendDraft] = useState("");
  const [resendMode, setResendMode] = useState("say");
  const [savedCharacters, setSavedCharacters] = useState([]);
  const [characterImageFile, setCharacterImageFile] = useState(null);
  const [characterImageUploading, setCharacterImageUploading] = useState(false);
  const [charactersLoading, setCharactersLoading] = useState(false);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [chatAccess, setChatAccess] = useState(null);
  const [engagementSummary, setEngagementSummary] = useState(null);
  const [engagementLoading, setEngagementLoading] = useState(false);
  const [addonCheckoutLoading, setAddonCheckoutLoading] = useState(false);
  const [latestPromptPreview, setLatestPromptPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [nextLineSuggestions, setNextLineSuggestions] = useState([]);
  const [nextLineLoading, setNextLineLoading] = useState(false);
  const [selectedAnimeTitle, setSelectedAnimeTitle] = useState("");
  const [animeTitleDialogOpen, setAnimeTitleDialogOpen] = useState(false);
  const [animeTitleLoading, setAnimeTitleLoading] = useState(false);
  const [animeTitleCandidates, setAnimeTitleCandidates] = useState([]);
  const [animeTitleCandidateName, setAnimeTitleCandidateName] = useState("");
  const [animeTitleDraft, setAnimeTitleDraft] = useState("");
  const [imagePromptDraft, setImagePromptDraft] = useState("");
  const [imageNegativePromptDraft, setImageNegativePromptDraft] = useState("");
  const [imageGenerating, setImageGenerating] = useState(false);
  const [chatImageFiles, setChatImageFiles] = useState([]);
  const [chatImageUploading, setChatImageUploading] = useState(false);
  const [authToken, setAuthToken] = useState(() => getStoredAuthToken() || "");
  const [guestMigrationRunning, setGuestMigrationRunning] = useState(false);
  const [guestMigrationInfo, setGuestMigrationInfo] = useState("");
  const [saveNameConflict, setSaveNameConflict] = useState(null);
  const [relationshipMemoHistory, setRelationshipMemoHistory] = useState(() => {
    if (typeof window === "undefined") return [];
    try {
      const raw = localStorage.getItem(AI_CHAT_RELATIONSHIP_MEMO_HISTORY_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return normalizeRelationshipMemoHistory(parsed);
    } catch {
      return [];
    }
  });
  const [castRelationshipSelectMap, setCastRelationshipSelectMap] = useState({});
  const [isMobileViewport, setIsMobileViewport] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia(MOBILE_VIEWPORT_MEDIA_QUERY).matches;
  });
  const fanficCacheRef = useRef(new Map());
  const lastImportedPublicCharacterKeyRef = useRef("");
  const lastAppliedEntryPresetRef = useRef("");
  const guestMigrationStartedRef = useRef(false);
  const guestDraftBackupDoneRef = useRef(false);
  const chatImageInputRef = useRef(null);
  const autoSaveTimerRef = useRef(null);
  const lastAutoSavedSignatureRef = useRef("");
  const visibleAiModels = useMemo(
    () => (recommendedModelsOnly ? AI_MODELS.filter((m) => RECOMMENDED_MODEL_VALUES.has(m.value)) : AI_MODELS),
    [recommendedModelsOnly]
  );
  const activeModel = useMemo(() => {
    if (visibleAiModels.some((m) => m.value === model)) return model;
    return visibleAiModels[0]?.value || DEFAULT_AI_CHAT_MODEL;
  }, [visibleAiModels, model]);
  const mapApiCharacter = (raw) => {
    const split = splitPersonalityAndAppearance(String(raw?.personality || ""));
    return {
      id: String(raw?.id),
      name: String(raw?.name || "").trim(),
      personality: split.personalityText,
      appearance: split.appearanceText,
      image_url: String(raw?.image_url || "").trim(),
      speech_gender: normalizeSpeechGender(raw?.speech_gender),
      owner_username: String(raw?.owner_username || "").trim(),
      is_readonly: !!raw?.is_readonly,
      is_public: !!raw?.is_public,
      is_r18: !!raw?.is_r18,
      recommendation_score: Number(raw?.recommendation_score || 0),
      recommendation_samples: Number(raw?.recommendation_samples || 0),
      is_recommended: !!raw?.is_recommended,
      is_name_duplicate: !!raw?.is_name_duplicate,
      name_duplicate_index: Number(raw?.name_duplicate_index || 1),
      published_at: raw?.published_at || null,
      updated_at: raw?.updated_at || null,
    };
  };
  const formatCharacterNameWithIndex = (c) => {
    const name = String(c?.name || "").trim();
    const idx = Math.max(1, Number(c?.name_duplicate_index || 1));
    if (!name) return "";
    if (c?.is_name_duplicate) return `${name} #${idx}`;
    return name;
  };

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const media = window.matchMedia(MOBILE_VIEWPORT_MEDIA_QUERY);
    const onChange = (event) => setIsMobileViewport(event.matches);
    setIsMobileViewport(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    if (!visibleAiModels.length) return;
    const modelExists = visibleAiModels.some((m) => m.value === model);
    if (!modelExists) {
      setModel(visibleAiModels[0].value);
    }
  }, [visibleAiModels, model]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const syncAuthToken = () => setAuthToken(getStoredAuthToken() || "");
    syncAuthToken();
    window.addEventListener("focus", syncAuthToken);
    window.addEventListener("storage", syncAuthToken);
    const timer = window.setInterval(syncAuthToken, 1500);
    return () => {
      window.removeEventListener("focus", syncAuthToken);
      window.removeEventListener("storage", syncAuthToken);
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!isDemo02UserLocal()) return;
    setRecommendedModelsOnly(true);
    setModel(DEMO02_AI_CHAT_MODEL);
  }, [authToken]);

  useEffect(() => {
    const preset = getAiChatPresetFromLocation(location);
    if (!preset) return;
    const presetStamp = `${preset}|${location.pathname}|${location.search}`;
    if (lastAppliedEntryPresetRef.current === presetStamp) return;
    const picked =
      preset === "girlfriend"
        ? randomPick(GIRLFRIEND_PRESET_POOL)
        : randomPick(BOYFRIEND_PRESET_POOL);
    if (!picked) return;
    lastAppliedEntryPresetRef.current = presetStamp;
    setSelectedCharacterId("");
    setCharacterImageFile(null);
    setCharacterName(String(picked.name || ""));
    setPersonality(String(picked.personality || ""));
    setAppearance(String(picked.appearance || ""));
    setMainSpeechGender(normalizeSpeechGender(picked.speech_gender));
    setFanficMode(false);
    setSelectedAnimeTitle("");
    setMessages([]);
    setLastRequest(null);
    setResendDraft("");
    setLatestPromptPreview(null);
    setError("");
  }, [location.pathname, location.search]);

  const normalizeAiNovelResponse = (data) => {
    if (!data || typeof data !== "object") return data;
    const rawBody = String(data?.body || "").trim();
    if (!rawBody) return data;
    const rawTitle = String(data?.generated_title || "").trim();
    if (rawBody.startsWith("{") && rawBody.endsWith("}")) {
      try {
        const parsed = JSON.parse(rawBody);
        return {
          ...data,
          generated_title: String(
            rawTitle || parsed?.generated_title || parsed?.title || ""
          ).trim(),
          body: String(parsed?.body || parsed?.content || rawBody),
        };
      } catch {
        return data;
      }
    }
    return data;
  };

  const buildConversationTimelineForNovel = () => {
    const list = Array.isArray(messages) ? messages : [];
    if (!list.length) return [];

    const normalized = list
      .filter((m) => m?.role === "user" || m?.role === "assistant")
      .map((m) => {
        const role = m.role === "assistant" ? "assistant" : "user";
        const mode = m.mode === "do" ? "do" : "say";
        const speaker = String(m.speaker_name || "").trim();
        const content = String(m.content || "").trim();
        return { role, mode, speaker, content };
      })
      .filter((m) => m.content);

    const firstUserIndex = normalized.findIndex((m) => m.role === "user");
    if (firstUserIndex < 0) return [];
    return normalized.slice(firstUserIndex);
  };

  const buildScenePromptFromCurrentChat = () => {
    const mainName = compactText(characterName) || t({ ja: "メインキャラ", en: "Main character" });
    const sceneCasts = castCharacters.slice(0, 4);
    const effectiveMainAppearance = compactText(appearance)
      || (fanficMode ? "" : buildRandomAppearanceText(mainName, mainSpeechGender));
    if (!compactText(appearance) && effectiveMainAppearance) {
      setAppearance(effectiveMainAppearance);
    }
    const normalizePromptTokens = (value, fallback = "", limit = 8) => {
      const primary = extractConcreteImagePromptWords(value, limit);
      if (primary.length) return primary;
      return extractConcreteImagePromptWords(fallback, limit);
    };
    const countTag = (count, singular, plural) => {
      if (count <= 0) return "";
      if (count === 1) return `1${singular}`;
      return `${count}${plural}`;
    };

    const recent = (Array.isArray(messages) ? messages : [])
      .map((m) => ({ ...m, content: sanitizeImagePromptSourceText(m?.content || "") }))
      .filter((m) => compactText(m?.content))
      .slice(-14);
    const recentDoMessages = recent.filter((m) => m.mode === "do");
    const recentDoText = sanitizeImagePromptSourceText(
      recentDoMessages.map((m) => String(m?.content || "")).join(" ")
    );
    const latestDo = [...recent].reverse().find((m) => m.mode === "do" && compactText(m.content));
    const pickByKeywords = (text, candidates, limit = 5) => {
      const src = String(text || "").toLowerCase();
      if (!src) return [];
      return uniqueTokens(
        candidates.filter((kw) => src.includes(String(kw || "").toLowerCase())),
        limit
      );
    };
    const locationCandidates = [
      "classroom", "school", "hallway", "library", "rooftop", "station", "train", "park",
      "cafe", "restaurant", "street", "office", "home", "bedroom", "living room", "kitchen",
      "beach", "sea", "mountain", "forest", "river", "temple",
      "教室", "学校", "廊下", "図書室", "屋上", "駅", "電車", "公園", "カフェ", "喫茶店", "通学路",
      "道", "オフィス", "職場", "部屋", "自室", "リビング", "キッチン", "海", "浜辺", "山", "森", "神社",
    ];
    const outfitCandidates = [
      "school uniform", "blazer", "shirt", "jacket", "hoodie", "coat", "dress", "skirt",
      "pants", "jeans", "suit", "kimono", "armor", "swimsuit", "apron", "glasses",
      "制服", "ブレザー", "シャツ", "ジャケット", "パーカー", "コート", "ワンピース", "スカート",
      "ズボン", "ジーンズ", "スーツ", "和服", "着物", "鎧", "水着", "エプロン", "眼鏡", "メガネ",
    ];
    const locationTokens = pickByKeywords(recentDoText, locationCandidates, 5);
    const outfitTokens = uniqueTokens([
      ...pickByKeywords(recentDoText, outfitCandidates, 6),
      ...pickByKeywords(effectiveMainAppearance, outfitCandidates, 4),
      ...sceneCasts.flatMap((cast) => {
        const castAppearance = compactText(cast?.appearance)
          || (cast?.fanfic_mode ? "" : buildRandomAppearanceText(cast?.name, cast?.speech_gender));
        return pickByKeywords(castAppearance || cast?.personality, outfitCandidates, 3);
      }),
    ], 6);
    const actionTokens = normalizePromptTokens(
      latestDo?.content || "",
      t({ ja: "歩く, 立つ, 見つめる, 手を伸ばす", en: "standing, walking, eye contact, reaching hand" }),
      8
    );
    const detailTokens = uniqueTokens([
      ...normalizePromptTokens(latestDo?.content || "", "", 6),
      ...normalizePromptTokens(recentDoText, "", 6),
    ], 10);
    const participantGenders = [
      normalizeSpeechGender(mainSpeechGender),
      ...sceneCasts.map((cast) => normalizeSpeechGender(cast?.speech_gender)),
    ];
    const girlCount = participantGenders.filter((g) => g === "female").length;
    const boyCount = participantGenders.filter((g) => g === "male").length;
    const unknownCount = Math.max(0, participantGenders.length - girlCount - boyCount);
    const peopleCountTags = [
      countTag(girlCount, "girl", "girls"),
      countTag(boyCount, "boy", "boys"),
      countTag(unknownCount, "person", "people"),
    ].filter(Boolean);
    const participantNames = uniqueTokens([
      mainName,
      ...recent
        .map((m) => compactText(m?.speaker_name))
        .filter(Boolean)
        .slice(-4),
      ...sceneCasts.map((cast, idx) => compactText(cast?.name) || t({ ja: `サブキャラ${idx + 1}`, en: `Sub character ${idx + 1}` })),
    ], 3);
    const companions = participantNames.slice(1, 3);
    const mainLookTokens = normalizePromptTokens(
      effectiveMainAppearance || personality,
      t({ ja: "制服, 黒髪, 前髪, 青い目", en: "school uniform, black hair, bangs, blue eyes" }),
      6
    );
    const castLookTokens = uniqueTokens(
      sceneCasts.flatMap((cast) =>
        normalizePromptTokens(
          compactText(cast?.appearance)
            || (cast?.fanfic_mode ? "" : buildRandomAppearanceText(cast?.name, cast?.speech_gender))
            || cast?.personality,
          t({ ja: "制服, 茶髪, ポニーテール", en: "school uniform, brown hair, ponytail" }),
          4
        )
      ),
      6
    );
    const characterTags = [
      ...participantNames,
      ...mainLookTokens,
      ...castLookTokens,
    ];
    const chatContextTags = normalizePromptTokens(
      recentDoText,
      t({ ja: "教室, 窓, 机, 夕方, 廊下", en: "classroom, window, desk, sunset, hallway" })
    );
    const mergedLocationTokens = uniqueTokens([
      ...locationTokens,
      ...chatContextTags,
      "indoor",
    ], 5);
    const mergedOutfitTokens = uniqueTokens([
      ...outfitTokens,
      ...mainLookTokens.filter((v) => /uniform|blazer|shirt|jacket|dress|skirt|pants|suit|kimono|制服|ブレザー|シャツ|ジャケット|ワンピース|スカート|ズボン|スーツ|着物/.test(v.toLowerCase())),
    ], 5);
    const subjectClause = `subjects: ${uniqueTokens([...peopleCountTags, ...characterTags], 9).join(", ")}`;
    const actionClause = `action: ${actionTokens.join(", ")}`;
    const sceneClause = `scene: ${(mergedLocationTokens.length ? mergedLocationTokens : ["classroom", "indoor"]).join(", ")}`;
    const outfitClause = `outfit: ${(mergedOutfitTokens.length ? mergedOutfitTokens : ["school uniform"]).join(", ")}`;
    const companionClause = companions.length ? `companions: with ${companions.join(", ")}` : "companions: solo";
    const detailClause = detailTokens.length ? `details: ${detailTokens.join(", ")}` : "";
    const lightTokens = uniqueTokens([
      ...pickByKeywords(recentDoText, ["sunset", "night", "window", "backlight", "逆光", "夕方", "夜", "窓", "木漏れ日"], 3),
      r18Mode ? "soft dramatic lighting" : "soft rim light and window light",
    ], 3);
    const colorTokens = uniqueTokens([
      ...pickByKeywords(recentDoText, ["blue", "amber", "gold", "teal", "neon", "青", "琥珀", "金", "暖色", "寒色"], 3),
      "muted teal and amber",
    ], 3);
    const textureTokens = uniqueTokens([
      "anime key visual",
      "clean lineart",
      "subtle skin texture",
      "highly detailed",
      "sharp focus",
    ], 5);
    const lensTokens = uniqueTokens([
      "50mm lens",
      "shallow depth of field",
      "eye-level medium shot",
      "hands visible",
    ], 4);
    const compositionTokens = uniqueTokens([
      companionClause.includes("solo") ? "single subject composition" : "two-shot composition",
      "balanced framing",
      "clear silhouette",
    ], 3);
    const subjectTokens = uniqueTokens([
      ...peopleCountTags,
      ...participantNames,
      ...mainLookTokens,
      ...castLookTokens,
    ], 10);

    return [
      "prompt blueprint",
      "style reference: anime girl, long black hair, white blouse with large ribbon, black skirt, shy expression, looking slightly down, arms behind back, upper body, indoor wooden floor, soft light",
      `subject: ${subjectTokens.join(", ")}`,
      `composition: ${compositionTokens.join(", ")}`,
      `lighting: ${lightTokens.join(", ")}`,
      `color: ${colorTokens.join(", ")}`,
      `texture/style: ${textureTokens.join(", ")}`,
      `lens/camera: ${lensTokens.join(", ")}`,
      "workflow note: first pass for composition, second pass for hi-res detail polish",
      r18Mode ? "nsfw, adult" : "safe for work",
      "character design consistency, same face, same hairstyle, same outfit details",
      `main character look: ${uniqueTokens([mainName, ...mainLookTokens], 7).join(", ")}`,
      castLookTokens.length ? `other character look: ${castLookTokens.join(", ")}` : "",
      "camera: eye-level, medium shot, full body, hands visible, sharp focus",
      sceneClause,
      outfitClause,
      companionClause,
      subjectClause,
      actionClause,
      detailClause,
    ].filter(Boolean).join("; ");
  };

  const buildCharacterOutputTemplate = () => {
    const resolvedName = compactText(characterName) || t({ ja: "未設定キャラ", en: "Unnamed character" });
    const resolvedAppearance = compactText(appearance) || buildRandomAppearanceText(resolvedName, mainSpeechGender);
    const traits = uniqueTokens(
      normalizePromptTokens(
        personality,
        t({ ja: "やさしい, 知的, 少し皮肉屋", en: "kind, intelligent, slightly sarcastic" }),
        3
      ),
      3
    );
    const intro = traits.length
      ? `${traits.join("・")}案内役`
      : t({ ja: "やさしく導く近未来の案内役", en: "A gentle guide from a near-future world" });
    const firstGreeting = t(
      {
        ja: `はじめまして、${resolvedName}です。無理なく進められるように、必要なところだけ一緒に整理していきましょう。`,
        en: `Hi, I'm ${resolvedName}. I'll help you organize only what you need, step by step.`,
      }
    );
    return [
      "【AIチャットキャラクター出力テンプレ】",
      `名前: ${resolvedName}`,
      `一言紹介(30字以内): ${intro.slice(0, 30)}`,
      `外見(80字以内): ${resolvedAppearance.slice(0, 80)}`,
      `性格: ${traits.join(", ") || t({ ja: "やさしい, 知的, 少し皮肉屋", en: "kind, intelligent, slightly sarcastic" })}`,
      `話し方の特徴: ${t({ ja: "丁寧語ベース、たまに軽い冗談", en: "Mostly polite, with occasional light jokes" })}`,
      `初回あいさつ(100字以内): ${firstGreeting.slice(0, 100)}`,
      `サンプル会話: ${t({ ja: "ユーザー: 今日つらい / キャラ: 今日は深呼吸から始めましょう。次に、いちばん軽い1タスクだけ決めます。", en: "User: Today is rough / Character: Let's start with one deep breath, then pick the lightest single task." })}`,
    ].join("\n");
  };

  const applyCharacterOutputTemplate = () => {
    const nextAppearance = compactText(appearance) || buildRandomAppearanceText(characterName, mainSpeechGender);
    setPersonality(buildCharacterOutputTemplate());
    if (!compactText(appearance)) {
      setAppearance(nextAppearance);
    }
  };

  const buildSceneNegativePromptFromCurrentChat = () => {
    const base = [
      "smile, open mouth",
      "worst quality, low quality, normal quality, lowres, blurry, pixelated, jpeg artifacts",
      "extra limbs, missing limbs, distorted",
      "bad anatomy, bad hands, fused fingers, extra fingers, missing fingers, malformed limbs",
      "deformed face, asymmetrical eyes, cross-eye, duplicate face, cloned face",
      "text, watermark, logo, signature, username, caption, speech bubble, subtitle",
      "cropped, out of frame, duplicate body, extra arms, extra legs",
      "3d, realistic photo, photorealistic, monochrome, sketch",
    ];
    if (!r18Mode) {
      base.push("nsfw, nude, nipples, explicit, sexual content");
    }
    return base.join("; ");
  };

  const withImageUrl = (url) => {
    const raw = String(url || "").trim();
    if (!raw) return "";
    if (raw.startsWith("data:image/")) return raw;
    if (/^https?:\/\//i.test(raw)) return raw;
    if (raw.startsWith("/")) return `${window.location.origin}${raw}`;
    return `${window.location.origin}/${raw}`;
  };

  const handleCreateNovelFromConversation = async () => {
    if (creatingNovelFromChat || loading) return;
    setError("");

    const token = getStoredAuthToken();
    if (!token) {
      setError(
        t({
          ja: "この機能はログインが必要です。",
          en: "Login is required for this feature.",
        })
      );
      return;
    }

    const timeline = buildConversationTimelineForNovel();
    const hasUser = timeline.some((m) => m.role === "user");
    const hasAssistant = timeline.some((m) => m.role === "assistant");
    if (!hasUser || !hasAssistant) {
      setError(
        t({
          ja: "会話全体を小説化するには、ユーザー発言とGPT発言の両方が必要です。",
          en: "Need both user and GPT messages to convert the full chat into a novel.",
        })
      );
      return;
    }

    setCreatingNovelFromChat(true);
    try {
      const timelineText = timeline
        .slice(0, 120)
        .map((m, idx) => {
          const who = m.role === "assistant" ? "GPT" : "ユーザー";
          const modeText = m.mode === "do" ? "do" : "say";
          const speakerLabel = m.speaker ? `(${m.speaker})` : "";
          const line = m.content.length > 1200 ? `${m.content.slice(0, 1200)}...` : m.content;
          return `${idx + 1}. ${who}${speakerLabel} [${modeText}]\n${line}`;
        })
        .join("\n\n");

      const prompt = [
        "次のチャットログを先頭から末尾まで時系列で読み、1本の日本語小説に再構成してください。",
        "各ユーザー発言とGPT発言を素材に、会話内容をベースにした新しい物語へ発展させてください。",
        "要約ではなく、小説として場面描写・心理描写・行動描写を追加し、起承転結のある展開にしてください。",
        "分量は通常よりしっかり増やし、同内容の簡易版ではなく約1.5倍の読了感になるように肉付けしてください。",
        "各ユーザー発言の行間を、直後のGPT発言を参考に地の文で自然につないでください。",
        "会話の感情推移・関係性・出来事の順番は保ちつつ、因果関係と余韻を補って厚みを出してください。",
        "途中の重要な発言は削除せず、台詞や描写として必ず反映してください。",
        "1行目は作品タイトル、2行目は空行、3行目以降を本文にしてください。",
        "本文は章見出しなしで連続した小説文にしてください。",
        "",
        "### チャットログ",
        timelineText,
      ].join("\n");

      const generateRes = await fetch("/api/ai/novels/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          title_hint: "チャットから生まれた物語",
          length: "xlong",
          prompt,
        }),
      });
      const generatedRaw = await generateRes.json().catch(() => ({}));
      const generated = normalizeAiNovelResponse(generatedRaw || {});
      if (!generateRes.ok) {
        throw new Error(
          generated?.detail ||
            t(
              {
                ja: "会話からの小説生成に失敗しました (status={{status}})",
                en: "Failed to generate novel from conversation (status={{status}})",
              },
              { status: generateRes.status }
            )
        );
      }

      const novelTitle =
        String(generated?.generated_title || "").trim() ||
        t({ ja: "チャットから生まれた物語", en: "A Story Born from Chat" });
      const storyBody = String(generated?.body || "").trim();
      if (!storyBody) {
        throw new Error(
          t({
            ja: "生成された本文が空でした。",
            en: "Generated story body was empty.",
          })
        );
      }

      let episodeTitle =
        t({ ja: "第1話", en: "Episode 1" });
      try {
        const titleRes = await fetch("/api/ai/title_candidate", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ text: storyBody.slice(0, 2000) }),
        });
        const titleData = await titleRes.json().catch(() => ({}));
        if (titleRes.ok && titleData?.title) {
          episodeTitle = String(titleData.title).trim() || episodeTitle;
        }
      } catch {
        // ignore title generation failures
      }

      const novelRes = await fetch("/api/novels", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          title: novelTitle,
          description: t({ ja: "AIチャット会話から自動作成", en: "Auto-created from AI chat conversation" }),
          is_ai_generated: true,
          is_public: false,
          age_limit: "all",
          tag_names: [],
        }),
      });
      const novelData = await novelRes.json().catch(() => ({}));
      if (!novelRes.ok) {
        throw new Error(
          novelData?.detail ||
            t(
              {
                ja: "小説の自動作成に失敗しました (status={{status}})",
                en: "Failed to auto-create novel (status={{status}})",
              },
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

      const episodeRes = await fetch(`/api/novels/${novelId}/episodes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          episode_number: 1,
          title: episodeTitle,
          body: storyBody,
          status: "draft",
          tag_names: [],
        }),
      });
      const episodeData = await episodeRes.json().catch(() => ({}));
      if (!episodeRes.ok) {
        throw new Error(
          episodeData?.detail ||
            t(
              {
                ja: "エピソード書き出しに失敗しました (status={{status}})",
                en: "Failed to export episode (status={{status}})",
              },
              { status: episodeRes.status }
            )
        );
      }
      const episodeId = episodeData?.id || episodeData?.episode_id;
      if (!episodeId) {
        throw new Error(
          t({ ja: "エピソードIDが取得できませんでした。", en: "Could not get episode ID." })
        );
      }

      navigate(`/episodes/${episodeId}/edit`);
    } catch (e) {
      setError(
        e?.message ||
          t({
            ja: "会話からの小説作成中にエラーが発生しました。",
            en: "An error occurred while creating a novel from conversation.",
          })
      );
    } finally {
      setCreatingNovelFromChat(false);
    }
  };

  const generateChatSceneImage = async () => {
    if (loading || imageGenerating) return;
    setError("");
    const prompt = compactText(imagePromptDraft) ? imagePromptDraft : buildScenePromptFromCurrentChat();
    const negativePrompt = compactText(imageNegativePromptDraft)
      ? imageNegativePromptDraft
      : buildSceneNegativePromptFromCurrentChat();
    if (!compactText(prompt)) {
      setError(t({ ja: "画像生成プロンプトが空です。", en: "Image prompt is empty." }));
      return;
    }

    setImageGenerating(true);
    try {
      const token = getStoredAuthToken();
      const headers = { "Content-Type": "application/json" };
      if (token) headers.Authorization = `Bearer ${token}`;

      const res = await fetch("/api/ai/chat/generate_image", {
        method: "POST",
        headers,
        body: JSON.stringify({
          prompt,
          negative_prompt: negativePrompt,
          character_id: writableSelectedCharacterId ? Number(writableSelectedCharacterId) : null,
          width: 576,
          height: 1024,
          steps: 40,
          guidance_scale: 6.5,
          num_images: 1,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "画像生成に失敗しました。", en: "Failed to generate image." })
        );
      }
      const images = Array.isArray(data?.images)
        ? data.images
          .map((item) => {
            const rawUrl = String(item?.url || "").trim();
            if (!rawUrl) return null;
            return {
              url: withImageUrl(rawUrl),
              filename: String(item?.filename || "").trim(),
            };
          })
          .filter(Boolean)
        : [];
      if (!images.length) {
        throw new Error(
          t({ ja: "画像URLを取得できませんでした。", en: "No image URL returned." })
        );
      }
      setImagePromptDraft(prompt);
      setImageNegativePromptDraft(negativePrompt);
      setMessages((prev) => [
        ...prev,
        {
          id: null,
          role: "assistant",
          mode: "say",
          is_auto_dialogue: false,
          is_generated_image: true,
          content: t({ ja: "画像を生成しました。", en: "Generated an image." }),
          speaker_name: String(characterName || "").trim(),
          generated_images: images,
        },
      ]);
    } catch (e) {
      setError(
        e?.message ||
          t({ ja: "画像生成中にエラーが発生しました。", en: "Image generation error occurred." })
      );
    } finally {
      setImageGenerating(false);
    }
  };

  const uploadAdditionalChatImages = async () => {
    if (!Array.isArray(chatImageFiles) || chatImageFiles.length === 0) return;
    if (!writableSelectedCharacterId) {
      setError(
        t({
          ja: "画像を貼るには、まず編集可能なキャラを選択してください。",
          en: "Select an editable character before attaching images.",
        })
      );
      return;
    }
    const token = getStoredAuthToken();
    if (!token) {
      setError(t({ ja: "ログインが必要です。", en: "Login required." }));
      return;
    }

    setChatImageUploading(true);
    setError("");
    try {
      const formData = new FormData();
      chatImageFiles.forEach((file) => {
        formData.append("files", file);
      });
      const res = await fetch(
        `/api/ai/chat/characters/${encodeURIComponent(writableSelectedCharacterId)}/messages/images`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "画像アップロードに失敗しました。", en: "Failed to upload images." })
        );
      }
      const images = Array.isArray(data?.images)
        ? data.images
            .map((item) => {
              if (!item || typeof item !== "object") return null;
              const url = String(item.url || "").trim();
              if (!url) return null;
              return {
                url,
                filename: String(item.filename || "").trim(),
              };
            })
            .filter(Boolean)
        : [];
      const descriptions = Array.isArray(data?.descriptions)
        ? data.descriptions.map((v) => String(v || "").trim()).filter(Boolean)
        : [];
      if (!images.length) {
        throw new Error(
          t({ ja: "アップロード画像のURLを取得できませんでした。", en: "No uploaded image URL returned." })
        );
      }
      const imageDescriptionText =
        descriptions.length > 0
          ? `【ユーザー添付画像の説明】\n${descriptions.map((d, i) => `${i + 1}. ${d}`).join("\n")}`
          : t({
              ja: "【ユーザー添付画像】画像を受け取りました。内容を踏まえて返答してください。",
              en: "[User attached image] I attached an image. Please respond considering it.",
            });
      const uploadMessage = {
        id: data?.message_id != null ? Number(data.message_id) : null,
        role: "user",
        mode: "say",
        is_auto_dialogue: false,
        is_generated_image: true,
        image_message_kind: "uploaded_images",
        content: t({ ja: "画像を追加しました。", en: "Added images." }),
        speaker_name: String(userSpeakerProfile?.name || characterName || "").trim(),
        generated_images: images,
        image_descriptions: descriptions,
      };
      setMessages((prev) => [
        ...prev,
        uploadMessage,
      ]);
      setChatImageFiles([]);
      if (chatImageInputRef.current) {
        chatImageInputRef.current.value = "";
      }

      // 画像だけ送っても会話が続くよう、説明文を履歴に含めて1回自動送信する
      const autoPrompt = t({
        ja: "この画像の内容に反応して返信して。",
        en: "Please reply by reacting to this image.",
      });
      const userMessage = {
        id: null,
        role: "user",
        mode: "say",
        content: autoPrompt,
        speaker_name: String(userSpeakerProfile?.name || characterName || "").trim(),
      };
      const explicitHistory = [
        ...historyPayload,
        {
          role: "user",
          content: uploadMessage.speaker_name
            ? `[${uploadMessage.speaker_name}] ${imageDescriptionText}`
            : imageDescriptionText,
          mode: "say",
        },
        {
          role: "user",
          content: userMessage.speaker_name
            ? `[${userMessage.speaker_name}] ${userMessage.content}`
            : userMessage.content,
          mode: "say",
        },
      ];
      setMessages((prev) => [...prev, userMessage]);
      setLastRequest({ text: autoPrompt, mode: "say" });
      setResendDraft(autoPrompt);
      setResendMode("say");
      await sendChat({
        text: autoPrompt,
        modeAtSend: "say",
        explicitHistory,
      });
    } catch (e) {
      setError(
        e?.message ||
          t({ ja: "画像アップロード中にエラーが発生しました。", en: "Failed while uploading images." })
      );
    } finally {
      setChatImageUploading(false);
    }
  };

  const historyPayload = useMemo(
    () =>
      messages
        .filter((m) => {
          if (!m?.is_generated_image) return true;
          return (
            m?.image_message_kind === "uploaded_images"
            && Array.isArray(m?.image_descriptions)
            && m.image_descriptions.length > 0
          );
        })
        .slice(-20)
        .map((m) => ({
          role: m.role,
          content: (() => {
            const base = (
              m?.is_generated_image
              && m?.image_message_kind === "uploaded_images"
              && Array.isArray(m?.image_descriptions)
              && m.image_descriptions.length > 0
            )
              ? `【ユーザー添付画像の説明】\n${m.image_descriptions.map((d, i) => `${i + 1}. ${d}`).join("\n")}`
              : m.content;
            return m.speaker_name ? `[${m.speaker_name}] ${base}` : base;
          })(),
          mode: m.mode,
        })),
    [messages]
  );
  const visibleSavedCharacters = useMemo(() => {
    const filtered = showR18ByDisplaySetting
      ? [...savedCharacters]
      : savedCharacters.filter((c) => !c?.is_r18);
    return filtered.sort((a, b) => {
      const aRecommended = a?.is_recommended ? 1 : 0;
      const bRecommended = b?.is_recommended ? 1 : 0;
      if (bRecommended !== aRecommended) return bRecommended - aRecommended;
      const aScore = Number(a?.recommendation_score || 0);
      const bScore = Number(b?.recommendation_score || 0);
      if (bScore !== aScore) return bScore - aScore;
      const aUpdated = new Date(a?.updated_at || 0).getTime();
      const bUpdated = new Date(b?.updated_at || 0).getTime();
      return bUpdated - aUpdated;
    });
  }, [savedCharacters, showR18ByDisplaySetting]);
  const selectedCharacter = useMemo(
    () => visibleSavedCharacters.find((c) => c.id === selectedCharacterId) || null,
    [visibleSavedCharacters, selectedCharacterId]
  );
  const isDemo02User = useMemo(() => {
    if (typeof window === "undefined") return false;
    return String(localStorage.getItem("username") || "").trim().toLowerCase() === "demo02";
  }, [authToken]);
  const selectedCharacterMessageBytes = useMemo(() => calcChatMessagesBytes(messages), [messages]);
  const selectedCharacterMessageKb = useMemo(
    () => (selectedCharacterMessageBytes / 1024).toFixed(1),
    [selectedCharacterMessageBytes]
  );
  const readableSelectedCharacterId = selectedCharacterId ? String(selectedCharacterId) : "";
  const characterMessageBytesMap = useMemo(() => {
    if (!isDemo02User) return {};
    const out = {};
    visibleSavedCharacters.forEach((c) => {
      const cid = String(c?.id || "").trim();
      if (!cid) return;
      if (cid === readableSelectedCharacterId) {
        out[cid] = selectedCharacterMessageBytes;
        return;
      }
      const draft = loadCharacterChatDraft(cid);
      const raw = Array.isArray(draft?.messages) ? draft.messages : [];
      out[cid] = calcChatMessagesBytes(raw);
    });
    return out;
  }, [isDemo02User, visibleSavedCharacters, readableSelectedCharacterId, selectedCharacterMessageBytes]);
  const selectedCharacterReadonly =
    !!selectedCharacter?.is_readonly
    && String(selectedCharacter?.owner_username || "").trim().toLowerCase() !== "demo02";
  const writableSelectedCharacterId =
    selectedCharacterId && !selectedCharacterReadonly ? selectedCharacterId : "";
  const engagementMetricRows = useMemo(() => {
    const data = engagementSummary;
    if (!data || typeof data !== "object") return [];
    const gender = String(data?.speech_gender || selectedCharacter?.speech_gender || "auto");
    const rows = [
      { key: "engagement", label: t({ ja: "総合", en: "Overall" }), value: Number(data?.average_engagement_score || 0) },
      { key: "latency", label: t({ ja: "速度", en: "Speed" }), value: Number(data?.average_latency_score || 0) },
      { key: "intimacy", label: t({ ja: "親密度", en: "Intimacy" }), value: Number(data?.average_intimacy_score || 0) },
      { key: "proactive", label: t({ ja: "積極度", en: "Proactiveness" }), value: Number(data?.average_proactiveness_score || 0) },
      { key: "consistency", label: t({ ja: "設定整合度", en: "Consistency" }), value: Number(data?.average_consistency_score || 0) },
      { key: "empathy", label: t({ ja: "共感度", en: "Empathy" }), value: Number(data?.average_empathy_score || 0) },
      { key: "novelty", label: t({ ja: "新規性", en: "Novelty" }), value: Number(data?.average_novelty_score || 0) },
      { key: "clarity", label: t({ ja: "明瞭さ", en: "Clarity" }), value: Number(data?.average_clarity_score || 0) },
    ];
    if (gender === "male") {
      rows.push(
        { key: "coolness", label: t({ ja: "かっこよさ", en: "Coolness" }), value: Number(data?.average_coolness_score || 0) },
        { key: "seriousness", label: t({ ja: "まじめさ", en: "Seriousness" }), value: Number(data?.average_seriousness_score || 0) }
      );
    } else {
      rows.push(
        { key: "cuteness", label: t({ ja: "かわいさ", en: "Cuteness" }), value: Number(data?.average_cuteness_score || 0) }
      );
    }
    return rows.map((row) => ({ ...row, value: Math.max(0, Math.min(1, Number(row.value || 0))) }));
  }, [engagementSummary, selectedCharacter?.speech_gender, t]);
  const getSpeakerProfileByKey = (key) => {
    if (key === "you") {
      return {
        key: "you",
        name: t({ ja: "あなた", en: "You" }),
        personality: "",
        fanfic_mode: false,
        speech_gender: "auto",
      };
    }
    if (key === "main") {
      return {
        key: "main",
        name: characterName,
        personality,
        appearance,
        fanfic_mode: fanficMode,
        speech_gender: mainSpeechGender,
      };
    }
    return castCharacters.find((c) => c.key === key) || null;
  };
  const userSpeakerProfile = useMemo(
    () => getSpeakerProfileByKey(userSpeakerKey) || getSpeakerProfileByKey("main"),
    [userSpeakerKey, castCharacters, characterName, personality, fanficMode, mainSpeechGender, t]
  );
  const selectedSpeakerName = normalizeSpeakerName(userSpeakerProfile?.name || characterName)
    || t({ ja: "未選択", en: "Not selected" });
  const relationshipMemoOptions = useMemo(
    () => normalizeRelationshipMemoHistory(relationshipMemoHistory),
    [relationshipMemoHistory]
  );
  const selectedSpeakerBubbles = useMemo(() => {
    const bubbles = [];
    for (let i = 0; i < PREVIEW_BUBBLE_COUNT; i += 1) {
      const current = compactText(nextLineSuggestions[i] || "");
      if (current) {
        bubbles.push(truncateText(current, 88));
      } else if (nextLineLoading && i === 0) {
        bubbles.push(t({ ja: "候補を生成中…", en: "Generating suggestions..." }));
      } else {
        bubbles.push(t({ ja: "「……」", en: "\"...\"" }));
      }
    }
    return {
      name: selectedSpeakerName,
      bubbles,
    };
  }, [nextLineLoading, nextLineSuggestions, selectedSpeakerName, t]);

  const isStopCommand = (text) => {
    const normalized = String(text || "").trim().toLowerCase();
    if (!normalized) return false;
    return AUTO_DIALOGUE_STOP_WORDS.some((w) => normalized.includes(String(w).toLowerCase()));
  };

  const languageStyle = useMemo(() => {
    if (iq80CrudeMode) return "iq80_crude";
    if (dailyTalkMode) return "daily";
    return "normal";
  }, [dailyTalkMode, iq80CrudeMode]);

  const createCastCharacter = () => ({
    key: `cast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    saved_id: "",
    name: "",
    personality: "",
    appearance: "",
    relationship: "",
    fanfic_mode: true,
    speech_gender: "auto",
  });

  const updateCastCharacter = (key, patch) => {
    setCastCharacters((prev) =>
      prev.map((c) => (c.key === key ? { ...c, ...patch } : c))
    );
  };
  const getResolvedCastRelationship = (cast) => {
    const typed = compactText(cast?.relationship || "");
    if (typed) return typed;
    return compactText(castRelationshipSelectMap?.[cast?.key] || "");
  };
  const rememberRelationshipMemo = (text) => {
    const v = compactText(text);
    if (!v) return;
    setRelationshipMemoHistory((prev) => {
      const now = Date.now();
      const key = v.toLowerCase();
      const rows = normalizeRelationshipMemoHistory(prev);
      let found = false;
      const next = rows.map((item) => {
        if (item.text.toLowerCase() !== key) return item;
        found = true;
        return {
          ...item,
          use_count: Number(item.use_count || 0) + 1,
          last_used_at: now,
        };
      });
      if (!found) {
        next.push({ text: v, use_count: 1, last_used_at: now });
      }
      return normalizeRelationshipMemoHistory(next);
    });
  };

  const applySavedCharacterToCast = (castKey, savedId) => {
    const normalizedId = String(savedId || "").trim();
    if (!normalizedId) {
      updateCastCharacter(castKey, { saved_id: "" });
      return;
    }
    const selected = savedCharacters.find((c) => c.id === normalizedId);
    if (!selected) return;
    const split = splitPersonalityAndAppearance(String(selected.personality || ""));
    updateCastCharacter(castKey, {
      saved_id: selected.id,
      name: String(selected.name || "").trim(),
      personality: split.personalityText,
      appearance: split.appearanceText,
      speech_gender: normalizeSpeechGender(selected.speech_gender),
    });
  };

  const removeCastCharacter = (key) => {
    setCastCharacters((prev) => prev.filter((c) => c.key !== key));
    setCastRelationshipSelectMap((prev) => {
      const next = { ...(prev || {}) };
      delete next[key];
      return next;
    });
    setUserSpeakerKey((prev) => (prev === key ? "you" : prev));
    setRandomSpeakerKeys((prev) => {
      const next = prev.filter((k) => k !== key);
      return next.length ? next : ["main"];
    });
    setAutoRandomSpeakerKeys((prev) => {
      const next = prev.filter((k) => k !== key);
      return next.length ? next : ["main"];
    });
  };

  const buildDuplicatedCastName = (baseName, names) => {
    const raw = String(baseName || "").trim() || t({ ja: "サブキャラ", en: "Sub character" });
    const m = raw.match(/^(.*?)(\d+)$/);
    const stem = m ? m[1].trim() : raw;
    let num = m ? Number(m[2]) + 1 : 2;
    const used = new Set((names || []).map((n) => String(n || "").trim()).filter(Boolean));
    let candidate = `${stem}${num}`;
    while (used.has(candidate) && num < 9999) {
      num += 1;
      candidate = `${stem}${num}`;
    }
    return candidate;
  };

  const duplicateCastCharacter = (castKey) => {
    const duplicatedKey = `cast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const isDemo02User =
      typeof window !== "undefined"
      && String(localStorage.getItem("username") || "").trim().toLowerCase() === "demo02";
    setCastCharacters((prev) => {
      const original = prev.find((c) => c.key === castKey);
      if (!original) return prev;
      const nextName = buildDuplicatedCastName(
        original.name,
        prev.map((c) => c.name)
      );
      const duplicate = {
        ...original,
        key: duplicatedKey,
        saved_id: "",
        name: nextName,
        relationship: isDemo02User ? "自分同士" : String(original.relationship || ""),
      };
      return [...prev, duplicate];
    });
    setRandomSpeakerKeys((prev) => (prev.includes(duplicatedKey) ? prev : [...prev, duplicatedKey]));
    setAutoRandomSpeakerKeys((prev) => (prev.includes(duplicatedKey) ? prev : [...prev, duplicatedKey]));
  };
  const duplicateMainCharacter = () => {
    const duplicatedKey = `cast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const isDemo02User =
      typeof window !== "undefined"
      && String(localStorage.getItem("username") || "").trim().toLowerCase() === "demo02";
    setCastCharacters((prev) => {
      const nextName = buildDuplicatedCastName(
        characterName,
        prev.map((c) => c.name)
      );
      const duplicate = {
        ...createCastCharacter(),
        key: duplicatedKey,
        name: nextName,
        personality: String(personality || ""),
        appearance: String(appearance || ""),
        relationship: isDemo02User ? "自分同士" : "",
        fanfic_mode: !!fanficMode,
        speech_gender: normalizeSpeechGender(mainSpeechGender),
      };
      return [...prev, duplicate];
    });
    setRandomSpeakerKeys((prev) => (prev.includes(duplicatedKey) ? prev : [...prev, duplicatedKey]));
    setAutoRandomSpeakerKeys((prev) => (prev.includes(duplicatedKey) ? prev : [...prev, duplicatedKey]));
  };

  const toggleRandomSpeakerKey = (key, checked) => {
    setRandomSpeakerKeys((prev) => {
      if (checked) {
        if (prev.includes(key)) return prev;
        return [...prev, key];
      }
      const next = prev.filter((k) => k !== key);
      return next.length ? next : ["main"];
    });
  };

  const toggleAutoRandomSpeakerKey = (key, checked) => {
    setAutoRandomSpeakerKeys((prev) => {
      if (checked) {
        if (prev.includes(key)) return prev;
        return [...prev, key];
      }
      const next = prev.filter((k) => k !== key);
      return next.length ? next : ["main"];
    });
  };

  const chooseRandomAssistantProfile = (keys = randomSpeakerKeys) => {
    const candidates = keys
      .map((key) => getSpeakerProfileByKey(key))
      .filter((p) => p && p.key !== "you" && String(p.name || "").trim());
    const fallback = getSpeakerProfileByKey("main");
    if (!candidates.length) {
      return fallback;
    }
    const picked = candidates[Math.floor(Math.random() * candidates.length)];
    return picked || fallback;
  };

  const buildParticipantsContext = (speakerKey) => {
    const participants = [];
    const relationshipRules = [];
    const perspectiveRules = [];
    let hasRomanticRelation = false;
    const mainName = String(characterName || "").trim();
    const mainPersonality = String(personality || "").trim();
    const castNamed = castCharacters
      .map((c, idx) => ({ ...c, __idx: idx + 1, __name: String(c.name || "").trim() }))
      .filter((c) => c.__name);
    const nameCounts = {};
    if (mainName) {
      nameCounts[mainName] = (nameCounts[mainName] || 0) + 1;
    }
    castNamed.forEach((c) => {
      nameCounts[c.__name] = (nameCounts[c.__name] || 0) + 1;
    });
    const renderMainLabel = () => {
      if (!mainName) return "";
      return nameCounts[mainName] > 1 ? `メイン(${mainName})` : `メイン:${mainName}`;
    };
    const renderCastLabel = (name, idx) => {
      return nameCounts[name] > 1 ? `サブ${idx}(${name})` : `サブ${idx}:${name}`;
    };
    const formatProfileForContext = (text) => {
      const raw = String(text || "").trim();
      if (!raw) return "性格設定なし";
      return raw.replace(/\s*【二次創作モード補完】/g, "\n【二次創作モード補完】");
    };
    const romanticKeywords = [
      "恋人", "彼氏", "彼女", "夫婦", "婚約", "相思相愛", "両想い", "カップル", "いちゃ", "ラブラブ",
      "lover", "lovers", "boyfriend", "girlfriend", "couple", "romantic",
    ];
    if (speakerKey !== "main" && mainName) {
      participants.push(`- ${renderMainLabel()}: ${mainPersonality || "性格設定なし"}`);
    }
    castNamed.forEach((c) => {
      if (c.key === speakerKey) return;
      const n = c.__name;
      if (!n) return;
      const rel = getResolvedCastRelationship(c);
      const relText = rel ? ` / 関係性: ${rel}` : "";
      const label = renderCastLabel(n, c.__idx);
      participants.push(`- ${label}: ${formatProfileForContext(c.personality)}${relText}`);
      if (rel) {
        relationshipRules.push(`- ${label} との関係性「${rel}」を最優先し、呼び方・距離感・態度を維持する。`);
        if (romanticKeywords.some((k) => rel.toLowerCase().includes(String(k).toLowerCase()))) {
          hasRomanticRelation = true;
          relationshipRules.push(`- ${label} とは恋人関係として、甘く密着した空気・照れ・ときめきが会話で伝わるようにする。`);
        }
      }
    });
    if (hasRomanticRelation) {
      relationshipRules.push("- 恋人関係の会話では、少なくとも一方のAIキャラが主導して積極的に甘える・距離を詰める。");
      relationshipRules.push("- そっけない事務的な返答を避け、触れ合い・独占欲・安心させる言葉を自然に混ぜる。");
    }
    if (participants.length === 0 && relationshipRules.length === 0) return "";
    if (participants.length > 0) {
      perspectiveRules.push("- 他キャラは必ず『他人』として扱い、自分の分身・同一人物のように語らない。");
      perspectiveRules.push("- 同名キャラがいても別個体として描写し、『俺同士』『私がもう一人』のような表現を避ける。");
      perspectiveRules.push("- 台詞は相手を呼びかける形にし、第三者視点で関係性と反応を描く。");
    }
    const sections = [];
    if (participants.length > 0) {
      sections.push(`【会話に登場する他キャラクター】\n${participants.join("\n")}`);
    }
    if (relationshipRules.length > 0) {
      sections.push(`【関係性重視ルール】\n${relationshipRules.join("\n")}`);
    }
    if (perspectiveRules.length > 0) {
      sections.push(`【視点固定ルール】\n${perspectiveRules.join("\n")}`);
    }
    return `\n\n${sections.join("\n\n")}`;
  };

  const buildRoleplayConstraint = (speakerName) => {
    const s = String(speakerName || "").trim();
    if (!s) return "";
    return (
      "\n\n【発言者ロール固定ルール】\n"
      + `- 今回のユーザー入力は「${s}」本人としての発言・思考として扱う。\n`
      + "- 口調・一人称・相手への態度は、そのキャラの既存設定と直前までの関係性を維持する。\n"
      + "- 二次創作キャラ同士の関係（親密度・呼び方・距離感）は勝手にリセット/改変しない。\n"
      + "- 関係性を変える場合は、ユーザーが明示した指示があるときだけ変更する。"
    );
  };

  const buildSpeechGenderConstraint = (speakerName, speechGender) => {
    const s = String(speakerName || "").trim() || "このキャラ";
    if (speechGender === "female") {
      return (
        "\n\n【一人称ルール】\n"
        + `- ${s} の一人称は女性的に統一する（例: 「わたし」「あたし」）。\n`
        + "- 「俺」「僕」など男性寄りの一人称は使わない。\n"
        + "- 語尾・口調も女性的な自然さを優先する。"
      );
    }
    if (speechGender === "male") {
      return (
        "\n\n【一人称ルール】\n"
        + `- ${s} の一人称は男性的に統一する（例: 「俺」「僕」）。\n`
        + "- 「わたし」「あたし」など女性寄りの一人称は使わない。\n"
        + "- 語尾・口調も男性的な自然さを優先する。"
      );
    }
    return "";
  };

  const renderSpeechGenderButtons = (value, onChange) => (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
      <button
        type="button"
        className="btn btn-border"
        onClick={() => onChange("female")}
        style={{
          fontWeight: value === "female" ? 700 : 400,
          borderColor: value === "female" ? "#c75a8a" : undefined,
          background: value === "female" ? "#ffeaf4" : undefined,
        }}
      >
        {t({ ja: "女", en: "Female" })}
      </button>
      <button
        type="button"
        className="btn btn-border"
        onClick={() => onChange("male")}
        style={{
          fontWeight: value === "male" ? 700 : 400,
          borderColor: value === "male" ? "#4f79c8" : undefined,
          background: value === "male" ? "#eaf1ff" : undefined,
        }}
      >
        {t({ ja: "男", en: "Male" })}
      </button>
      <button
        type="button"
        className="btn btn-border"
        onClick={() => onChange("auto")}
        style={{
          fontWeight: value === "auto" ? 700 : 400,
          borderColor: value === "auto" ? "#6f7785" : undefined,
          background: value === "auto" ? "#f2f4f8" : undefined,
        }}
      >
        {t({ ja: "自動", en: "Auto" })}
      </button>
    </div>
  );

  const runCharacterAugment = async ({
    name,
    personalityText,
    appearanceText = "",
    speechGender = "auto",
    enabled,
    animeTitle = "",
  }) => {
    const normalizedName = String(name || "").trim();
    const split = splitPersonalityAndAppearance(personalityText);
    const normalizedPersonality = String(split.personalityText || personalityText || "");
    const normalizedAppearance = String(appearanceText || split.appearanceText || "").trim();
    const normalizedAnimeTitle = String(animeTitle || "").trim();
    if (!enabled) {
      const fallbackAppearance = normalizedAppearance || buildRandomAppearanceText(normalizedName, speechGender);
      return {
        characterName: normalizedName,
        personalityText: normalizedPersonality,
        appearanceText: fallbackAppearance,
        notes: normalizedAppearance ? "" : t({ ja: "通常モードのため見た目をランダム設定しました。", en: "Set random appearance for normal mode." }),
      };
    }
    if (!normalizedName) {
      throw new Error(t({ ja: "二次創作モードではキャラ名が必要です。", en: "Character name is required in fanfic mode." }));
    }
    const cacheKey = `${normalizedName}::${normalizedAnimeTitle}::${normalizedPersonality}::${normalizedAppearance}`;
    const cached = fanficCacheRef.current.get(cacheKey);
    if (cached?.personalityText || cached?.appearanceText) {
      return cached;
    }
    setAugmentLoading(true);
    setAugmentNotes("");
    try {
      const token = getStoredAuthToken();
      const headers = { "Content-Type": "application/json" };
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch("/api/ai/chat/character/augment", {
        method: "POST",
        headers,
        body: JSON.stringify({
          character_name: normalizedName,
          personality: normalizedPersonality,
          anime_title: normalizedAnimeTitle || null,
          model: activeModel,
          provider: modelProvider(activeModel),
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "二次創作キャラ設定の補完に失敗しました。", en: "Failed to augment fanfic character profile." })
        );
      }
      const resolved = {
        characterName: String(data?.character_name || normalizedName).trim(),
        personalityText: String(data?.enriched_personality || normalizedPersonality || "").trim(),
        appearanceText: deriveFanficAppearanceFromSources(
          normalizedName,
          data?.sources,
          normalizedAppearance || buildRandomAppearanceText(normalizedName, speechGender)
        ),
        notes: String(data?.notes || "").trim(),
        animeTitle: String(data?.anime_title || normalizedAnimeTitle || "").trim(),
      };
      fanficCacheRef.current.set(cacheKey, resolved);
      return resolved;
    } finally {
      setAugmentLoading(false);
    }
  };

  const loadChatAccess = async () => {
    const token = getStoredAuthToken();
    try {
      const headers = {};
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch("/api/ai/chat/access", {
        headers,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) return;
      setChatAccess(data || null);
    } catch {
      // ignore
    }
  };

  const loadEngagementSummary = async () => {
    const token = getStoredAuthToken();
    if (!token || !writableSelectedCharacterId) {
      setEngagementSummary(null);
      return;
    }
    setEngagementLoading(true);
    try {
      const res = await fetch(
        `/api/ai/chat/characters/${encodeURIComponent(writableSelectedCharacterId)}/engagement_summary`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "学習スコアの取得に失敗しました。", en: "Failed to load learning scores." })
        );
      }
      setEngagementSummary(data || null);
    } catch (e) {
      setEngagementSummary(null);
      setError(
        e?.message ||
          t({ ja: "学習スコア取得中にエラーが発生しました。", en: "Failed while loading learning scores." })
      );
    } finally {
      setEngagementLoading(false);
    }
  };

  const startAiChatAddonCheckout = async () => {
    if (addonCheckoutLoading) return;
    const token = getStoredAuthToken();
    if (!token) {
      setError(t({ ja: "ログインが必要です。", en: "Login required." }));
      return;
    }
    setAddonCheckoutLoading(true);
    setError("");
    try {
      const res = await fetch("/api/ai/chat/addon/checkout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ blocks: 1 }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "追加課金Checkoutの作成に失敗しました。", en: "Failed to start add-on checkout." })
        );
      }
      const url = String(data?.checkout_url || "").trim();
      if (!url) {
        throw new Error(
          t({ ja: "Checkout URLが取得できませんでした。", en: "Checkout URL was missing." })
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

  const openAnimeTitlePicker = async () => {
    const name = String(characterName || "").trim();
    if (!name) {
      setError(t({ ja: "先にキャラ名を入力してください。", en: "Enter character name first." }));
      return;
    }
    setError("");
    setAnimeTitleLoading(true);
    try {
      const token = getStoredAuthToken();
      const headers = { "Content-Type": "application/json" };
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch("/api/ai/chat/character/anime_title_candidates", {
        method: "POST",
        headers,
        body: JSON.stringify({
          character_name: name,
          model: activeModel,
          provider: modelProvider(activeModel),
          limit: 8,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "作品候補の取得に失敗しました。", en: "Failed to fetch anime title candidates." })
        );
      }
      const candidates = Array.isArray(data?.candidates)
        ? data.candidates.map((v) => String(v || "").trim()).filter(Boolean)
        : [];
      if (!candidates.length) {
        setError(t({ ja: "候補が見つかりませんでした。", en: "No title candidates found." }));
        return;
      }
      if (candidates.length === 1) {
        setSelectedAnimeTitle(candidates[0]);
        return;
      }
      setAnimeTitleCandidateName(name);
      setAnimeTitleCandidates(candidates);
      setAnimeTitleDraft(selectedAnimeTitle && candidates.includes(selectedAnimeTitle) ? selectedAnimeTitle : candidates[0]);
      setAnimeTitleDialogOpen(true);
    } catch (e) {
      setError(
        e?.message ||
          t({ ja: "作品候補の取得中にエラーが発生しました。", en: "Failed to fetch title candidates." })
      );
    } finally {
      setAnimeTitleLoading(false);
    }
  };

  useEffect(() => {
    const state = location.state;
    if (!state || typeof state !== "object") return;
    if (state.source !== "public_chat_character") return;

    const importedName = String(state.prefillCharacterName || "").trim();
    const importedPersonality = String(state.prefillPersonality || "");
    if (!importedName && !importedPersonality) return;

    const importKey = `${String(state.characterId || "")}|${importedName}|${importedPersonality}`;
    if (lastImportedPublicCharacterKeyRef.current === importKey) return;
    lastImportedPublicCharacterKeyRef.current = importKey;

    if (importedName) setCharacterName(importedName);
    const split = splitPersonalityAndAppearance(importedPersonality);
    setPersonality(split.personalityText);
    setAppearance(split.appearanceText);
    setSelectedCharacterId("");
    setMessages([]);
    setSelectedMessageIndex(null);
    setError("");
  }, [location.state]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem(AI_CHAT_CHARACTER_NAME_KEY, characterName || "");
  }, [characterName]);

  useEffect(() => {
    setSelectedAnimeTitle("");
  }, [characterName]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem(AI_CHAT_PERSONALITY_KEY, personality || "");
  }, [personality]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem(AI_CHAT_APPEARANCE_KEY, appearance || "");
  }, [appearance]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (selectedCharacterId) {
      localStorage.setItem(AI_CHAT_SELECTED_CHARACTER_ID_KEY, selectedCharacterId);
    } else {
      localStorage.removeItem(AI_CHAT_SELECTED_CHARACTER_ID_KEY);
    }
  }, [selectedCharacterId]);

  useEffect(() => {
    const split = splitPersonalityAndAppearance(personality);
    if (!split.appearanceText) return;
    if (!appearance) setAppearance(split.appearanceText);
    if (split.personalityText !== personality) setPersonality(split.personalityText);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem(
        AI_CHAT_RELATIONSHIP_MEMO_HISTORY_KEY,
        JSON.stringify(normalizeRelationshipMemoHistory(relationshipMemoHistory))
      );
    } catch {
      // ignore storage failures
    }
  }, [relationshipMemoHistory]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (authToken) return;
    const trimmedName = String(characterName || "").trim();
    const trimmedPersonality = String(personality || "").trim();
    const trimmedAppearance = String(appearance || "").trim();
    const normalizedMessages = (Array.isArray(messages) ? messages : [])
      .slice(-200)
      .map((m) => {
        if (!m || typeof m !== "object") return null;
        return {
          role: m.role === "assistant" ? "assistant" : "user",
          mode: m.mode === "do" ? "do" : "say",
          is_auto_dialogue: !!m.is_auto_dialogue,
          content: String(m.content || ""),
          speaker_name: String(m.speaker_name || ""),
          model_name: String(m.model_name || "").trim(),
          is_generated_image: !!m.is_generated_image,
          image_message_kind: m.image_message_kind === "uploaded_images" ? "uploaded_images" : "generated_images",
          generated_images: Array.isArray(m.generated_images)
            ? m.generated_images
                .map((img) => {
                  if (!img || typeof img !== "object") return null;
                  const url = String(img.url || "").trim();
                  if (!url) return null;
                  const filename = String(img.filename || "").trim();
                  return { url, ...(filename ? { filename } : {}) };
                })
                .filter(Boolean)
            : [],
          image_descriptions: Array.isArray(m.image_descriptions)
            ? m.image_descriptions.map((d) => String(d || "").trim()).filter(Boolean)
            : [],
        };
      })
      .filter(Boolean);

    const hasMeaningfulState = !!(
      trimmedName
      || trimmedPersonality
      || trimmedAppearance
      || normalizedMessages.some((m) => String(m?.content || "").trim())
    );
    if (!hasMeaningfulState) {
      localStorage.removeItem(AI_CHAT_GUEST_DRAFT_KEY);
      return;
    }

    const payload = {
      version: 1,
      character_name: trimmedName,
      personality: personality || "",
      appearance: appearance || "",
      speech_gender: normalizeSpeechGender(mainSpeechGender),
      mode: mode === "do" ? "do" : "say",
      r18_mode: !!r18Mode,
      fanfic_mode: !!fanficMode,
      messages: normalizedMessages,
      updated_at: new Date().toISOString(),
    };
    try {
      localStorage.setItem(AI_CHAT_GUEST_DRAFT_KEY, JSON.stringify(payload));
    } catch {
      // ignore storage failures
    }
  }, [
    authToken,
    appearance,
    characterName,
    fanficMode,
    mainSpeechGender,
    messages,
    mode,
    personality,
    r18Mode,
  ]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!authToken) return;
    const cid = String(selectedCharacterId || "").trim();
    if (!cid) return;
    const normalizedMessages = (Array.isArray(messages) ? messages : [])
      .slice(-500)
      .map((m) => normalizeStoredGuestMessage(m))
      .filter(Boolean);
    const payload = {
      version: 1,
      character_id: cid,
      character_name: String(characterName || "").trim(),
      personality: String(personality || ""),
      appearance: String(appearance || ""),
      speech_gender: normalizeSpeechGender(mainSpeechGender),
      mode: mode === "do" ? "do" : "say",
      r18_mode: !!r18Mode,
      fanfic_mode: !!fanficMode,
      messages: normalizedMessages,
      updated_at: new Date().toISOString(),
    };
    const key = buildCharacterDraftStorageKey(cid);
    if (!key) return;
    try {
      localStorage.setItem(key, JSON.stringify(payload));
    } catch {
      // ignore storage failures
    }
  }, [
    authToken,
    selectedCharacterId,
    characterName,
    personality,
    appearance,
    mainSpeechGender,
    mode,
    r18Mode,
    fanficMode,
    messages,
  ]);

  const maybeAugmentCharacterProfile = async ({
    nameOverride,
    personalityOverride,
    appearanceOverride,
    speechGenderOverride,
    force = false,
  } = {}) => {
    const currentName = String((nameOverride ?? characterName) || "").trim();
    const currentPersonality = String((personalityOverride ?? personality) || "");
    const currentAppearance = String((appearanceOverride ?? appearance) || "").trim();
    const currentSpeechGender = normalizeSpeechGender(speechGenderOverride ?? mainSpeechGender);
    if (!fanficMode) {
      const fallbackAppearance = currentAppearance || buildRandomAppearanceText(currentName, currentSpeechGender);
      if (!force && !currentAppearance && fallbackAppearance) {
        setAppearance(fallbackAppearance);
      }
      return {
        characterName: currentName,
        personalityText: currentPersonality,
        appearanceText: fallbackAppearance,
      };
    }
    const resolved = await runCharacterAugment({
      name: currentName,
      personalityText: currentPersonality,
      appearanceText: currentAppearance,
      speechGender: currentSpeechGender,
      enabled: fanficMode,
      animeTitle: selectedAnimeTitle,
    });
    if (resolved?.animeTitle) {
      setSelectedAnimeTitle(String(resolved.animeTitle || "").trim());
    }
    if (!force && resolved.personalityText && resolved.personalityText !== personality) {
      setPersonality(resolved.personalityText);
    }
    if (!force && resolved.appearanceText && resolved.appearanceText !== appearance) {
      setAppearance(resolved.appearanceText);
    }
    setAugmentNotes(String(resolved.notes || ""));
    return resolved;
  };

  useEffect(() => {
    if (!authToken) {
      setSavedCharacters([]);
      setSelectedCharacterId("");
      return;
    }

    (async () => {
      try {
        setCharactersLoading(true);
        const res = await fetch("/api/ai/chat/characters", {
          headers: { Authorization: `Bearer ${authToken}` },
        });
        const data = await res.json().catch(() => []);
        if (!res.ok) {
          throw new Error(
            data?.detail ||
              t({ ja: "キャラ一覧の取得に失敗しました。", en: "Failed to load characters." })
          );
        }
        const list = Array.isArray(data) ? data : [];
        setSavedCharacters(
          list
            .map((c) => mapApiCharacter(c))
            .filter((c) => c.name)
        );
      } catch (e) {
        setError(
          e?.message ||
            t({ ja: "キャラ一覧の取得中にエラーが発生しました。", en: "Failed to load characters." })
        );
      } finally {
        setCharactersLoading(false);
      }
    })();
  }, [authToken, t]);

  useEffect(() => {
    if (!authToken || guestMigrationStartedRef.current) return;
    const draft = loadGuestChatDraft();
    const importMessages = buildGuestImportMessages(draft?.messages);
    if (!importMessages.length) return;
    if (!guestDraftBackupDoneRef.current && typeof window !== "undefined") {
      const rawText = localStorage.getItem(AI_CHAT_GUEST_DRAFT_KEY) || "";
      const forceByInterval = shouldBackupGuestDraftByInterval();
      const { shouldBackup, hash, bytes } = shouldBackupGuestDraft(rawText, { force: forceByInterval });
      if (shouldBackup && downloadGuestChatDraftJson(draft, rawText)) {
        markGuestDraftBackedUp(hash, bytes);
        markGuestDraftDownloadTime();
        guestDraftBackupDoneRef.current = true;
      }
    }

    guestMigrationStartedRef.current = true;
    (async () => {
      setGuestMigrationRunning(true);
      setGuestMigrationInfo(
        t({
          ja: "ゲスト会話をログインユーザーへ移行しています...",
          en: "Migrating guest chat to your account...",
        })
      );
      try {
        const stamp = (() => {
          const now = new Date();
          const y = now.getFullYear();
          const m = String(now.getMonth() + 1).padStart(2, "0");
          const d = String(now.getDate()).padStart(2, "0");
          const hh = String(now.getHours()).padStart(2, "0");
          const mm = String(now.getMinutes()).padStart(2, "0");
          return `${y}${m}${d}${hh}${mm}`;
        })();
        const rawName = String(draft?.character_name || "").trim();
        const fallbackName = t({ ja: "ゲストチャット", en: "Guest Chat" });
        const migrationTag = t({ ja: "移行", en: "migrated" });
        const nextName = `${(rawName || fallbackName).slice(0, 56)} ${migrationTag} ${stamp}`.trim().slice(0, 80);
        const mergedPersonality = mergePersonalityWithAppearance(
          String(draft?.personality || personality || ""),
          String(draft?.appearance || appearance || "")
        );
        const createRes = await fetch("/api/ai/chat/characters", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${authToken}`,
          },
          body: JSON.stringify({
            name: nextName,
            personality: mergedPersonality,
            speech_gender: normalizeSpeechGender(draft?.speech_gender || mainSpeechGender),
          }),
        });
        const createData = await createRes.json().catch(() => ({}));
        if (!createRes.ok) {
          throw new Error(
            createData?.detail
            || t({ ja: "移行用キャラの作成に失敗しました。", en: "Failed to create migration character." })
          );
        }
        const createdId = String(createData?.id || "").trim();
        if (!createdId) {
          throw new Error(t({ ja: "移行先キャラIDの取得に失敗しました。", en: "Failed to get destination character ID." }));
        }

        const beforeListRes = await fetch(
          `/api/ai/chat/characters/${encodeURIComponent(createdId)}/messages`,
          { headers: { Authorization: `Bearer ${authToken}` } }
        );
        const beforeListData = await beforeListRes.json().catch(() => []);
        const existingMessages = beforeListRes.ok && Array.isArray(beforeListData) ? beforeListData : [];
        const diffMessages = extractAppendOnlyDiffMessages(importMessages, existingMessages);
        if (!diffMessages.length) {
          localStorage.removeItem(AI_CHAT_GUEST_DRAFT_KEY);
          setGuestMigrationInfo(
            t({
              ja: "差分がないため、ゲスト会話の追加入力はありませんでした。",
              en: "No diff found. No additional guest messages were imported.",
            })
          );
          return;
        }

        const importRes = await fetch(`/api/ai/chat/characters/${encodeURIComponent(createdId)}/messages/import`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${authToken}`,
          },
          body: JSON.stringify({
            messages: diffMessages,
            replace_existing: false,
          }),
        });
        const importData = await importRes.json().catch(() => ({}));
        if (!importRes.ok) {
          throw new Error(
            importData?.detail
            || t({ ja: "ゲスト会話の取り込みに失敗しました。", en: "Failed to import guest messages." })
          );
        }

        const normalizedSaved = mapApiCharacter(createData);
        setSavedCharacters((prev) => [normalizedSaved, ...prev.filter((c) => c.id !== normalizedSaved.id)]);
        setSelectedCharacterId(normalizedSaved.id);
        setCharacterName(normalizedSaved.name || "");
        setPersonality(normalizedSaved.personality || "");
        setAppearance(normalizedSaved.appearance || "");
        setMainSpeechGender(normalizeSpeechGender(normalizedSaved.speech_gender));

        const listRes = await fetch(
          `/api/ai/chat/characters/${encodeURIComponent(createdId)}/messages`,
          { headers: { Authorization: `Bearer ${authToken}` } }
        );
        const listData = await listRes.json().catch(() => []);
        if (listRes.ok) {
          applyServerChatMessages(listData);
        }

        localStorage.removeItem(AI_CHAT_GUEST_DRAFT_KEY);
        setGuestMigrationInfo(
          t({
            ja: "ゲスト会話を新規キャラへ移行しました。",
            en: "Guest chat has been migrated to a new character.",
          })
        );
      } catch (e) {
        guestMigrationStartedRef.current = false;
        setError(
          e?.message
          || t({ ja: "ゲスト会話の移行に失敗しました。", en: "Failed to migrate guest chat." })
        );
        setGuestMigrationInfo(
          t({
            ja: "ゲスト会話の移行に失敗しました。再度ログイン後に再試行されます。",
            en: "Guest chat migration failed. It will retry after login.",
          })
        );
      } finally {
        setGuestMigrationRunning(false);
      }
    })();
  }, [authToken, appearance, mainSpeechGender, personality, t]);

  useEffect(() => {
    if (!authToken) return;
    if (!selectedCharacterId) return;
    const exists = savedCharacters.some((c) => c.id === selectedCharacterId);
    if (exists) return;
    setSelectedCharacterId("");
    setMessages([]);
    setLastRequest(null);
    setResendDraft("");
  }, [authToken, savedCharacters, selectedCharacterId]);

  useEffect(() => {
    if (!authToken || typeof window === "undefined") return undefined;
    const backupGuestDraftHourly = () => {
      const draft = loadGuestChatDraft();
      const importMessages = buildGuestImportMessages(draft?.messages);
      if (!importMessages.length) return;
      const rawText = localStorage.getItem(AI_CHAT_GUEST_DRAFT_KEY) || "";
      const forceByInterval = shouldBackupGuestDraftByInterval();
      const { shouldBackup, hash, bytes } = shouldBackupGuestDraft(rawText, { force: forceByInterval });
      if (!shouldBackup) return;
      if (!downloadGuestChatDraftJson(draft, rawText)) return;
      if (!forceByInterval) {
        markGuestDraftBackedUp(hash, bytes);
      } else {
        markGuestDraftBackedUp(hash, Math.max(0, Number(bytes) || 0));
      }
      markGuestDraftDownloadTime();
    };
    backupGuestDraftHourly();
    const timer = window.setInterval(backupGuestDraftHourly, 5 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [authToken]);

  const uploadCharacterImage = async (characterId, file, token) => {
    if (!characterId || !file || !token) return null;
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`/api/ai/chat/characters/${encodeURIComponent(characterId)}/image`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(
        data?.detail ||
          t({ ja: "キャラ画像のアップロードに失敗しました。", en: "Failed to upload character image." })
      );
    }
    const imageUrl = String(data?.image_url || "").trim();
    setSavedCharacters((prev) =>
      prev.map((c) => (c.id === String(characterId) ? { ...c, image_url: imageUrl } : c))
    );
    return imageUrl || null;
  };

  const saveCharacter = (saveMode = "ask") => {
    const run = async () => {
      const token = getStoredAuthToken();
      if (!token) {
        throw new Error(t({ ja: "キャラ登録はログインが必要です。", en: "Login is required to save characters." }));
      }
      const name = characterName.trim();
      if (!name) {
        throw new Error(t({ ja: "キャラ名を入力してください。", en: "Please enter a character name." }));
      }
      const augmented = await maybeAugmentCharacterProfile({
        nameOverride: name,
        personalityOverride: personality,
        appearanceOverride: appearance,
        speechGenderOverride: mainSpeechGender,
        force: true,
      });
      const selected = savedCharacters.find((c) => c.id === selectedCharacterId) || null;
      const sameNameEditable = savedCharacters.filter(
        (c) => !c.is_readonly && String(c.name || "").trim() === name
      );
      const overwriteTarget =
        selected && !selected.is_readonly && String(selected.name || "").trim() === name
          ? selected
          : (sameNameEditable[0] || null);
      if (saveMode === "ask" && sameNameEditable.length > 0) {
        setSaveNameConflict({
          name,
          count: sameNameEditable.length,
          overwriteTargetId: String(overwriteTarget?.id || ""),
        });
        return;
      }
      const shouldUpdateExisting =
        saveMode === "overwrite" && !!overwriteTarget && !!overwriteTarget.id;
      setSaveNameConflict(null);
      const url = shouldUpdateExisting
        ? `/api/ai/chat/characters/${encodeURIComponent(String(overwriteTarget?.id || ""))}`
        : "/api/ai/chat/characters";
      const method = shouldUpdateExisting ? "PUT" : "POST";
      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: augmented.characterName || name,
          personality: mergePersonalityWithAppearance(
            augmented.personalityText || personality,
            augmented.appearanceText || appearance
          ),
          speech_gender: normalizeSpeechGender(mainSpeechGender),
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "キャラ登録に失敗しました。", en: "Failed to save character." })
        );
      }

      const splitSaved = splitPersonalityAndAppearance(String(data.personality || ""));
      const saved = {
        id: String(data.id),
        name: String(data.name || "").trim(),
        personality: splitSaved.personalityText,
        appearance: splitSaved.appearanceText,
        image_url: String(data.image_url || "").trim(),
        speech_gender: normalizeSpeechGender(data.speech_gender),
        owner_username: String(data.owner_username || "").trim(),
        is_readonly: !!data.is_readonly,
        is_public: !!data.is_public,
        is_r18: !!data.is_r18,
        is_name_duplicate: !!data.is_name_duplicate,
        name_duplicate_index: Number(data.name_duplicate_index || 1),
        published_at: data.published_at || null,
      };
      setSavedCharacters((prev) => {
        const without = prev.filter((c) => c.id !== saved.id);
        return [saved, ...without];
      });
      setSelectedCharacterId(saved.id);
      setPersonality(saved.personality || "");
      setAppearance(saved.appearance || "");
      setMainSpeechGender(normalizeSpeechGender(saved.speech_gender));
      if (characterImageFile) {
        setCharacterImageUploading(true);
        try {
          const uploadedImageUrl = await uploadCharacterImage(saved.id, characterImageFile, token);
          if (uploadedImageUrl) {
            saved.image_url = uploadedImageUrl;
          }
          setCharacterImageFile(null);
        } finally {
          setCharacterImageUploading(false);
        }
      }
      setMessages([]);
      setLastRequest(null);
      setResendDraft("");
      setLatestPromptPreview(null);
      setError("");
    };
    run().catch((e) => {
      setError(
        e?.message ||
          t({ ja: "キャラ登録中にエラーが発生しました。", en: "Failed to save character." })
      );
    });
  };

  useEffect(() => {
    setSaveNameConflict(null);
  }, [characterName, selectedCharacterId]);

  const applySelectedCharacter = (id) => {
    if (!id) {
      setSelectedCharacterId("");
      setCharacterImageFile(null);
      setMainSpeechGender("auto");
      setMessages([]);
      setLastRequest(null);
      setResendDraft("");
      setLatestPromptPreview(null);
      return;
    }
    const item = savedCharacters.find((c) => c.id === id);
    if (!item) return;
    setMessages([]);
    setLastRequest(null);
    setResendDraft("");
    setSelectedCharacterId(item.id);
    setCharacterImageFile(null);
    setCharacterName(item.name || "");
    setPersonality(item.personality || "");
    setAppearance(String(item.appearance || ""));
    setMainSpeechGender(normalizeSpeechGender(item.speech_gender));
    setSelectedAnimeTitle("");
    setLatestPromptPreview(null);
    setError("");
  };

  const uploadSelectedCharacterImage = () => {
    const run = async () => {
      if (!writableSelectedCharacterId || !characterImageFile) return;
      const token = getStoredAuthToken();
      if (!token) {
        throw new Error(t({ ja: "画像登録はログインが必要です。", en: "Login is required to upload image." }));
      }
      setCharacterImageUploading(true);
      try {
        await uploadCharacterImage(writableSelectedCharacterId, characterImageFile, token);
        setCharacterImageFile(null);
      } finally {
        setCharacterImageUploading(false);
      }
    };
    run().catch((e) => {
      setError(
        e?.message ||
          t({ ja: "キャラ画像のアップロード中にエラーが発生しました。", en: "Failed while uploading character image." })
      );
    });
  };

  const deleteSelectedCharacter = () => {
    const run = async () => {
      if (!writableSelectedCharacterId) return;
      const token = getStoredAuthToken();
      if (!token) {
        throw new Error(t({ ja: "キャラ削除はログインが必要です。", en: "Login is required to delete characters." }));
      }
      const res = await fetch(`/api/ai/chat/characters/${encodeURIComponent(writableSelectedCharacterId)}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "キャラ削除に失敗しました。", en: "Failed to delete character." })
        );
      }
      setSavedCharacters((prev) => prev.filter((c) => c.id !== writableSelectedCharacterId));
      setSelectedCharacterId("");
      setMessages([]);
      setLastRequest(null);
      setResendDraft("");
      setLatestPromptPreview(null);
      setError("");
    };
    run().catch((e) => {
      setError(
        e?.message ||
          t({ ja: "キャラ削除中にエラーが発生しました。", en: "Failed to delete character." })
      );
    });
  };

  const togglePublishSelectedCharacter = () => {
    const run = async () => {
      if (!writableSelectedCharacterId) return;
      const token = getStoredAuthToken();
      if (!token) {
        throw new Error(t({ ja: "公開設定はログインが必要です。", en: "Login is required for publish settings." }));
      }
      const nextPublic = !(selectedCharacter?.is_public || false);
      const res = await fetch(`/api/ai/chat/characters/${encodeURIComponent(writableSelectedCharacterId)}/publish`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ is_public: nextPublic }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "公開設定の更新に失敗しました。", en: "Failed to update publish setting." })
        );
      }
      setSavedCharacters((prev) =>
        prev.map((c) =>
          c.id === writableSelectedCharacterId
            ? {
                ...c,
                is_public: !!data.is_public,
                published_at: data.published_at || null,
                speech_gender: normalizeSpeechGender(data.speech_gender ?? c.speech_gender),
              }
            : c
        )
      );
    };
    run().catch((e) => {
      setError(
        e?.message ||
          t({ ja: "公開設定の更新中にエラーが発生しました。", en: "Failed to update publish setting." })
      );
    });
  };

  const loadPersonalitySetting = () => {
    const run = async () => {
      setError("");
      const selected = selectedCharacterId
        ? savedCharacters.find((c) => c.id === selectedCharacterId) || null
        : null;
      const baseName = String(selected?.name || characterName || "").trim();
      const basePersonality = String(selected?.personality || personality || "");
      const baseAppearance = String(selected?.appearance || appearance || "");

      if (!baseName && !basePersonality) {
        throw new Error(
          t({
            ja: "読み込む性格設定がありません。保存済みキャラを選ぶか、キャラ名を入力してください。",
            en: "No personality setting to load. Select a saved character or enter a character name.",
          })
        );
      }

      if (fanficMode) {
        const augmented = await maybeAugmentCharacterProfile({
          nameOverride: baseName,
          personalityOverride: basePersonality,
          appearanceOverride: baseAppearance,
          speechGenderOverride: selected?.speech_gender || mainSpeechGender,
          force: true,
        });
        if (augmented.characterName && augmented.characterName !== characterName) {
          setCharacterName(augmented.characterName);
        }
        if (augmented.personalityText && augmented.personalityText !== personality) {
          setPersonality(augmented.personalityText);
        }
        if (augmented.appearanceText && augmented.appearanceText !== appearance) {
          setAppearance(augmented.appearanceText);
        }
        return;
      }

      if (selected) {
        setCharacterName(selected.name || "");
        setPersonality(selected.personality || "");
        setAppearance(String(selected.appearance || ""));
        return;
      }
      throw new Error(
        t({
          ja: "読み込む性格設定がありません。保存済みキャラを選ぶか、二次創作モードをONにしてください。",
          en: "No personality setting to load. Select a saved character or enable fanfic mode.",
        })
      );
    };
    run().catch((e) => {
      setError(
        e?.message ||
          t({ ja: "性格設定の読み込みに失敗しました。", en: "Failed to load personality setting." })
      );
    });
  };

  const updatePersonalitySetting = () => {
    const run = async () => {
      setError("");
      let nextName = characterName.trim();
      let nextPersonality = personality;
      let nextAppearance = String(appearance || "").trim();
      if (!nextName) {
        throw new Error(t({ ja: "キャラ名を入力してください。", en: "Please enter a character name." }));
      }
      if (!nextAppearance && !fanficMode) {
        nextAppearance = buildRandomAppearanceText(nextName, mainSpeechGender);
      }
      // 「性格設定を変更」は入力値をそのまま確定させる。自動補完はここでは行わない。
      if (nextName !== characterName) setCharacterName(nextName);
      if (nextPersonality !== personality) setPersonality(nextPersonality);
      if (nextAppearance !== appearance) setAppearance(nextAppearance);

      if (!writableSelectedCharacterId) {
        return;
      }
      const token = getStoredAuthToken();
      if (!token) {
        throw new Error(t({ ja: "性格設定の変更はログインが必要です。", en: "Login is required to update personality." }));
      }
      const res = await fetch(`/api/ai/chat/characters/${encodeURIComponent(writableSelectedCharacterId)}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: nextName,
          personality: mergePersonalityWithAppearance(nextPersonality, nextAppearance),
          speech_gender: normalizeSpeechGender(mainSpeechGender),
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "性格設定の変更に失敗しました。", en: "Failed to update personality setting." })
        );
      }
      const updatedSplit = splitPersonalityAndAppearance(String(data.personality || mergePersonalityWithAppearance(nextPersonality, nextAppearance)));
      const updated = {
        id: String(data.id || writableSelectedCharacterId),
        name: String(data.name || nextName).trim(),
        personality: updatedSplit.personalityText,
        appearance: updatedSplit.appearanceText,
        image_url: String(data.image_url || "").trim(),
        speech_gender: normalizeSpeechGender(data.speech_gender ?? mainSpeechGender),
        owner_username: String(data.owner_username || "").trim(),
        is_readonly: !!data.is_readonly,
        is_public: !!data.is_public,
        is_r18: !!data.is_r18,
        is_name_duplicate: !!data.is_name_duplicate,
        name_duplicate_index: Number(data.name_duplicate_index || 1),
        published_at: data.published_at || null,
      };
      setSavedCharacters((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      setCharacterName(updated.name);
      setPersonality(updated.personality);
      setAppearance(updated.appearance || "");
      setMainSpeechGender(normalizeSpeechGender(updated.speech_gender));
    };
    run().catch((e) => {
      setError(
        e?.message ||
          t({ ja: "性格設定の変更中にエラーが発生しました。", en: "Failed to update personality setting." })
      );
    });
  };

  const saveCastCharacter = (castKey) => {
    const run = async () => {
      const cast = castCharacters.find((c) => c.key === castKey);
      if (!cast) return;
      const token = getStoredAuthToken();
      if (!token) {
        throw new Error(t({ ja: "キャラ登録はログインが必要です。", en: "Login is required to save characters." }));
      }
      const name = String(cast.name || "").trim();
      if (!name) {
        throw new Error(t({ ja: "キャラ名を入力してください。", en: "Please enter a character name." }));
      }
      const resolved = await runCharacterAugment({
        name,
        personalityText: String(cast.personality || ""),
        appearanceText: String(cast.appearance || ""),
        speechGender: normalizeSpeechGender(cast.speech_gender),
        enabled: !!cast.fanfic_mode,
        animeTitle: "",
      });
      const castSaved = savedCharacters.find((c) => c.id === String(cast.saved_id || ""));
      const canUpdateSaved = !!cast.saved_id && !castSaved?.is_readonly;
      const method = canUpdateSaved ? "PUT" : "POST";
      const url = canUpdateSaved
        ? `/api/ai/chat/characters/${encodeURIComponent(cast.saved_id)}`
        : "/api/ai/chat/characters";
      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: resolved.characterName || name,
          personality: mergePersonalityWithAppearance(
            resolved.personalityText || cast.personality || "",
            resolved.appearanceText || cast.appearance || ""
          ),
          speech_gender: normalizeSpeechGender(cast.speech_gender),
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "サブキャラ登録に失敗しました。", en: "Failed to save sub character." })
        );
      }
      const savedId = String(data.id || cast.saved_id || "");
      const splitSaved = splitPersonalityAndAppearance(
        String(
          data.personality
          || mergePersonalityWithAppearance(
            resolved.personalityText || cast.personality || "",
            resolved.appearanceText || cast.appearance || ""
          )
        )
      );
      updateCastCharacter(castKey, {
        saved_id: savedId,
        name: String(data.name || resolved.characterName || name).trim(),
        personality: splitSaved.personalityText,
        appearance: splitSaved.appearanceText,
        speech_gender: normalizeSpeechGender(data.speech_gender || cast.speech_gender),
      });
      if (savedId) {
        setSavedCharacters((prev) => {
          const normalized = {
            id: savedId,
            name: String(data.name || resolved.characterName || name).trim(),
            personality: splitSaved.personalityText,
            appearance: splitSaved.appearanceText,
            image_url: String(data.image_url || "").trim(),
            speech_gender: normalizeSpeechGender(data.speech_gender || cast.speech_gender),
            owner_username: String(data.owner_username || "").trim(),
            is_readonly: !!data.is_readonly,
            is_public: !!data.is_public,
            is_r18: !!data.is_r18,
            is_name_duplicate: !!data.is_name_duplicate,
            name_duplicate_index: Number(data.name_duplicate_index || 1),
            published_at: data.published_at || null,
          };
          const without = prev.filter((c) => c.id !== savedId);
          return [normalized, ...without];
        });
      }
      setAugmentNotes(String(resolved.notes || ""));
    };
    run().catch((e) => {
      setError(
        e?.message ||
          t({ ja: "サブキャラ登録中にエラーが発生しました。", en: "Failed to save sub character." })
      );
    });
  };

  const loadLatestPromptPreview = async () => {
    if (!writableSelectedCharacterId || previewLoading) return;
    const token = getStoredAuthToken();
    if (!token) {
      setError(t({ ja: "ログインが必要です。", en: "Login required." }));
      return;
    }

    setPreviewLoading(true);
    setError("");
    try {
      const previewParams = new URLSearchParams();
      if (r18Mode) previewParams.set("r18", "1");
      const res = await fetch(
        `/api/ai/chat/characters/${encodeURIComponent(writableSelectedCharacterId)}/latest_prompt_preview?${previewParams.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "最新ログの可視化に失敗しました。", en: "Failed to load latest prompt preview." })
        );
      }
      setLatestPromptPreview(data);
    } catch (e) {
      setError(
        e?.message ||
          t({ ja: "最新ログの可視化中にエラーが発生しました。", en: "Failed to visualize latest logs." })
      );
    } finally {
      setPreviewLoading(false);
    }
  };

  const sendChat = async ({
    text,
    modeAtSend,
    explicitHistory,
    characterNameAtSend,
    personalityAtSend,
  }) => {
    if (!text || loading) return;
    setError("");
    setLoading(true);
    try {
      const token = getStoredAuthToken();
      const headers = { "Content-Type": "application/json" };
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
      const res = await fetchWithSingleRetry("/api/ai/chat", {
        method: "POST",
        cache: "no-store",
        headers,
        body: JSON.stringify({
          message: text,
          mode: modeAtSend,
          r18: r18Mode,
          character_id: selectedCharacterId ? Number(selectedCharacterId) : null,
          character_name: characterNameAtSend ?? characterName,
          personality: personalityAtSend ?? personality,
          long_reply: longReply,
          short_reply: shortReply,
          language_style: languageStyle,
          auto_dialogue: autoDialogue,
          model: activeModel,
          provider: modelProvider(activeModel),
          history: explicitHistory,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "AIチャットに失敗しました。", en: "AI chat failed." })
        );
      }
      const reply = String(data?.reply || "").trim();
      if (!reply) {
        throw new Error(
          t({ ja: "AIの返答が空でした。", en: "AI response was empty." })
        );
      }
      const isDoMode = data?.mode === "do";
      const sayText = String(data?.say || "").trim();
      const extras = Array.isArray(data?.extra_messages) ? data.extra_messages : [];
      setMessages((prev) => {
        if (!isDoMode) {
          const next = [...prev, { id: null, role: "assistant", mode: "say", is_auto_dialogue: false, content: reply, speaker_name: characterNameAtSend ?? characterName, model_name: String(data?.model || activeModel || "").trim() }];
          extras.forEach((m) => {
            const c = String(m?.content || "").trim();
            if (!c) return;
            next.push({
              id: null,
              role: "assistant",
              mode: m?.mode === "do" ? "do" : "say",
              is_auto_dialogue: true,
              content: c,
              speaker_name: characterNameAtSend ?? characterName,
              model_name: String(data?.model || activeModel || "").trim(),
            });
          });
          return next;
        }
        const next = [...prev, { id: null, role: "assistant", mode: "do", is_auto_dialogue: false, content: reply, speaker_name: characterNameAtSend ?? characterName, model_name: String(data?.model || activeModel || "").trim() }];
        if (sayText) {
          next.push({ id: null, role: "assistant", mode: "say", is_auto_dialogue: false, content: sayText, speaker_name: characterNameAtSend ?? characterName, model_name: String(data?.model || activeModel || "").trim() });
        }
        extras.forEach((m) => {
          const c = String(m?.content || "").trim();
          if (!c) return;
          next.push({
            id: null,
            role: "assistant",
            mode: m?.mode === "do" ? "do" : "say",
            is_auto_dialogue: true,
            content: c,
            speaker_name: characterNameAtSend ?? characterName,
            model_name: String(data?.model || activeModel || "").trim(),
          });
        });
        return next;
      });
    } catch (e) {
      const failedText = String(text || "").trim();
      if (failedText) {
        setLastRequest({ text: failedText, mode: modeAtSend === "do" ? "do" : "say" });
        if (!String(resendDraft || "").trim()) {
          setResendDraft(failedText);
        }
        setResendMode(modeAtSend === "do" ? "do" : "say");
      }
      setError(
        normalizeChatFetchErrorMessage(
          e,
          t({ ja: "AIチャット中にエラーが発生しました。", en: "AI chat error occurred." }),
          t
        )
      );
    } finally {
      setLoading(false);
      loadChatAccess();
    }
  };

  const continueAutoDialogue = async (explicitHistory) => {
    if (autoContinuing) return false;
    try {
      setAutoContinuing(true);
      const assistantProfile = autoCharacterMode
        ? chooseRandomAssistantProfile(autoRandomSpeakerKeys)
        : chooseRandomAssistantProfile();
      const assistantKey = String(assistantProfile?.key || "main");
      const assistantName = String(assistantProfile?.name || characterName || "").trim();
      const assistantPersonality = String(assistantProfile?.personality || personality || "");
      const assistantSpeechGender = String(assistantProfile?.speech_gender || "auto");
      const token = getStoredAuthToken();
      const headers = { "Content-Type": "application/json" };
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
      const res = await fetchWithSingleRetry("/api/ai/chat/auto_continue", {
        method: "POST",
        cache: "no-store",
        headers,
        body: JSON.stringify({
          r18: r18Mode,
          character_id: selectedCharacterId ? Number(selectedCharacterId) : null,
          character_name: assistantName,
          personality: `${assistantPersonality}${buildParticipantsContext(assistantKey)}${buildRoleplayConstraint(assistantName)}${buildSpeechGenderConstraint(assistantName, assistantSpeechGender)}`,
          long_reply: longReply,
          short_reply: shortReply,
          language_style: languageStyle,
          model: activeModel,
          provider: modelProvider(activeModel),
          history: explicitHistory,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "自動会話の続行に失敗しました。", en: "Failed to continue auto dialogue." })
        );
      }
      const reply = String(data?.reply || data?.say || "").trim();
      if (!reply) return false;
      setMessages((prev) => [
        ...prev,
        { id: null, role: "assistant", mode: "say", is_auto_dialogue: true, content: reply, speaker_name: assistantName, model_name: String(data?.model || activeModel || "").trim() },
      ]);
      return true;
    } catch (e) {
      setError(
        normalizeChatFetchErrorMessage(
          e,
          t({ ja: "自動会話中にエラーが発生しました。", en: "An error occurred during auto dialogue." }),
          t
        )
      );
      return false;
    } finally {
      setAutoContinuing(false);
      loadChatAccess();
    }
  };

  const submitChat = async (overrideText = null) => {
    const hasExplicitText = typeof overrideText === "string";
    const fromBubble = hasExplicitText;
    const text = String(hasExplicitText ? overrideText : input).trim();
    if (!text || loading) return;
    if (isStopCommand(text)) {
      setAutoDialogue(false);
      if (!fromBubble) setInput("");
      return;
    }
    const userMessage = {
      id: null,
      role: "user",
      mode: mode === "do" ? "do" : "say",
      content: text,
      speaker_name: String(userSpeakerProfile?.name || characterName || "").trim(),
    };
    const explicitHistory = [...historyPayload, userMessage];
    setMessages((prev) => [...prev, userMessage]);
    setLastRequest({ text, mode });
    setResendDraft(text);
    setResendMode(mode);
    if (!fromBubble) setInput("");
    const assistantProfile = chooseRandomAssistantProfile();
    const assistantKey = String(assistantProfile?.key || "main");
    let resolvedCharacterName = String(assistantProfile?.name || "").trim();
    let resolvedPersonality = String(assistantProfile?.personality || "");
    let resolvedAppearance = String(assistantProfile?.appearance || "");
    const resolvedSpeechGender = String(assistantProfile?.speech_gender || "auto");
    const userSpeakerNameAtSend = String(userSpeakerProfile?.name || characterName || "").trim();
    const activeFanfic = !!assistantProfile?.fanfic_mode;
    try {
      const augmented =
        assistantKey === "main"
          ? await maybeAugmentCharacterProfile({
              nameOverride: resolvedCharacterName,
              personalityOverride: resolvedPersonality,
              appearanceOverride: resolvedAppearance,
              speechGenderOverride: resolvedSpeechGender,
            })
          : await runCharacterAugment({
              name: resolvedCharacterName,
              personalityText: resolvedPersonality,
              appearanceText: resolvedAppearance,
              speechGender: resolvedSpeechGender,
              enabled: activeFanfic,
            });
      resolvedCharacterName = augmented.characterName || resolvedCharacterName;
      resolvedPersonality = augmented.personalityText || resolvedPersonality;
      resolvedAppearance = augmented.appearanceText || resolvedAppearance;
      setAugmentNotes(String(augmented.notes || ""));
      if (assistantKey === "main" && resolvedAppearance && resolvedAppearance !== appearance) {
        setAppearance(resolvedAppearance);
      } else if (assistantKey !== "main") {
        updateCastCharacter(assistantKey, {
          name: resolvedCharacterName,
          personality: resolvedPersonality,
          appearance: resolvedAppearance,
        });
      }
    } catch (e) {
      setError(
        e?.message ||
          t({ ja: "二次創作向け設定の補完に失敗しました。", en: "Failed to augment fanfic profile." })
      );
      return;
    }
    await sendChat({
      text,
      modeAtSend: mode,
      explicitHistory,
      characterNameAtSend: resolvedCharacterName,
      personalityAtSend: `${resolvedPersonality}${buildParticipantsContext(assistantKey)}${buildRoleplayConstraint(userSpeakerNameAtSend)}${buildSpeechGenderConstraint(resolvedCharacterName, resolvedSpeechGender)}`,
    });
  };

  const sendSelectedBubbleLine = (line) => {
    const text = compactText(line);
    if (!text || text === "「……」" || text === "候補を生成中…" || text === "Generating suggestions..." || loading) return;
    submitChat(text);
  };

  const applyServerChatMessages = (raw) => {
    const list = Array.isArray(raw) ? raw : [];
    setMessages(
      list.map((m) => {
        const role = m?.role === "assistant" ? "assistant" : "user";
        const ownerUsername = String(m?.message_owner_username || "").trim();
        const serverSpeakerName = String(m?.speaker_name || "").trim();
        const assistantSpeakerName = String(m?.character_name || "").trim()
          || String(characterName || "").trim();
        const parsedImage = parseGeneratedImageMessageContent(String(m?.content || ""));
        const imageKind = String(parsedImage?.kind || "").trim();
        return {
          id: m?.id != null ? Number(m.id) : null,
          role,
          mode: m?.mode === "do" ? "do" : "say",
          is_auto_dialogue: !!m?.is_auto_dialogue,
          model_name: "",
          message_owner_username: ownerUsername,
          content: parsedImage
            ? (
              imageKind === "uploaded_images"
                ? t({ ja: "画像を追加しました。", en: "Added images." })
                : t({ ja: "画像を生成しました。", en: "Generated an image." })
            )
            : String(m?.content || ""),
          speaker_name: serverSpeakerName || (role === "assistant" ? assistantSpeakerName : ownerUsername),
          ...(parsedImage
            ? {
                is_generated_image: true,
                image_message_kind: imageKind || "generated_images",
                generated_images: parsedImage.images,
                image_descriptions: parsedImage.descriptions || [],
              }
            : {}),
        };
      })
    );

    const lastUser = [...list].reverse().find(
      (m) =>
        (m?.role || "") === "user"
        && !parseGeneratedImageMessageContent(String(m?.content || ""))
    );
    if (lastUser) {
      const text = String(lastUser.content || "");
      const lastMode = lastUser?.mode === "do" ? "do" : "say";
      setLastRequest({ text, mode: lastMode });
      setResendDraft(text);
      setResendMode(lastMode);
    } else {
      setLastRequest(null);
      setResendDraft("");
    }

    return list;
  };

  const fetchServerChatMessages = async () => {
    const token = getStoredAuthToken();
    if (!token || !readableSelectedCharacterId) return [];
    const res = await fetch(
      `/api/ai/chat/characters/${encodeURIComponent(readableSelectedCharacterId)}/messages`,
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    const data = await res.json().catch(() => []);
    if (!res.ok) {
      throw new Error(
        data?.detail ||
          t({ ja: "チャット履歴の取得に失敗しました。", en: "Failed to load chat history." })
      );
    }
    return applyServerChatMessages(data);
  };

  const removeGeneratedImageAt = (messageIndex, imageIndex) => {
    const run = async () => {
      if (messageIndex < 0 || imageIndex < 0) return;
      const target = messages[messageIndex];
      if (!target || !Array.isArray(target.generated_images) || target.generated_images.length <= imageIndex) return;
      const token = getStoredAuthToken();
      if (writableSelectedCharacterId && token && target?.id != null) {
        const res = await fetch(
          `/api/ai/chat/characters/${encodeURIComponent(writableSelectedCharacterId)}/messages/${encodeURIComponent(target.id)}/images/${encodeURIComponent(imageIndex)}`,
          {
            method: "DELETE",
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(
            data?.detail ||
              t({ ja: "画像削除に失敗しました。", en: "Failed to delete image." })
          );
        }
      }

      setMessages((prev) => {
        if (messageIndex < 0 || messageIndex >= prev.length) return prev;
        const current = prev[messageIndex];
        const list = Array.isArray(current?.generated_images) ? [...current.generated_images] : [];
        const descs = Array.isArray(current?.image_descriptions) ? [...current.image_descriptions] : [];
        if (imageIndex < 0 || imageIndex >= list.length) return prev;
        list.splice(imageIndex, 1);
        if (imageIndex < descs.length) {
          descs.splice(imageIndex, 1);
        }
        if (!list.length) {
          return prev.filter((_, idx) => idx !== messageIndex);
        }
        const next = [...prev];
        next[messageIndex] = {
          ...current,
          generated_images: list,
          image_descriptions: descs,
        };
        return next;
      });
      setSelectedGeneratedImageKey("");
    };
    run().catch((e) => {
      setError(
        e?.message ||
          t({ ja: "画像削除中にエラーが発生しました。", en: "Failed while deleting image." })
      );
    });
  };

  const deleteFromSelectedMessage = () => {
    const run = async () => {
      if (selectedMessageIndex === null || selectedMessageIndex < 0 || selectedMessageIndex >= messages.length) return;
      const target = messages[selectedMessageIndex];
      if (!target) return;
      const confirmed = window.confirm(
        t({
          ja: "選択したメッセージ以降を削除します。GPTの返信も削除されます。よろしいですか？",
          en: "Delete from selected message onward, including GPT replies. Continue?",
        })
      );
      if (!confirmed) return;

      const token = getStoredAuthToken();

      let messageId = target?.id ?? null;
      if (writableSelectedCharacterId && token && messageId == null) {
        // Sync once so we can get a real message id; otherwise deletion won't persist.
        const serverList = await fetchServerChatMessages();
        const idx = Math.min(Math.max(selectedMessageIndex, 0), Math.max(0, serverList.length - 1));
        messageId = serverList[idx]?.id != null ? Number(serverList[idx].id) : null;
      }

      if (writableSelectedCharacterId && token && messageId != null) {
        const res = await fetch(
          `/api/ai/chat/characters/${encodeURIComponent(writableSelectedCharacterId)}/messages/${encodeURIComponent(messageId)}`,
          {
            method: "DELETE",
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(
            data?.detail ||
              t({ ja: "メッセージ削除に失敗しました。", en: "Failed to delete messages." })
          );
        }
        await fetchServerChatMessages();
      } else if (writableSelectedCharacterId && token && messageId == null) {
        throw new Error(t({ ja: "履歴の同期に失敗しました。少し待ってから再度お試しください。", en: "Failed to sync history. Please try again." }));
      }

      setSelectedMessageIndex(null);
    };
    run().catch((e) => {
      setError(
        e?.message ||
          t({ ja: "メッセージ削除中にエラーが発生しました。", en: "Failed to delete messages." })
      );
    });
  };

  const resendLastRequest = async () => {
    if (!lastRequest || loading) return;
    const text = String(resendDraft || "").trim();
    if (!text) return;
    if (isStopCommand(text)) {
      setAutoDialogue(false);
      return;
    }
    const userMessage = {
      id: null,
      role: "user",
      mode: resendMode === "do" ? "do" : "say",
      content: text,
      speaker_name: String(userSpeakerProfile?.name || characterName || "").trim(),
    };
    const explicitHistory = [...historyPayload, userMessage];
    setMessages((prev) => [...prev, userMessage]);
    setLastRequest({ text, mode: resendMode });
    setIsResending(true);
    try {
      const assistantProfile = chooseRandomAssistantProfile();
      const assistantKey = String(assistantProfile?.key || "main");
      let resolvedCharacterName = String(assistantProfile?.name || "").trim();
      let resolvedPersonality = String(assistantProfile?.personality || "");
      let resolvedAppearance = String(assistantProfile?.appearance || "");
      const resolvedSpeechGender = String(assistantProfile?.speech_gender || "auto");
      const userSpeakerNameAtSend = String(userSpeakerProfile?.name || characterName || "").trim();
      const activeFanfic = !!assistantProfile?.fanfic_mode;
      try {
        const augmented =
          assistantKey === "main"
            ? await maybeAugmentCharacterProfile({
                nameOverride: resolvedCharacterName,
                personalityOverride: resolvedPersonality,
                appearanceOverride: resolvedAppearance,
                speechGenderOverride: resolvedSpeechGender,
              })
            : await runCharacterAugment({
                name: resolvedCharacterName,
                personalityText: resolvedPersonality,
                appearanceText: resolvedAppearance,
                speechGender: resolvedSpeechGender,
                enabled: activeFanfic,
              });
        resolvedCharacterName = augmented.characterName || resolvedCharacterName;
        resolvedPersonality = augmented.personalityText || resolvedPersonality;
        resolvedAppearance = augmented.appearanceText || resolvedAppearance;
        setAugmentNotes(String(augmented.notes || ""));
        if (assistantKey === "main" && resolvedAppearance && resolvedAppearance !== appearance) {
          setAppearance(resolvedAppearance);
        }
      } catch (e) {
        setError(
          e?.message ||
            t({ ja: "二次創作向け設定の補完に失敗しました。", en: "Failed to augment fanfic profile." })
        );
        return;
      }
      await sendChat({
        text,
        modeAtSend: resendMode === "do" ? "do" : "say",
        explicitHistory,
        characterNameAtSend: resolvedCharacterName,
        personalityAtSend: `${resolvedPersonality}${buildParticipantsContext(assistantKey)}${buildRoleplayConstraint(userSpeakerNameAtSend)}${buildSpeechGenderConstraint(resolvedCharacterName, resolvedSpeechGender)}`,
      });
    } finally {
      setIsResending(false);
    }
  };

  useEffect(() => {
    const token = getStoredAuthToken();
    if (!token) {
      return;
    }
    if (!readableSelectedCharacterId) {
      setMessages([]);
      setLastRequest(null);
      setResendDraft("");
      return;
    }

    const localDraft = loadCharacterChatDraft(readableSelectedCharacterId);
    const localMessages = Array.isArray(localDraft?.messages)
      ? localDraft.messages.map(normalizeStoredGuestMessage).filter(Boolean).slice(-500)
      : [];
    if (localMessages.length) {
      setMessages(localMessages);
      const lastUser = [...localMessages].reverse().find(
        (m) => m?.role === "user" && !parseGeneratedImageMessageContent(String(m?.content || ""))
      );
      if (lastUser) {
        const text = String(lastUser.content || "");
        const lastMode = lastUser?.mode === "do" ? "do" : "say";
        setLastRequest({ text, mode: lastMode });
        setResendDraft(text);
        setResendMode(lastMode);
      }
    }

    (async () => {
      try {
        setMessagesLoading(true);
        await fetchServerChatMessages();
      } catch (e) {
        setError(
          e?.message ||
            t({ ja: "チャット履歴の取得中にエラーが発生しました。", en: "Failed to load chat history." })
        );
      } finally {
        setMessagesLoading(false);
      }
    })();
  }, [readableSelectedCharacterId, t, mode]);

  useEffect(() => {
    loadChatAccess();
  }, [selectedCharacterId]);

  useEffect(() => {
    if (!writableSelectedCharacterId) {
      setEngagementSummary(null);
      return;
    }
    loadEngagementSummary();
  }, [writableSelectedCharacterId, messages.length]);

  useEffect(() => {
    if (!autoDialogue) return;
    if (loading || autoContinuing || messagesLoading) return;
    if (messages.length === 0) return;
    const last = messages[messages.length - 1];
    if (!last || last.role !== "assistant") return;

    const timer = setTimeout(() => {
      const snapshot = messages.slice(-20).map((m) => ({
        role: m.role,
        content: m.content,
        mode: m.mode,
      }));
      continueAutoDialogue(snapshot);
    }, 900);
    return () => clearTimeout(timer);
  }, [
    autoDialogue,
    loading,
    autoContinuing,
    messagesLoading,
    messages,
    longReply,
    shortReply,
    autoCharacterMode,
    autoRandomSpeakerKeys,
  ]);

  useEffect(() => {
    if (selectedMessageIndex === null) return;
    if (selectedMessageIndex >= messages.length) {
      setSelectedMessageIndex(null);
    }
  }, [messages.length, selectedMessageIndex]);

  useEffect(() => {
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
      autoSaveTimerRef.current = null;
    }
    if (!writableSelectedCharacterId) return undefined;
    if (!authToken) return undefined;
    if (messagesLoading) return undefined;

    const importMessages = buildGuestImportMessages(messages);
    const signature = JSON.stringify(importMessages);
    if (!signature || signature === "[]" || signature === lastAutoSavedSignatureRef.current) {
      return undefined;
    }

    autoSaveTimerRef.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `/api/ai/chat/characters/${encodeURIComponent(writableSelectedCharacterId)}/messages/import`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${authToken}`,
            },
            body: JSON.stringify({
              messages: importMessages,
              replace_existing: true,
            }),
          }
        );
        if (res.ok) {
          lastAutoSavedSignatureRef.current = signature;
        }
      } catch {
        // Keep chat UX stable even when autosave fails transiently.
      } finally {
        autoSaveTimerRef.current = null;
      }
    }, 700);

    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
        autoSaveTimerRef.current = null;
      }
    };
  }, [messages, writableSelectedCharacterId, authToken, messagesLoading]);

  useEffect(() => {
    setSelectedGeneratedImageKey("");
  }, [selectedCharacterId]);

  useEffect(() => {
    const fallback = [
      t({ ja: "「……」", en: "\"...\"" }),
      t({ ja: "それ、どう受け取ろうかな。", en: "How should I take that?" }),
      t({ ja: "次はこう返してみよう。", en: "Maybe I should reply like this next." }),
    ];
    const speakerName = normalizeSpeakerName(userSpeakerProfile?.name || characterName);
    const speakerPersonality = userSpeakerKey === "you"
      ? ""
      : String(userSpeakerProfile?.personality || personality || "");
    const speakerSpeechGender = String(userSpeakerProfile?.speech_gender || "auto");
    if (!speakerName && !compactText(input) && messages.length === 0) {
      setNextLineSuggestions(fallback);
      setNextLineLoading(false);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        setNextLineLoading(true);
        const token = getStoredAuthToken();
        const headers = { "Content-Type": "application/json" };
        if (token) headers.Authorization = `Bearer ${token}`;
        const res = await fetch("/api/ai/chat/next_user_lines", {
          method: "POST",
          headers,
          signal: controller.signal,
          body: JSON.stringify({
            character_id: token && selectedCharacterId ? Number(selectedCharacterId) : null,
            r18: r18Mode,
            character_name: speakerName || characterName,
            personality: `${speakerPersonality}${buildParticipantsContext(userSpeakerKey)}${buildRoleplayConstraint(speakerName || characterName)}${buildSpeechGenderConstraint(speakerName || characterName, speakerSpeechGender)}`,
            history: historyPayload,
            input_hint: input,
            suggestions_count: PREVIEW_BUBBLE_COUNT,
            language_style: languageStyle,
            model: activeModel,
            provider: modelProvider(activeModel),
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data?.detail || "failed");
        }
        const list = Array.isArray(data?.suggestions)
          ? data.suggestions.map((s) => compactText(s)).filter(Boolean)
          : [];
        if (!list.length) {
          setNextLineSuggestions(fallback);
          return;
        }
        setNextLineSuggestions(list.slice(0, PREVIEW_BUBBLE_COUNT));
      } catch (e) {
        if (e?.name === "AbortError") return;
        setNextLineSuggestions(fallback);
      } finally {
        if (!controller.signal.aborted) setNextLineLoading(false);
      }
    }, 420);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [
    characterName,
    historyPayload,
    input,
    languageStyle,
    messages.length,
    activeModel,
    personality,
    r18Mode,
    selectedCharacterId,
    t,
    userSpeakerKey,
    userSpeakerProfile,
  ]);

  const toggleR18Mode = () => {
    if (loading) return;
    if (!showR18ByDisplaySetting) return;
    if (r18Mode) {
      setR18Mode(false);
      return;
    }
    const ok = window.confirm(
      t({
        ja: "あなたは18歳以上ですか？",
        en: "Are you 18 years old or older?",
      })
    );
    if (!ok) return;
    setR18Mode(true);
  };

  useEffect(() => {
    if (showR18ByDisplaySetting) return;
    setR18Mode(false);
  }, [showR18ByDisplaySetting]);

  useEffect(() => {
    if (!selectedCharacterId) return;
    if (showR18ByDisplaySetting) return;
    const selected = savedCharacters.find((c) => c.id === selectedCharacterId);
    if (selected?.is_r18) {
      setSelectedCharacterId("");
    }
  }, [selectedCharacterId, savedCharacters, showR18ByDisplaySetting]);

  const topNavRowStyle = isMobileViewport
    ? {
        display: "grid",
        gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
        gap: 8,
        marginBottom: 10,
      }
    : {
        display: "flex",
        gap: 8,
        marginBottom: 10,
        flexWrap: "wrap",
      };
  const topNavButtonStyle = isMobileViewport
    ? {
        width: "100%",
        textAlign: "center",
        whiteSpace: "normal",
        lineHeight: 1.25,
        fontSize: "0.92rem",
        fontWeight: 700,
        padding: "11px 8px",
      }
    : undefined;
  const characterBackgroundImageUrl = resolveImageUrl(selectedCharacter?.image_url);

  return (
    <>
      {characterBackgroundImageUrl && (
        <>
          <img
            aria-hidden="true"
            src={characterBackgroundImageUrl}
            alt=""
            style={{
              position: "fixed",
              inset: 0,
              width: "100vw",
              height: "100vh",
              objectFit: "cover",
              pointerEvents: "none",
              zIndex: 0,
              opacity: 0.62,
            }}
          />
          <div
            aria-hidden="true"
            style={{
              position: "fixed",
              inset: 0,
              pointerEvents: "none",
              zIndex: 0,
              background: "linear-gradient(to bottom, rgba(255,255,255,0.2), rgba(255,255,255,0.28))",
            }}
          />
        </>
      )}
    <div className="ai-chat-page" style={{ maxWidth: 960, margin: "0 auto", position: "relative", zIndex: 1 }}>
      <div style={topNavRowStyle}>
        <Link to="/" className="btn btn-border" style={topNavButtonStyle}>{t({ ja: "トップへ", en: "Home" })}</Link>
        <Link to="/ai_chat/lp" className="btn btn-border" style={topNavButtonStyle}>
          {t({ ja: "AIチャットLP", en: "AI Chat LP" })}
        </Link>
        <Link to="/ai-novel" className="btn btn-border" style={topNavButtonStyle}>{t({ ja: "AI小説", en: "AI Novel" })}</Link>
        <Link to="/ai_chat/howto" className="btn btn-border" style={topNavButtonStyle}>
          {t({ ja: "使い方", en: "How to Use" })}
        </Link>
        <button
          type="button"
          className="btn btn-border"
          style={topNavButtonStyle}
          onClick={handleCreateNovelFromConversation}
          disabled={loading || creatingNovelFromChat || messages.length < 2}
        >
          {creatingNovelFromChat
            ? t({ ja: "書き出し中...", en: "Exporting..." })
            : t({ ja: "先頭からAI小説化して書き出す", en: "Convert full chat to AI novel" })}
        </button>
        <Link to="/ai_chat/public" className="btn btn-border" style={topNavButtonStyle}>
          {t({ ja: "公開チャット検索", en: "Public Chat Search" })}
        </Link>
      </div>
      <h2>{t({ ja: "AIチャット", en: "AI Chat" })}</h2>
      <p style={{ color: "#666", marginTop: 0, marginBottom: 12 }}>
        {t({
          ja: "AIキャラクターと自由に会話できるページです。会話内容はそのままAI小説として書き出すこともできます。",
          en: "This page lets you chat freely with AI characters. You can also export the conversation directly as an AI novel.",
        })}
      </p>
      {chatAccess && (
        <div
          style={{
            border: "1px solid #d5dbe7",
            borderRadius: 8,
            padding: 10,
            marginBottom: 10,
            background: "#f8fbff",
          }}
        >
          <div style={{ fontSize: "0.9rem", marginBottom: 6 }}>
            {t({ ja: "AIチャット利用量", en: "AI chat usage" })}: {Number(chatAccess.used_tokens || 0).toLocaleString()} / {Number(chatAccess.allowed_tokens || 0).toLocaleString()} tokens
          </div>
          {chatAccess.is_guest && (
            <div style={{ fontSize: "0.9rem", color: "#4b5569", marginBottom: 8 }}>
              {t({
                ja: "ゲスト利用はクッキー/セッションで管理され、上限は200万トークンです。",
                en: "Guest usage is tracked by cookie/session with a 2,000,000 token cap.",
              })}
            </div>
          )}
          {chatAccess.show_premium_prompt && (
            <div style={{ fontSize: "0.9rem", color: "#5b4a1f", marginBottom: 8 }}>
              {chatAccess.is_guest
                ? t({
                    ja: "ゲスト上限に達しました。ログインすると継続利用できます。",
                    en: "Guest cap reached. Log in to continue.",
                  })
                : t({
                    ja: `無料枠到達以降は、まずプレミアム登録が必要です。プレミアム登録後は追加で${Number(chatAccess.block_tokens || 0).toLocaleString()}トークンの利用枠が付与されます。`,
                    en: `After the free quota, premium registration is required first. After premium, an additional ${Number(chatAccess.block_tokens || 0).toLocaleString()} tokens will be granted.`,
                  })}
            </div>
          )}
          {chatAccess.show_premium_prompt && chatAccess.is_guest && (
            <div style={{ marginBottom: 8 }}>
              <Link to="/login" className="btn btn-border">
                {t({ ja: "ログインする", en: "Log In" })}
              </Link>
            </div>
          )}
          {chatAccess.show_premium_prompt && !chatAccess.demo_bypass && !chatAccess.is_guest && (
            <div style={{ marginBottom: 8 }}>
              <Link to="/premium" className="btn btn-border">
                {t({ ja: "プレミアム登録へ", en: "Go Premium" })}
              </Link>
            </div>
          )}
          {chatAccess.show_addon_prompt && !chatAccess.demo_bypass && (
            <div style={{ fontSize: "0.9rem", color: "#5b4a1f", marginBottom: 8 }}>
              {t({
                ja: `プレミアム付与分を使い切ったため、${Number(chatAccess.block_tokens || 0).toLocaleString()}トークンごと${Number(chatAccess.block_price_yen || 0).toLocaleString()}円の追加課金で継続できます。`,
                en: `Premium-included tokens are exhausted. Continue with add-on payment: ¥${Number(chatAccess.block_price_yen || 0).toLocaleString()} per ${Number(chatAccess.block_tokens || 0).toLocaleString()} tokens.`,
              })}
            </div>
          )}
          {chatAccess.show_addon_prompt && !chatAccess.demo_bypass && (
            <button
              type="button"
              className="btn btn-border"
              onClick={startAiChatAddonCheckout}
              disabled={addonCheckoutLoading}
            >
              {addonCheckoutLoading
                ? t({ ja: "Checkout準備中...", en: "Preparing checkout..." })
                : t({
                    ja: `${Number(chatAccess.block_price_yen || 0).toLocaleString()}円で${Number(chatAccess.block_tokens || 0).toLocaleString()}トークン追加`,
                    en: `Add ${Number(chatAccess.block_tokens || 0).toLocaleString()} tokens for ¥${Number(chatAccess.block_price_yen || 0).toLocaleString()}`,
                  })}
            </button>
          )}
          {chatAccess.demo_bypass && chatAccess.show_premium_prompt && (
            <div style={{ fontSize: "0.85rem", color: "#2f5b1f" }}>
              {t({
                ja: "demo02 はデモ特例で追加課金なしで利用できます。",
                en: "demo02 can continue without add-on payment (demo exception).",
              })}
            </div>
          )}
        </div>
      )}
      {!!writableSelectedCharacterId && (
        <div
          style={{
            border: "1px solid #d5dbe7",
            borderRadius: 8,
            padding: 10,
            marginBottom: 10,
            background: "#fcfdff",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
            <strong>{t({ ja: "会話学習スコア", en: "Conversation Learning Scores" })}</strong>
            <button
              type="button"
              className="btn btn-border"
              onClick={loadEngagementSummary}
              disabled={engagementLoading}
            >
              {engagementLoading
                ? t({ ja: "更新中...", en: "Refreshing..." })
                : t({ ja: "再取得", en: "Refresh" })}
            </button>
          </div>
          <div style={{ marginTop: 6, fontSize: "0.85rem", color: "#5f6675" }}>
            {t({
              ja: "速度・親密度・積極度・共感度はユーザー入力解析、他は返信テキスト特性から算出（0.00〜1.00）。",
              en: "Speed/intimacy/proactiveness/empathy come from user follow-up signals; others come from reply text traits (0.00-1.00).",
            })}
          </div>
          {engagementSummary && Number(engagementSummary.sample_size || 0) > 0 ? (
            <>
              <div style={{ marginTop: 6, fontSize: "0.86rem", color: "#4b5568" }}>
                {t({ ja: "サンプル数", en: "Samples" })}: {Number(engagementSummary.sample_size || 0)}
              </div>
              <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
                {engagementMetricRows.map((row) => (
                  <div key={row.key}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                      <span>{row.label}</span>
                      <span>{row.value.toFixed(2)}</span>
                    </div>
                    <div
                      style={{
                        position: "relative",
                        height: 10,
                        borderRadius: 999,
                        background: "#e8edf5",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          position: "absolute",
                          inset: 0,
                          width: `${Math.round(row.value * 100)}%`,
                          background: "linear-gradient(90deg, #5ca9ff 0%, #44d7b6 100%)",
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div style={{ marginTop: 8, fontSize: "0.86rem", color: "#6b7280" }}>
              {engagementLoading
                ? t({ ja: "読み込み中...", en: "Loading..." })
                : t({ ja: "まだ学習データがありません。会話を続けると表示されます。", en: "No learning data yet. Keep chatting to populate scores." })}
            </div>
          )}
        </div>
      )}
      {animeTitleDialogOpen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1200,
            padding: 16,
          }}
        >
          <div
            style={{
              width: "min(560px, 96vw)",
              maxHeight: "82vh",
              overflow: "auto",
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: 14,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: 8 }}>
              {t({ ja: "作品タイトルを選択", en: "Select anime title" })}
            </div>
            <div style={{ fontSize: "0.9rem", color: "var(--muted-text)", marginBottom: 10 }}>
              {t({ ja: "キャラ名", en: "Character" })}: {animeTitleCandidateName}
            </div>
            <div style={{ display: "grid", gap: 8 }}>
              {animeTitleCandidates.map((title, idx) => (
                <label key={`${title}-${idx}`} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <input
                    type="radio"
                    name="anime-title-candidate"
                    checked={animeTitleDraft === title}
                    onChange={() => setAnimeTitleDraft(title)}
                  />
                  <span>{title}</span>
                </label>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 14 }}>
              <button
                type="button"
                className="btn btn-border"
                onClick={() => {
                  setAnimeTitleDialogOpen(false);
                  setAnimeTitleCandidates([]);
                  setAnimeTitleCandidateName("");
                }}
              >
                {t({ ja: "キャンセル", en: "Cancel" })}
              </button>
              <button
                type="button"
                className="btn btn-border"
                onClick={() => {
                  setSelectedAnimeTitle(String(animeTitleDraft || "").trim());
                  setAnimeTitleDialogOpen(false);
                  setAnimeTitleCandidates([]);
                  setAnimeTitleCandidateName("");
                }}
                disabled={!String(animeTitleDraft || "").trim()}
              >
                {t({ ja: "この作品で決定", en: "Use this title" })}
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gap: 8, marginBottom: 12 }}>
        <label>
          {t({ ja: "登録キャラを選択", en: "Select saved character" })}
          <div style={{ display: "flex", gap: 8, marginTop: 4, flexWrap: "wrap" }}>
            <select
              value={selectedCharacterId}
              onChange={(e) => applySelectedCharacter(e.target.value)}
              style={{ minWidth: 260, flex: 1 }}
              disabled={charactersLoading}
            >
              <option value="">
                {charactersLoading
                  ? t({ ja: "読み込み中...", en: "Loading..." })
                  : t({ ja: "未選択", en: "Not selected" })}
              </option>
              {visibleSavedCharacters.map((c) => (
                <option key={c.id} value={c.id}>
                  {`${c.is_recommended ? "★" : ""}${formatCharacterNameWithIndex(c)}${c.owner_username ? ` @${c.owner_username}` : ""}${c.is_recommended ? ` (${t({ ja: "おすすめ", en: "Recommended" })} ${Number(c.recommendation_score || 0).toFixed(2)})` : ""}${c.is_readonly ? ` (${t({ ja: "閲覧専用", en: "Read only" })})` : ""}${isDemo02User ? ` [${((Number(characterMessageBytesMap[String(c.id)] || 0)) / 1024).toFixed(1)} kB]` : ""}`}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-border"
              onClick={saveCharacter}
            >
              {t({ ja: "キャラ登録/更新", en: "Save/Update character" })}
            </button>
            <button
              type="button"
              className="btn btn-border"
              onClick={deleteSelectedCharacter}
              disabled={!writableSelectedCharacterId}
            >
              {t({ ja: "選択キャラ削除", en: "Delete selected" })}
            </button>
            <button
              type="button"
              className="btn btn-border"
              onClick={togglePublishSelectedCharacter}
              disabled={!writableSelectedCharacterId}
            >
              {selectedCharacter?.is_public
                ? t({ ja: "公開を停止", en: "Unpublish" })
                : t({ ja: "チャットを公開", en: "Publish chat" })}
            </button>
            <button
              type="button"
              className="btn btn-border"
              onClick={loadLatestPromptPreview}
              disabled={!writableSelectedCharacterId || previewLoading}
            >
              {previewLoading
                ? t({ ja: "取得中...", en: "Loading..." })
                : t({ ja: "最新ログ送信内容を可視化", en: "Visualize latest sent payload" })}
            </button>
          </div>
          {selectedCharacterId && (
            <div style={{ marginTop: 6, fontSize: "0.9rem", color: selectedCharacter?.is_public ? "#1f6f43" : "#666" }}>
              {selectedCharacter?.is_public
                ? t({ ja: "このキャラのチャットは公開中です。", en: "This character's chat is public." })
                : t({ ja: "このキャラのチャットは非公開です。", en: "This character's chat is private." })}
            </div>
          )}
          {isDemo02User && (
            <div style={{ marginTop: 4, fontSize: "0.86rem", color: "var(--muted-text)" }}>
              {t(
                { ja: "選択中キャラの会話履歴サイズ: {{kb}} kB（{{bytes}} bytes）", en: "Selected character history size: {{kb}} kB ({{bytes}} bytes)" },
                { kb: selectedCharacterMessageKb, bytes: selectedCharacterMessageBytes.toLocaleString() }
              )}
            </div>
          )}
          {saveNameConflict && (
            <div
              style={{
                marginTop: 8,
                border: "1px solid #d7b97a",
                background: "#fff8e9",
                borderRadius: 8,
                padding: "8px 10px",
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div style={{ fontSize: "0.88rem", color: "#6e4b11" }}>
                {t({
                  ja: `同名キャラ「${saveNameConflict.name}」が ${saveNameConflict.count} 件あります。上書き保存か、同名で複製保存か選択してください。`,
                  en: `Same-name character \"${saveNameConflict.name}\" already exists (${saveNameConflict.count}). Choose overwrite or duplicate save.`,
                })}
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => saveCharacter("overwrite")}
                  disabled={loading || augmentLoading}
                >
                  {t({ ja: "既存を上書き", en: "Overwrite existing" })}
                </button>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => saveCharacter("duplicate")}
                  disabled={loading || augmentLoading}
                >
                  {t({ ja: "同名で複製", en: "Duplicate with same name" })}
                </button>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => setSaveNameConflict(null)}
                >
                  {t({ ja: "キャンセル", en: "Cancel" })}
                </button>
              </div>
            </div>
          )}
          {selectedCharacterReadonly && (
            <div style={{ marginTop: 6, fontSize: "0.9rem", color: "#7a5b1b" }}>
              {t({
                ja: "このキャラは他ユーザー作成のため読み込み専用です。更新・削除・公開変更・履歴保存はできません。",
                en: "This character belongs to another user and is read-only. Update/delete/publish/history save are disabled.",
              })}
            </div>
          )}
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, fontSize: "0.92rem" }}>
            <input
              type="checkbox"
              checked={fanficMode}
              onChange={(e) => setFanficMode(e.target.checked)}
              disabled={loading || augmentLoading}
            />
            <span>
              {t({
                ja: "二次創作モード（アニメ系のキャラ名を検索して性格・見た目を自動補完）",
                en: "Fanfic mode (search anime-like character names and auto-augment personality and appearance)",
              })}
            </span>
          </label>
          {(augmentLoading || augmentNotes) && (
            <div style={{ marginTop: 4, fontSize: "0.85rem", color: augmentLoading ? "#235a93" : "#666" }}>
              {augmentLoading
                ? t({ ja: "二次創作向けのキャラ設定（性格・見た目）を補完中...", en: "Augmenting fanfic character profile (personality and appearance)..." })
                : augmentNotes}
            </div>
          )}
        </label>

        <label>
          {t({ ja: "チャットAI", en: "Chat AI" })}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, fontSize: "0.92rem" }}>
            <input
              type="checkbox"
              checked={recommendedModelsOnly}
              onChange={(e) => setRecommendedModelsOnly(e.target.checked)}
            />
            <span>{t({ ja: "おすすめのみ（Kimi / Gemini 3）", en: "Recommended only (Kimi / Gemini 3)" })}</span>
          </div>
          <select value={activeModel} onChange={(e) => setModel(e.target.value)} style={{ width: "100%", marginTop: 6 }}>
            {visibleAiModels.map((m) => (
              <option key={m.value} value={m.value}>
                {t({ ja: m.labelJa, en: m.labelEn })}
              </option>
            ))}
          </select>
          <div style={{ marginTop: 6, fontSize: "0.86rem", color: "#5f6675" }}>
            {t({
              ja: "性格設定の読み込みを含むAI処理は、ここで選択したモデルを使用します。",
              en: "AI actions including personality loading use the model selected here.",
            })}
          </div>
        </label>

        <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 8 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <strong>{t({ ja: "キャラ選択（ラジオ=あなた / チェック=AIランダム）", en: "Character selection (radio=you / checkbox=AI random)" })}</strong>
            <button
              type="button"
              className="btn btn-border"
              onClick={() => setCastCharacters((prev) => [...prev, createCastCharacter()])}
              disabled={loading || augmentLoading}
            >
              {t({ ja: "+ キャラ追加", en: "+ Add character" })}
            </button>
          </div>
          <div style={{ border: "1px solid #d8dee8", borderRadius: 8, padding: 8, marginBottom: 8 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.9rem" }}>
              <input
                type="checkbox"
                checked={autoCharacterMode}
                onChange={(e) => setAutoCharacterMode(e.target.checked)}
                disabled={loading}
              />
              <span>
                {t({
                  ja: "自動会話キャラモード（この欄のチェック済みキャラでランダム継続）",
                  en: "Auto dialogue character mode (random continuation from checked characters in this section)",
                })}
              </span>
            </label>
            <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  type="checkbox"
                  checked={autoRandomSpeakerKeys.includes("main")}
                  onChange={(e) => toggleAutoRandomSpeakerKey("main", e.target.checked)}
                  disabled={loading}
                />
                <span>{characterName?.trim() || t({ ja: "メインキャラ", en: "Main character" })}</span>
              </label>
              {castCharacters.map((cast) => (
                <label key={`auto-select-${cast.key}`} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <input
                    type="checkbox"
                    checked={autoRandomSpeakerKeys.includes(cast.key)}
                    onChange={(e) => toggleAutoRandomSpeakerKey(cast.key, e.target.checked)}
                    disabled={loading}
                  />
                  <span>{cast.name?.trim() || t({ ja: "サブキャラ", en: "Sub character" })}</span>
                </label>
              ))}
            </div>
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <input
              type="radio"
              name="user-speaker"
              checked={userSpeakerKey === "you"}
              onChange={() => setUserSpeakerKey("you")}
            />
            <span>{t({ ja: "あなた（デフォルト）", en: "You (default)" })}</span>
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <input
              type="radio"
              name="user-speaker"
              checked={userSpeakerKey === "main"}
              onChange={() => setUserSpeakerKey("main")}
            />
            <input
              type="checkbox"
              checked={randomSpeakerKeys.includes("main")}
              onChange={(e) => toggleRandomSpeakerKey("main", e.target.checked)}
            />
            <span>{characterName?.trim() || t({ ja: "メインキャラ", en: "Main character" })}</span>
          </label>
          {castCharacters.map((cast) => (
            <div key={cast.key} style={{ borderTop: "1px solid #eee", paddingTop: 8, marginTop: 8 }}>
              {(() => {
                const currentRelationship = compactText(cast.relationship || "");
                const selectedRelationship = compactText(castRelationshipSelectMap?.[cast.key] || "");
                const effectiveRelationship = currentRelationship || selectedRelationship;
                const hasCurrentInHistory = relationshipMemoOptions.some(
                  (memo) => memo.text === effectiveRelationship
                );
                const relationshipSelectOptions = (
                  effectiveRelationship && !hasCurrentInHistory
                    ? [{ text: effectiveRelationship }, ...relationshipMemoOptions]
                    : relationshipMemoOptions
                );
                return (
                  <>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  type="radio"
                  name="user-speaker"
                  checked={userSpeakerKey === cast.key}
                  onChange={() => setUserSpeakerKey(cast.key)}
                />
                <input
                  type="checkbox"
                  checked={randomSpeakerKeys.includes(cast.key)}
                  onChange={(e) => toggleRandomSpeakerKey(cast.key, e.target.checked)}
                />
                <span>{cast.name?.trim() || t({ ja: "サブキャラ", en: "Sub character" })}</span>
              </label>
              <div style={{ fontSize: "0.84rem", color: "#5f6675", marginTop: 6 }}>
                {t({ ja: "一人称", en: "First-person style" })}
              </div>
              {renderSpeechGenderButtons(
                cast.speech_gender || "auto",
                (next) => updateCastCharacter(cast.key, { speech_gender: next })
              )}
              <select
                value={cast.saved_id || ""}
                onChange={(e) => applySavedCharacterToCast(cast.key, e.target.value)}
                style={{ width: "100%", marginTop: 6 }}
                disabled={charactersLoading}
              >
                <option value="">
                  {charactersLoading
                    ? t({ ja: "読み込み中...", en: "Loading..." })
                    : t({ ja: "登録キャラから選択", en: "Select saved character" })}
                </option>
                {visibleSavedCharacters.map((c) => (
                  <option key={c.id} value={c.id}>
                    {`${c.is_recommended ? "★" : ""}${formatCharacterNameWithIndex(c)}${c.owner_username ? ` @${c.owner_username}` : ""}${c.is_recommended ? ` (${t({ ja: "おすすめ", en: "Recommended" })} ${Number(c.recommendation_score || 0).toFixed(2)})` : ""}${c.is_readonly ? ` (${t({ ja: "閲覧専用", en: "Read only" })})` : ""}`}
                  </option>
                ))}
              </select>
              <input
                value={cast.name}
                onChange={(e) => updateCastCharacter(cast.key, { name: e.target.value })}
                placeholder={t({ ja: "サブキャラ名", en: "Sub character name" })}
                style={{ width: "100%", marginTop: 6 }}
              />
              <textarea
                value={cast.personality}
                onChange={(e) => updateCastCharacter(cast.key, { personality: e.target.value })}
                rows={isMobileViewport ? 4 : 2}
                placeholder={t({ ja: "サブキャラの性格設定", en: "Sub character personality" })}
                style={{ width: "100%", marginTop: 6 }}
              />
              <textarea
                value={cast.appearance || ""}
                onChange={(e) => updateCastCharacter(cast.key, { appearance: e.target.value })}
                rows={2}
                placeholder={t({ ja: "サブキャラの見た目（例: 黒髪, 制服, 青い目）", en: "Sub character appearance (e.g. black hair, uniform, blue eyes)" })}
                style={{ width: "100%", marginTop: 6 }}
              />
              <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap", alignItems: "center" }}>
                <select
                  value={effectiveRelationship || ""}
                  onChange={(e) => {
                    const next = String(e.target.value || "");
                    if (!next) return;
                    setCastRelationshipSelectMap((prev) => ({ ...(prev || {}), [cast.key]: next }));
                    updateCastCharacter(cast.key, { relationship: next });
                    rememberRelationshipMemo(next);
                  }}
                  style={{ flex: "1 1 220px", minWidth: 180 }}
                >
                  <option value="">
                    {t({ ja: "関係性履歴から選択", en: "Select from relationship history" })}
                  </option>
                  {relationshipSelectOptions.map((memo) => (
                    <option key={`relationship-select-${memo.text}`} value={memo.text}>
                      {memo.text}
                    </option>
                  ))}
                </select>
                <input
                  value={cast.relationship || ""}
                  onChange={(e) => updateCastCharacter(cast.key, { relationship: e.target.value })}
                  onBlur={(e) => rememberRelationshipMemo(e.target.value)}
                  placeholder={t({ ja: "関係性メモ（例: 幼なじみ/恋人/師弟）", en: "Relationship note (e.g. childhood friend / partner / mentor)" })}
                  list="relationship-memo-history"
                  autoComplete="on"
                  style={{ flex: "2 1 260px", minWidth: 220 }}
                />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginTop: 6 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input
                    type="checkbox"
                    checked={!!cast.fanfic_mode}
                    onChange={(e) => updateCastCharacter(cast.key, { fanfic_mode: e.target.checked })}
                  />
                  <span>{t({ ja: "二次創作", en: "Fanfic" })}</span>
                </label>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => saveCastCharacter(cast.key)}
                  disabled={loading || augmentLoading}
                >
                  {t({ ja: "このキャラを登録/更新", en: "Save/Update this character" })}
                </button>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => duplicateCastCharacter(cast.key)}
                  disabled={loading || augmentLoading}
                >
                  {t({ ja: "このキャラを複製", en: "Duplicate this character" })}
                </button>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={() => removeCastCharacter(cast.key)}
                  disabled={loading || augmentLoading}
                >
                  {t({ ja: "削除", en: "Delete" })}
                </button>
              </div>
                  </>
                );
              })()}
            </div>
          ))}
          <datalist id="relationship-memo-history">
            {relationshipMemoOptions.map((memo, idx) => (
              <option key={`relationship-memo-${idx}`} value={memo.text} />
            ))}
          </datalist>
        </div>

        <label>
          {t({ ja: "キャラ名", en: "Character name" })}
          <input
            value={characterName}
            onChange={(e) => setCharacterName(e.target.value)}
            placeholder={t({ ja: "例: レイ", en: "e.g. Rei" })}
            style={{ width: "100%", marginTop: 4 }}
          />
          <div style={{ fontSize: "0.84rem", color: "#5f6675", marginTop: 6 }}>
            {t({ ja: "メインキャラの一人称", en: "Main character first-person style" })}
          </div>
          {renderSpeechGenderButtons(mainSpeechGender, setMainSpeechGender)}
          <div style={{ display: "flex", gap: 8, marginTop: 6, alignItems: "center", flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn btn-border"
              onClick={duplicateMainCharacter}
              disabled={loading || augmentLoading}
            >
              {t({ ja: "このキャラを複製", en: "Duplicate this character" })}
            </button>
            <button
              type="button"
              className="btn btn-border"
              onClick={openAnimeTitlePicker}
              disabled={loading || augmentLoading || animeTitleLoading || !fanficMode || !characterName.trim()}
            >
              {animeTitleLoading
                ? t({ ja: "候補取得中...", en: "Loading titles..." })
                : t({ ja: "作品候補を選択", en: "Select anime title" })}
            </button>
            {selectedAnimeTitle && (
              <span style={{ fontSize: "0.88rem", color: "#556" }}>
                {t({ ja: "選択中", en: "Selected" })}: {selectedAnimeTitle}
              </span>
            )}
          </div>
        </label>

        <label>
          {t({ ja: "性格設定", en: "Personality" })}
          <textarea
            value={personality}
            onChange={(e) => setPersonality(e.target.value)}
            placeholder={t(
              { ja: "例: 冷静で丁寧。時々毒舌。", en: "e.g. Calm and polite, sometimes sharp-tongued." }
            )}
            rows={isMobileViewport ? 4 : 3}
            style={{ width: "100%", marginTop: 4 }}
          />
          <div style={{ marginTop: 6, display: "flex", justifyContent: "flex-end" }}>
            <button
              type="button"
              className="btn btn-border"
              onClick={applyCharacterOutputTemplate}
              disabled={loading || augmentLoading}
            >
              {t({ ja: "キャラ出力テンプレを適用", en: "Apply character output template" })}
            </button>
          </div>
          <div style={{ marginTop: 8, fontSize: "0.9rem", fontWeight: 700 }}>
            {t({ ja: "見た目設定（画像生成で優先）", en: "Appearance (prioritized for image generation)" })}
          </div>
          <textarea
            value={appearance}
            onChange={(e) => setAppearance(e.target.value)}
            placeholder={t(
              { ja: "例: 黒髪ロング, 青い目, 制服, 細身", en: "e.g. long black hair, blue eyes, school uniform, slim build" }
            )}
            rows={2}
            style={{ width: "100%", marginTop: 4 }}
          />
          <div style={{ marginTop: 8, fontSize: "0.9rem", fontWeight: 700 }}>
            {t({ ja: "キャラ参照画像（1枚）", en: "Character reference image (1 file)" })}
          </div>
          {selectedCharacter?.image_url && (
            <div style={{ marginTop: 6, marginBottom: 6 }}>
              <img
                src={resolveImageUrl(selectedCharacter.image_url)}
                alt={t({ ja: "キャラ参照画像", en: "Character reference image" })}
                style={{ width: "100%", maxWidth: 220, borderRadius: 8, border: "1px solid #d8dce6", display: "block" }}
              />
            </div>
          )}
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setCharacterImageFile(e.target.files?.[0] || null)}
            style={{ width: "100%", marginTop: 4 }}
          />
          <div style={{ marginTop: 6, display: "flex", justifyContent: "flex-end" }}>
            <button
              type="button"
              className="btn btn-border"
              onClick={uploadSelectedCharacterImage}
              disabled={loading || augmentLoading || characterImageUploading || !characterImageFile || !writableSelectedCharacterId}
            >
              {characterImageUploading
                ? t({ ja: "画像登録中...", en: "Uploading image..." })
                : t({ ja: "この画像をキャラに登録", en: "Register this image to character" })}
            </button>
          </div>
          {!writableSelectedCharacterId && characterImageFile && (
            <div style={{ marginTop: 4, fontSize: "0.8rem", color: "#5f6675" }}>
              {t({
                ja: "先にキャラ登録/更新を押すと、この画像も自動で登録されます。",
                en: "Save/Update character first, then this image will be uploaded automatically.",
              })}
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 6 }}>
            <button
              type="button"
              className="btn btn-border"
              onClick={updatePersonalitySetting}
              disabled={loading || augmentLoading}
              style={{ marginRight: 8 }}
            >
              {t({ ja: "性格設定を変更", en: "Update personality setting" })}
            </button>
            <button
              type="button"
              className="btn btn-border"
              onClick={loadPersonalitySetting}
              disabled={loading || augmentLoading}
            >
              {augmentLoading
                ? t({ ja: "読み込み中...", en: "Loading..." })
                : t({ ja: "性格設定を読み込み", en: "Load personality setting" })}
            </button>
          </div>
        </label>
      </div>

		      <div
		        style={{
		          border: "1px solid var(--border)",
		          background: characterBackgroundImageUrl ? "rgba(255,255,255,0.18)" : "var(--surface)",
		          color: "var(--text)",
		          borderRadius: 8,
		          padding: 10,
		          minHeight: 260,
		          marginBottom: 10,
		        }}
		      >
		        {messagesLoading && (
	          <p style={{ color: "var(--muted-text)" }}>
	            {t({ ja: "履歴を読み込み中...", en: "Loading history..." })}
	          </p>
	        )}
	        {messages.length === 0 && (
	          <p style={{ color: "var(--muted-text)" }}>
	            {t({ ja: "メッセージを送ると会話が始まります。", en: "Send a message to start chatting." })}
	          </p>
	        )}
	        {messages.map((m, idx) => (
          <div
            key={`${m.role}-${idx}`}
            style={{
              marginBottom: 10,
              border: selectedMessageIndex === idx ? "1px solid #4a87c2" : "1px solid transparent",
              borderRadius: 10,
              padding: selectedMessageIndex === idx ? 4 : 0,
              cursor: "pointer",
            }}
            onClick={() => setSelectedMessageIndex((prev) => (prev === idx ? null : idx))}
          >
	            {m.mode === "do" ? (
	              <div
	                style={{
	                  background: "#fff2dc",
	                  border: "1px solid #f1c27a",
	                  color: "#4b3214",
	                  borderRadius: 8,
	                  padding: "8px 10px",
	                  whiteSpace: "pre-wrap",
	                  lineHeight: 1.6,
	                }}
	              >
		                <div style={{ fontSize: "0.78rem", color: "#3f2c14", marginBottom: 4, fontWeight: 700 }}>
			                  {(m.role === "user"
			                    ? (m.speaker_name?.trim() || t({ ja: "あなた", en: "You" }))
			                    : (m.speaker_name?.trim() || characterName.trim() || t({ ja: "AI", en: "AI" })) ) +
			                    " / do"}
                  {m.message_owner_username
                    ? ` @${m.message_owner_username}`
                    : ""}
	                  {m.is_auto_dialogue
	                    ? ` ${t({ ja: "[自動会話]", en: "[Auto]" })}`
	                    : ""}
                  {showChatbotByDisplaySetting && m.role === "assistant" && m.model_name
                    ? ` [${m.model_name}]`
                    : ""}
                </div>
                {m.content}
              </div>
            ) : (
              <div
                style={{
                  display: "flex",
                  justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                }}
              >
	                <div
	                  style={{
	                    maxWidth: "82%",
	                    background: m.role === "user" ? "#dff2ff" : "#f6f7fb",
	                    border: "1px solid #cfd4e2",
	                    borderRadius: 14,
	                    padding: "8px 12px",
	                    whiteSpace: "pre-wrap",
	                    lineHeight: 1.5,
	                    color: "#111",
	                  }}
	                >
		                  <div style={{ fontSize: "0.78rem", color: "#334155", marginBottom: 4 }}>
			                    {m.role === "user"
			                      ? (m.speaker_name?.trim() || t({ ja: "あなた", en: "You" }))
			                      : (m.speaker_name?.trim() || characterName.trim() || t({ ja: "AI", en: "AI" }))}{" "}
			                    / say
                    {m.message_owner_username
                      ? ` @${m.message_owner_username}`
                      : ""}
	                    {m.is_auto_dialogue
	                      ? ` ${t({ ja: "[自動会話]", en: "[Auto]" })}`
	                      : ""}
                    {showChatbotByDisplaySetting && m.role === "assistant" && m.model_name
                      ? ` [${m.model_name}]`
                      : ""}
                  </div>
                  {m.content ? <div>{m.content}</div> : null}
                  {Array.isArray(m.generated_images) && m.generated_images.length > 0 && (
                    <div style={{ marginTop: m.content ? 8 : 0, display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-start" }}>
                      {Array.isArray(m.image_descriptions) && m.image_descriptions.length > 0 && (
                        <div
                          style={{
                            width: "100%",
                            maxWidth: 330,
                            background: "#f7f9ff",
                            border: "1px solid #d8dce6",
                            borderRadius: 8,
                            padding: "7px 9px",
                            fontSize: "0.82rem",
                            color: "#334155",
                            whiteSpace: "pre-wrap",
                          }}
                        >
                          {m.image_descriptions.map((desc, didx) => (
                            <div key={`desc-${didx}`} style={{ marginBottom: didx + 1 < m.image_descriptions.length ? 4 : 0 }}>
                              {didx + 1}. {desc}
                            </div>
                          ))}
                        </div>
                      )}
                      {m.generated_images.map((img, gidx) => {
                        const imageKey = `${m.id ?? `tmp-${idx}`}:${gidx}`;
                        const selected = selectedGeneratedImageKey === imageKey;
                        return (
                          <div
                            key={`${img.url}-${gidx}`}
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                            }}
                            onDoubleClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              setSelectedGeneratedImageKey(imageKey);
                            }}
                            style={{
                              border: selected ? "2px solid #d32f2f" : "1px solid #d8dce6",
                              borderRadius: 8,
                              padding: 6,
                              textDecoration: "none",
                              color: "inherit",
                              width: "100%",
                              maxWidth: 330,
                              marginRight: "auto",
                              background: "#fff",
                            }}
                          >
                            <img
                              src={img.url}
                              alt={img.filename || `scene-${gidx + 1}`}
                              style={{ width: "100%", display: "block", borderRadius: 6 }}
                            />
                            <div style={{ marginTop: 6, fontSize: "0.8rem", color: "#5f6675", wordBreak: "break-all" }}>
                              {img.filename || img.url}
                            </div>
                            <div style={{ marginTop: 4, display: "flex", justifyContent: "flex-end" }}>
                              <a
                                href={img.url}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                style={{ fontSize: "0.78rem", color: "var(--accent)", textDecoration: "underline" }}
                              >
                                {t({ ja: "画像を開く", en: "Open image" })}
                              </a>
                            </div>
                            {selected && (
                              <div style={{ marginTop: 6, display: "flex", justifyContent: "flex-end" }}>
                                <button
                                  type="button"
                                  className="btn btn-border"
                                  onClick={(e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    removeGeneratedImageAt(idx, gidx);
                                  }}
                                  style={{ borderColor: "#d32f2f", color: "#d32f2f" }}
                                >
                                  {t({ ja: "この画像を削除", en: "Delete this image" })}
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}
		          </div>
		        ))}
		      </div>
	      {selectedMessageIndex !== null && (
	        <div style={{ marginTop: -2, marginBottom: 10, display: "flex", justifyContent: "flex-end" }}>
	          <button
            type="button"
            className="btn btn-border"
            onClick={deleteFromSelectedMessage}
            disabled={loading}
          >
            {t({ ja: "選択以降を削除（GPT返信含む）", en: "Delete from selected (incl. GPT replies)" })}
          </button>
        </div>
      )}
      <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 10, marginBottom: 10 }}>
        <div style={{ fontSize: "0.9rem", fontWeight: 700, marginBottom: 6 }}>
          {t({ ja: "チャットシーン画像生成", en: "Chat scene image generation" })}
        </div>
        <textarea
          value={imagePromptDraft}
          onChange={(e) => setImagePromptDraft(e.target.value)}
          rows={3}
          placeholder={t({
            ja: "空欄なら現在の会話ログから自動でプロンプトを作成します。",
            en: "If blank, prompt is auto-built from current chat logs.",
          })}
          style={{ width: "100%", marginBottom: 8 }}
          disabled={imageGenerating}
        />
        <textarea
          value={imageNegativePromptDraft}
          onChange={(e) => setImageNegativePromptDraft(e.target.value)}
          rows={2}
          placeholder={t({
            ja: "ネガティブプロンプト。空欄なら自動生成します。",
            en: "Negative prompt. If blank, auto-generated.",
          })}
          style={{ width: "100%", marginBottom: 8 }}
          disabled={imageGenerating}
        />
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => {
              setImagePromptDraft(buildScenePromptFromCurrentChat());
              setImageNegativePromptDraft(buildSceneNegativePromptFromCurrentChat());
            }}
            disabled={imageGenerating}
          >
            {t({ ja: "会話からプロンプト作成", en: "Build prompt from chat" })}
          </button>
          <button
            type="button"
            className="btn btn-border"
            onClick={generateChatSceneImage}
            disabled={imageGenerating}
          >
            {imageGenerating
              ? t({ ja: "画像生成中...", en: "Generating image..." })
              : t({ ja: "画像生成", en: "Generate image" })}
          </button>
        </div>
        <div style={{ marginTop: 8, fontSize: "0.8rem", color: "#5f6675" }}>
          {t({ ja: "生成元", en: "Source" })}:{" "}
          <a
            href="https://gazou.shosetsu-toukou-site.org/"
            target="_blank"
            rel="noreferrer"
            style={{ color: "var(--accent)", textDecoration: "underline" }}
          >
            https://gazou.shosetsu-toukou-site.org/
          </a>
        </div>
      </div>
      <div style={{ marginTop: -2, marginBottom: 10 }}>
        <div style={{ fontSize: "0.84rem", color: "#5f6675", marginBottom: 6 }}>
          {t({ ja: "次に言いそうなセリフ候補（3件）", en: "Likely next lines (3 suggestions)" })}: {selectedSpeakerBubbles.name}
        </div>
        <div style={{ display: "grid", gap: 8 }}>
          {selectedSpeakerBubbles.bubbles.map((line, idx) => {
            const normalizedLine = compactText(line);
            const canSend = normalizedLine
              && normalizedLine !== "「……」"
              && normalizedLine !== "候補を生成中…"
              && normalizedLine !== "Generating suggestions...";
            return (
              <div
                key={`selected-line-${idx}`}
                style={{
                  maxWidth: "86%",
                  borderRadius: 14,
                  padding: "8px 10px 8px 12px",
                  background: "#1f4788",
                  border: "1px solid #2e5ca8",
                  color: "#f5f1e8",
                  whiteSpace: "pre-wrap",
                  lineHeight: 1.5,
                  display: "flex",
                  alignItems: "flex-end",
                  justifyContent: "space-between",
                  gap: 10,
                }}
              >
                <div style={{ flex: 1 }}>{line}</div>
                <button
                  type="button"
                  className="btn btn-border bubble-send-btn"
                  onClick={() => sendSelectedBubbleLine(line)}
                  disabled={loading || !canSend}
                  aria-label={t({ ja: "このセリフを送信", en: "Send this line" })}
                >
                  <FontAwesomeIcon icon={faPaperPlane} />
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {guestMigrationInfo && (
        <p style={{ color: guestMigrationRunning ? "#2d5a9e" : "#2e7d32", marginBottom: 8 }}>
          {guestMigrationInfo}
        </p>
      )}
      {error && <p style={{ color: "crimson", marginBottom: 8 }}>{error}</p>}
      {latestPromptPreview && (
        <div style={{ marginBottom: 10, border: "1px solid #d9d9d9", borderRadius: 8, padding: 10, background: "#fcfcfc" }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>
            {t({ ja: "最新ログから再構築した GPT 送信情報", en: "GPT payload reconstructed from latest logs" })}
          </div>
          <div style={{ fontSize: "0.9rem", marginBottom: 8 }}>
            {t({ ja: "モード", en: "Mode" })}: {latestPromptPreview.mode} / ID: {latestPromptPreview.source_message_id}
            {latestPromptPreview.language_style ? ` / Style: ${latestPromptPreview.language_style}` : ""}
          </div>
          <details open>
            <summary style={{ cursor: "pointer", fontWeight: 600 }}>
              {t({ ja: "送信プロンプト", en: "Prompt sent" })}
            </summary>
            <pre style={{ whiteSpace: "pre-wrap", marginTop: 6, background: "#f3f5f9", borderRadius: 6, padding: 8 }}>
              {latestPromptPreview.prompt}
            </pre>
          </details>
          <details>
            <summary style={{ cursor: "pointer", fontWeight: 600 }}>
              {t({ ja: "System instructions", en: "System instructions" })}
            </summary>
            <pre style={{ whiteSpace: "pre-wrap", marginTop: 6, background: "#f3f5f9", borderRadius: 6, padding: 8 }}>
              {latestPromptPreview.system_instructions}
            </pre>
          </details>
          {latestPromptPreview.long_term_memories_text ? (
            <details>
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>
                {t({ ja: "長期メモリ", en: "Long-term memories" })}
              </summary>
              <pre style={{ whiteSpace: "pre-wrap", marginTop: 6, background: "#f3f5f9", borderRadius: 6, padding: 8 }}>
                {latestPromptPreview.long_term_memories_text}
              </pre>
            </details>
          ) : null}
          {latestPromptPreview.summary_text ? (
            <details>
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>
                {t({ ja: "会話要約", en: "Conversation summary" })}
              </summary>
              <pre style={{ whiteSpace: "pre-wrap", marginTop: 6, background: "#f3f5f9", borderRadius: 6, padding: 8 }}>
                {latestPromptPreview.summary_text}
              </pre>
            </details>
          ) : null}
          <details>
            <summary style={{ cursor: "pointer", fontWeight: 600 }}>
              {t({ ja: "履歴（最大20件）", en: "History (up to 20)" })}
            </summary>
            <pre style={{ whiteSpace: "pre-wrap", marginTop: 6, background: "#f3f5f9", borderRadius: 6, padding: 8 }}>
              {JSON.stringify(latestPromptPreview.history || [], null, 2)}
            </pre>
          </details>
        </div>
      )}
      {lastRequest && (
        <div
          style={{
            marginBottom: 10,
            padding: 10,
            border: isResending ? "1px solid #3a79b7" : "1px solid #d8d8d8",
            borderRadius: 8,
            background: isResending ? "#eef6ff" : "#fafafa",
          }}
        >
          <div style={{ fontSize: "0.9rem", fontWeight: 700, marginBottom: 6 }}>
            {t({ ja: "再送メッセージ（編集可）", en: "Resend message (editable)" })}
          </div>
          {isResending && (
            <div
              style={{
                marginBottom: 8,
                fontSize: "0.88rem",
                color: "#235a93",
                fontWeight: 700,
              }}
            >
              {t({ ja: "再送を送信中です...", en: "Resend is being sent..." })}
            </div>
          )}
          <textarea
            value={resendDraft}
            onChange={(e) => setResendDraft(e.target.value)}
            rows={2}
            style={{ width: "100%", marginBottom: 8 }}
            disabled={loading}
          />
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              className={resendMode === "say" ? "btn btn-border" : "btn"}
              onClick={() => setResendMode("say")}
              disabled={loading}
            >
              {t({ ja: "sayで再送", en: "Resend as say" })}
            </button>
            <button
              type="button"
              className={resendMode === "do" ? "btn btn-border" : "btn"}
              onClick={() => setResendMode("do")}
              disabled={loading}
            >
              {t({ ja: "doで再送", en: "Resend as do" })}
            </button>
            <button
              type="button"
              className="btn btn-border"
              onClick={resendLastRequest}
              disabled={loading || !resendDraft.trim()}
              style={{
                minWidth: 170,
                fontWeight: isResending ? 700 : 400,
              }}
            >
              {isResending
                ? t({ ja: "再送を送信中...", en: "Sending resend..." })
                : t({ ja: "編集内容で再送", en: "Resend edited message" })}
            </button>
          </div>
        </div>
      )}

      <div style={{ marginBottom: 8, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input
          ref={chatImageInputRef}
          type="file"
          accept="image/*"
          multiple
          disabled={loading || chatImageUploading}
          onChange={(e) => {
            const files = Array.from(e.target.files || []);
            setChatImageFiles(files);
          }}
        />
        <button
          type="button"
          className="btn btn-border"
          onClick={uploadAdditionalChatImages}
          disabled={loading || chatImageUploading || chatImageFiles.length === 0}
        >
          {chatImageUploading
            ? t({ ja: "画像を追加中...", en: "Adding images..." })
            : t({ ja: "画像を貼る", en: "Attach images" })}
        </button>
        {chatImageFiles.length > 0 && (
          <span style={{ fontSize: "0.82rem", color: "#5f6675" }}>
            {t({ ja: "選択中", en: "Selected" })}: {chatImageFiles.length}
          </span>
        )}
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="ai-chat-message-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submitChat();
            }
          }}
          placeholder={t({ ja: "メッセージを入力", en: "Type a message" })}
          style={{
            flex: 1,
            background: "var(--surface)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            opacity: 1,
          }}
          disabled={loading}
        />
        <button type="button" className="btn btn-border" onClick={() => submitChat()} disabled={loading || !input.trim()}>
          {loading ? t({ ja: "送信中...", en: "Sending..." }) : t({ ja: "送信", en: "Send" })}
        </button>
      </div>
      <div style={{ marginTop: 8 }}>
        <label style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: "0.92rem" }}>
          <input
            type="checkbox"
            checked={autoDialogue}
            onChange={(e) => setAutoDialogue(e.target.checked)}
            disabled={loading}
            style={{ marginTop: 3 }}
          />
          <span style={{ display: "inline-flex", flexDirection: "column", gap: 2 }}>
            <span>
              {t({
                ja: "自動会話モード（キャラ同士の会話を自動で続ける）",
                en: "Auto dialogue mode (continue character-to-character conversation)",
              })}
            </span>
            <span style={{ fontSize: "0.82rem", color: "var(--muted-text)" }}>
              {t({
                ja: "停止したいときはチャットで「停止」または「止める」と発言してください。",
                en: "To stop, send \"stop\" in chat.",
              })}
            </span>
          </span>
        </label>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
          <span
            aria-live="polite"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: "0.84rem",
              color: autoDialogue ? "#17663a" : "var(--muted-text)",
              fontWeight: autoDialogue ? 700 : 500,
            }}
          >
            <span
              aria-hidden="true"
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: autoDialogue ? "#22c55e" : "#b9c0cc",
                boxShadow: autoDialogue ? "0 0 0 3px rgba(34, 197, 94, 0.2)" : "none",
              }}
            />
            {autoDialogue
              ? t({ ja: "自動会話 ON", en: "Auto dialogue ON" })
              : t({ ja: "自動会話 OFF", en: "Auto dialogue OFF" })}
          </span>
          <button
            type="button"
            className="btn btn-border"
            onClick={() => setAutoDialogue(false)}
            disabled={!autoDialogue}
          >
            {t({ ja: "自動会話を停止", en: "Stop auto dialogue" })}
          </button>
        </div>
      </div>
      <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, fontSize: "0.92rem" }}>
        <input
          type="checkbox"
          checked={longReply}
          onChange={(e) => {
            const checked = e.target.checked;
            setLongReply(checked);
            if (checked) setShortReply(false);
          }}
          disabled={loading}
        />
        <span>
          {t({
            ja: "長めに返信（通常の約2倍の文量）",
            en: "Longer reply (about 2x text length)",
          })}
        </span>
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, fontSize: "0.92rem" }}>
        <input
          type="checkbox"
          checked={shortReply}
          onChange={(e) => {
            const checked = e.target.checked;
            setShortReply(checked);
            if (checked) setLongReply(false);
          }}
          disabled={loading}
        />
        <span>
          {t({
            ja: "短めに返信（一行で簡潔に返す）",
            en: "Short reply (single-line concise response)",
          })}
        </span>
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, fontSize: "0.92rem" }}>
        <input
          type="checkbox"
          checked={dailyTalkMode}
          onChange={(e) => {
            const checked = e.target.checked;
            setDailyTalkMode(checked);
            if (checked) setIq80CrudeMode(false);
          }}
          disabled={loading}
        />
        <span>
          {t({
            ja: "日常会話レベル（やさしい語彙で自然な口語）",
            en: "Daily conversation level (simple and natural wording)",
          })}
        </span>
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, fontSize: "0.92rem" }}>
        <input
          type="checkbox"
          checked={iq80CrudeMode}
          onChange={(e) => {
            const checked = e.target.checked;
            setIq80CrudeMode(checked);
            if (checked) setDailyTalkMode(false);
          }}
          disabled={loading}
        />
        <span>
          {t({
            ja: "下品寄り・IQ80会話（単純で砕けた言い回し）",
            en: "Crude IQ80 style (simple and rough wording)",
          })}
        </span>
      </label>
	      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
	        <button
	          type="button"
	          className={r18Mode ? "btn btn-border" : "btn"}
          onClick={toggleR18Mode}
          disabled={loading || !showR18ByDisplaySetting}
          aria-pressed={r18Mode}
          style={{
            fontWeight: r18Mode ? 700 : 400,
            background: r18Mode ? "#ffe1e1" : undefined,
            borderColor: r18Mode ? "#c53f3f" : undefined,
            color: r18Mode ? "#8a1f1f" : undefined,
          }}
	        >
	          {r18Mode ? "R18: ON" : "R18: OFF"}
	        </button>
	        <span style={{ fontSize: "0.85rem", color: "var(--muted-text)" }}>
	          {!showR18ByDisplaySetting
	            ? t({
	                ja: "マイページ設定でR18作品を非表示にしているため、AIチャットのR18も無効です。",
	                en: "R18 is disabled in AI Chat because it is hidden in My Page display settings.",
	              })
	            : t({
	                ja: "ON時は年齢確認済みとして扱います。",
	                en: "When ON, age confirmation is considered accepted.",
	              })}
	        </span>
	      </div>
      {autoDialogue && (
        <div style={{ marginTop: 4, fontSize: "0.85rem", color: autoContinuing ? "#235a93" : "var(--muted-text)" }}>
          {autoContinuing
            ? t({ ja: "キャラ会話を自動生成中...", en: "Generating auto character dialogue..." })
            : t({ ja: "自動会話が有効です。停止するには停止ボタン、またはチャットで「停止」「止める」を発言してください。", en: "Auto dialogue is active. Use the stop button or send \"stop\" in chat." })}
        </div>
      )}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginTop: 10,
          flexWrap: "wrap",
        }}
      >
        <span
          style={{
            fontSize: "0.9rem",
            padding: "4px 8px",
            borderRadius: 999,
            border: "1px solid #bbb",
            background: mode === "say" ? "#eef7ff" : "#fff6ef",
            color: "#333",
            fontWeight: 700,
          }}
        >
          {mode === "say"
            ? t({ ja: "現在: say（発言）", en: "Current: say (speech)" })
            : t({ ja: "現在: do（行動）", en: "Current: do (action)" })}
        </span>
        <button
          type="button"
          className={`ai-chat-mode-btn ${mode === "say" ? "btn btn-border" : "btn"}`}
          onClick={() => setMode("say")}
          disabled={loading}
          aria-pressed={mode === "say"}
          style={{
            fontWeight: mode === "say" ? 700 : 400,
            background: mode === "say" ? "var(--ai-chat-say-active-bg)" : undefined,
            borderColor: mode === "say" ? "#4a87c2" : undefined,
          }}
        >
          {t({ ja: "say（発言）", en: "say (speech)" })}
        </button>
        <button
          type="button"
          className={`ai-chat-mode-btn ${mode === "do" ? "btn btn-border" : "btn"}`}
          onClick={() => setMode("do")}
          disabled={loading}
          aria-pressed={mode === "do"}
          style={{
            fontWeight: mode === "do" ? 700 : 400,
            background: mode === "do" ? "var(--ai-chat-do-active-bg)" : undefined,
            borderColor: mode === "do" ? "#cf7a24" : undefined,
          }}
        >
          {t({ ja: "do（行動）", en: "do (action)" })}
        </button>
      </div>
      <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn btn-border"
          onClick={saveCharacter}
          disabled={loading || augmentLoading}
        >
          {t({ ja: "キャラ登録/更新", en: "Save/Update character" })}
        </button>
        <span style={{ fontSize: "0.82rem", color: "var(--muted-text)" }}>
          {t({
            ja: "保存済みキャラを選択中は会話履歴を自動で継続保存します。",
            en: "While a saved character is selected, chat history is continuously auto-saved.",
          })}
        </span>
      </div>
    </div>
    </>
  );
}
