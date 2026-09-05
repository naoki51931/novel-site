import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";

type ConsultationMessage = {
  role: "user" | "assistant";
  content: string;
};

type ConsultationSession = {
  id: string;
  title: string;
  messages: ConsultationMessage[];
  createdAt: string;
  updatedAt: string;
};

type ConsultationAccessStatus = {
  is_guest: boolean;
  is_premium: boolean;
  used_tokens: number;
  allowed_tokens: number;
  remaining_tokens: number;
  free_tokens: number;
  guest_tokens: number;
  premium_tokens: number;
  needs_upgrade: boolean;
};

const LEGACY_MESSAGES_KEY = "ai_consultation_messages_v1";
const SESSIONS_KEY = "ai_consultation_sessions_v1";
const RETRY_ON_EMPTY_KEY = "ai_consultation_retry_on_empty_v1";
const RETRY_ON_EMPTY_COUNT_KEY = "ai_consultation_retry_on_empty_count_v1";
const RETRY_ON_EMPTY_MAX = 5;
const AI_NOVEL_DRAFT_KEY = "draft_ai_novel_v1";
const AUTO_AI_NOVEL_MODEL_VALUE = "__auto__";
const AI_NOVEL_RETRY_SETTINGS_VERSION = 2;
const SEGMENT_TARGET_CHARS = 2000;
const SEGMENT_COUNT_MAX = 60;
const MODEL_OPTIONS = [
  { value: "", ja: "自動", en: "Auto" },
  { value: "openai/gpt-chat-latest", ja: "ChatGPT", en: "ChatGPT" },
  { value: "google/gemini-2.5-flash", ja: "Gemini Flash", en: "Gemini Flash" },
  { value: "deepseek/deepseek-chat", ja: "DeepSeek", en: "DeepSeek" },
];

const NOVEL_MODEL_OPTIONS = [
  { value: AUTO_AI_NOVEL_MODEL_VALUE, ja: "自動（既定モデル）", en: "Auto (default model)" },
  { value: "local-qwen3-8b-nsfw-jp", ja: "ローカル Qwen3 8B", en: "Local Qwen3 8B" },
  { value: "local-doujinshi-14b", ja: "ローカル Doujinshi 14B", en: "Local Doujinshi 14B" },
  { value: "local-llama3-jprp-8b", ja: "ローカル Llama3 JPRP 8B", en: "Local Llama3 JPRP 8B" },
  { value: "gpt-5.2", ja: "GPT-5.2（最高品質）", en: "GPT-5.2 (highest quality)" },
  { value: "gpt-5", ja: "GPT-5（高品質）", en: "GPT-5 (high quality)" },
  { value: "gpt-5-mini", ja: "GPT-5 Mini（推奨・高速）", en: "GPT-5 Mini (recommended, fast)" },
  { value: "gpt-4.1-mini", ja: "GPT-4.1 Mini（高速・低コスト）", en: "GPT-4.1 Mini (fast, low cost)" },
  { value: "gpt-4.1", ja: "GPT-4.1（高品質）", en: "GPT-4.1 (high quality)" },
  { value: "openai/gpt-chat-latest", ja: "ChatGPT（OpenRouter）", en: "ChatGPT (OpenRouter)" },
  { value: "google/gemini-2.5-flash", ja: "Gemini 2.5 Flash", en: "Gemini 2.5 Flash" },
  { value: "deepseek/deepseek-chat", ja: "DeepSeek Chat", en: "DeepSeek Chat" },
];

function normalizeMessages(value: unknown): ConsultationMessage[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item) => item && (item.role === "user" || item.role === "assistant") && typeof item.content === "string")
    .map((item) => ({ role: item.role, content: item.content }))
    .slice(-40);
}

function createSessionId() {
  return `consult_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function createSessionTitle(question: string) {
  const normalized = question.replace(/\s+/g, " ").trim();
  if (!normalized) return "新しい相談";
  return normalized.length > 32 ? `${normalized.slice(0, 32)}...` : normalized;
}

function loadSessions(): ConsultationSession[] {
  try {
    if (typeof window === "undefined") return [];
    const raw = localStorage.getItem(SESSIONS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (Array.isArray(parsed)) {
      const sessions = parsed
        .filter((item) => item && typeof item.id === "string")
        .map((item) => ({
          id: item.id,
          title: String(item.title || "過去の相談").trim() || "過去の相談",
          messages: normalizeMessages(item.messages),
          createdAt: String(item.createdAt || item.updatedAt || new Date().toISOString()),
          updatedAt: String(item.updatedAt || item.createdAt || new Date().toISOString()),
        }))
        .filter((item) => item.messages.length > 0)
        .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
        .slice(0, 30);
      if (sessions.length > 0) return sessions;
    }

    const legacyRaw = localStorage.getItem(LEGACY_MESSAGES_KEY);
    const legacyMessages = normalizeMessages(legacyRaw ? JSON.parse(legacyRaw) : []);
    if (legacyMessages.length === 0) return [];
    const firstUser = legacyMessages.find((item) => item.role === "user")?.content || "過去の相談";
    const now = new Date().toISOString();
    return [{ id: createSessionId(), title: createSessionTitle(firstUser), messages: legacyMessages, createdAt: now, updatedAt: now }];
  } catch {
    return [];
  }
}

function saveSessions(sessions: ConsultationSession[]) {
  try {
    if (typeof window === "undefined") return;
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions.slice(0, 30)));
  } catch {
    // ignore
  }
}

function loadRetryOnEmpty() {
  try {
    if (typeof window === "undefined") return true;
    const raw = localStorage.getItem(RETRY_ON_EMPTY_KEY);
    return raw == null ? true : raw === "1";
  } catch {
    return true;
  }
}

function loadRetryOnEmptyCount() {
  try {
    if (typeof window === "undefined") return 1;
    const raw = Number(localStorage.getItem(RETRY_ON_EMPTY_COUNT_KEY) || 1);
    return Math.max(1, Math.min(RETRY_ON_EMPTY_MAX, Math.floor(raw || 1)));
  } catch {
    return 1;
  }
}

function isEmptyReplyError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error || "");
  return (
    message.includes("AI相談室から返答を取得できませんでした") ||
    message.includes("AI Consultation did not return a reply") ||
    message.includes("AI Consultation did not return")
  );
}

function normalizeAccessStatus(value: unknown): ConsultationAccessStatus | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  const used = Math.max(0, Math.floor(Number(item.used_tokens) || 0));
  const allowed = Math.max(0, Math.floor(Number(item.allowed_tokens) || 0));
  const remaining = Math.max(0, Math.floor(Number(item.remaining_tokens ?? allowed - used) || 0));
  return {
    is_guest: Boolean(item.is_guest),
    is_premium: Boolean(item.is_premium),
    used_tokens: used,
    allowed_tokens: allowed,
    remaining_tokens: remaining,
    free_tokens: Math.max(0, Math.floor(Number(item.free_tokens) || 0)),
    guest_tokens: Math.max(0, Math.floor(Number(item.guest_tokens) || 0)),
    premium_tokens: Math.max(0, Math.floor(Number(item.premium_tokens) || 0)),
    needs_upgrade: Boolean(item.needs_upgrade),
  };
}

function formatTokens(value: number) {
  return Math.max(0, Math.floor(Number(value) || 0)).toLocaleString();
}

function buildIdeaText(input: string, messages: ConsultationMessage[]) {
  const trimmedInput = input.trim();
  if (trimmedInput) return trimmedInput;
  return messages
    .slice(-12)
    .map((message) => {
      const role = message.role === "assistant" ? "AI相談室" : "ユーザー";
      return `【${role}】\n${message.content.trim()}`;
    })
    .filter((item) => item.trim())
    .join("\n\n")
    .trim();
}

function extractChapterPlans(idea: string) {
  const lines = idea.replace(/\r\n?/g, "\n").split("\n");
  const headingPattern = /^\s*(?:#{1,3}\s*)?(?:第\s*[0-9０-９一二三四五六七八九十百千]+\s*[章話幕部]|(?:chapter|chap\.)\s*[0-9０-９]+|[0-9０-９]+\s*[.)．、]\s*.+)\s*$/i;
  const headings: Array<{ index: number; title: string }> = [];
  lines.forEach((line, index) => {
    const title = line.trim();
    if (title && headingPattern.test(title)) {
      headings.push({ index, title: title.replace(/^#{1,3}\s*/, "") });
    }
  });
  if (headings.length < 2) return [];
  return headings.slice(0, SEGMENT_COUNT_MAX).map((heading, index) => {
    const next = headings[index + 1];
    const body = lines.slice(heading.index + 1, next ? next.index : lines.length).join("\n").trim();
    const instruction = body ? `${heading.title}: ${body}` : heading.title;
    return {
      id: `consult-novel-block-${Date.now()}-${index}-${Math.random().toString(36).slice(2, 8)}`,
      instruction: instruction.slice(0, 1800),
    };
  });
}

function createNovelDraftFromIdea(idea: string, model: string) {
  const chapterPlans = extractChapterPlans(idea);
  const chunked = chapterPlans.length >= 2;
  const titleSource = idea.split("\n").map((line) => line.trim()).find(Boolean) || "AI相談室のアイデア";
  const titleHint = titleSource.replace(/^#{1,6}\s*/, "").slice(0, 80);
  const now = new Date().toISOString();
  return {
    titleHint,
    genre: "",
    characters: `AI相談室から持ち込んだアイデアです。以下を元に小説として構成して執筆してください。\n\n${idea}`,
    tone: "",
    length: chunked ? String(chapterPlans.length * SEGMENT_TARGET_CHARS) : "medium",
    model: model || AUTO_AI_NOVEL_MODEL_VALUE,
    isR18: false,
    retryMode: true,
    retryMax: 30,
    retrySettingsVersion: AI_NOVEL_RETRY_SETTINGS_VERSION,
    chunkedGenerationEnabled: chunked,
    chunkedGenerationCount: chunked ? chapterPlans.length : 2,
    chunkedGenerationPlans: chunked
      ? chapterPlans
      : [
          { id: `consult-novel-block-${Date.now()}-1`, instruction: "導入から自然に展開する。" },
          { id: `consult-novel-block-${Date.now()}-2`, instruction: "前半を受けて結末または次章へつながる展開を書く。" },
        ],
    aiCreatedPlotApplied: chunked,
    aiPlotSuggestionRetryThreshold: 5,
    isContinueMode: false,
    episodeId: null,
    continueNovelId: null,
    continueEpisodeNumber: null,
    isEditMode: false,
    editSourceBody: "",
    editEpisodeId: null,
    result: null,
    uploadedTextFileInfo: null,
    continuationBody: "",
    postEpisodeTitle: "",
    lastGenerateParams: null,
    lastPolishScope: "full",
    revisionCommentInput: "",
    revisionChatScope: "full",
    revisionComments: [],
    commentRevisionUndoStack: [],
    commentRevisionHasActiveDiff: false,
    commentRevisionLivePreviewEnabled: false,
    source: "ai_consultation",
    updatedAt: now,
  };
}

export default function AIConsultationPage() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<ConsultationSession[]>(() => loadSessions());
  const [activeSessionId, setActiveSessionId] = useState("");
  const [initialSessionSelected, setInitialSessionSelected] = useState(false);
  const [input, setInput] = useState("");
  const [model, setModel] = useState("");
  const [novelModel, setNovelModel] = useState(AUTO_AI_NOVEL_MODEL_VALUE);
  const [retryOnEmpty, setRetryOnEmpty] = useState(() => loadRetryOnEmpty());
  const [retryOnEmptyCount, setRetryOnEmptyCount] = useState(() => loadRetryOnEmptyCount());
  const [accessStatus, setAccessStatus] = useState<ConsultationAccessStatus | null>(null);
  const [accessLoading, setAccessLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const activeSession = sessions.find((item) => item.id === activeSessionId) || null;
  const messages = activeSession?.messages || [];
  const canSend = input.trim().length > 0 && !loading;
  const ideaText = useMemo(() => buildIdeaText(input, messages), [input, messages]);
  const chapterPlanCount = useMemo(() => extractChapterPlans(ideaText).length, [ideaText]);
  const canStartNovelGeneration = ideaText.trim().length > 0 && !loading;
  const recentHistory = useMemo(() => messages.slice(-12), [messages]);

  useEffect(() => {
    saveSessions(sessions);
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [sessions]);

  useEffect(() => {
    if (initialSessionSelected) return;
    setInitialSessionSelected(true);
    if (!activeSessionId && sessions.length > 0) {
      setActiveSessionId(sessions[0].id);
    }
  }, [activeSessionId, initialSessionSelected, sessions]);

  useEffect(() => {
    try {
      if (typeof window !== "undefined") {
        localStorage.setItem(RETRY_ON_EMPTY_KEY, retryOnEmpty ? "1" : "0");
      }
    } catch {
      // ignore
    }
  }, [retryOnEmpty]);

  useEffect(() => {
    try {
      if (typeof window !== "undefined") {
        localStorage.setItem(RETRY_ON_EMPTY_COUNT_KEY, String(retryOnEmptyCount));
      }
    } catch {
      // ignore
    }
  }, [retryOnEmptyCount]);

  useEffect(() => {
    let cancelled = false;
    setAccessLoading(true);
    apiFetch("/api/ai/consultation/access", { auth: true })
      .then((data) => {
        if (!cancelled) setAccessStatus(normalizeAccessStatus(data));
      })
      .catch(() => {
        if (!cancelled) setAccessStatus(null);
      })
      .finally(() => {
        if (!cancelled) setAccessLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const upsertSession = (sessionId: string, title: string, nextMessages: ConsultationMessage[]) => {
    const now = new Date().toISOString();
    setSessions((prev) => {
      const existing = prev.find((item) => item.id === sessionId);
      const nextSession: ConsultationSession = {
        id: sessionId,
        title: title || existing?.title || "新しい相談",
        messages: nextMessages.slice(-40),
        createdAt: existing?.createdAt || now,
        updatedAt: now,
      };
      return [nextSession, ...prev.filter((item) => item.id !== sessionId)].slice(0, 30);
    });
    setActiveSessionId(sessionId);
  };

  const handleNewSession = () => {
    setActiveSessionId("");
    setInput("");
    setError("");
  };

  const handleDeleteSession = () => {
    if (!activeSessionId || loading) return;
    setSessions((prev) => prev.filter((item) => item.id !== activeSessionId));
    setActiveSessionId("");
    setError("");
  };

  const handleStartNovelFromIdea = () => {
    const idea = ideaText.trim();
    if (!idea || loading) return;
    const draft = createNovelDraftFromIdea(idea, novelModel);
    try {
      localStorage.setItem(AI_NOVEL_DRAFT_KEY, JSON.stringify(draft));
      setError("");
      navigate("/ai-novel?mode=new_novel");
    } catch {
      setError(t({ ja: "小説生成用の下書きを保存できませんでした。", en: "Could not save the draft for novel generation." }));
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    const sessionId = activeSessionId || createSessionId();
    const sessionTitle = activeSession?.title || createSessionTitle(question);
    const userMessage: ConsultationMessage = { role: "user", content: question };
    const nextMessages = [...messages, userMessage].slice(-40);
    upsertSession(sessionId, sessionTitle, nextMessages);
    setInput("");
    setError("");
    setLoading(true);

    try {
      const retryCount = Math.max(1, Math.min(RETRY_ON_EMPTY_MAX, Math.floor(Number(retryOnEmptyCount) || 1)));
      const maxAttempts = retryOnEmpty ? retryCount + 1 : 1;
      let reply = "";
      let lastError: unknown = null;
      for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        try {
          const data = await apiFetch("/api/ai/consultation/chat", {
            method: "POST",
            auth: true,
            body: {
              message: question,
              history: recentHistory,
              model: model || null,
            },
          });
          const nextAccessStatus = normalizeAccessStatus({
            is_guest: accessStatus?.is_guest || false,
            is_premium: accessStatus?.is_premium || false,
            used_tokens: data?.monthly_used_tokens,
            allowed_tokens: data?.monthly_allowed_tokens,
            remaining_tokens: data?.monthly_remaining_tokens,
            free_tokens: accessStatus?.free_tokens || 0,
            guest_tokens: accessStatus?.guest_tokens || 0,
            premium_tokens: accessStatus?.premium_tokens || 0,
            needs_upgrade: Number(data?.monthly_remaining_tokens) <= 0,
          });
          if (nextAccessStatus) setAccessStatus(nextAccessStatus);
          reply = String(data?.reply || "").trim();
          if (reply) break;
          throw new Error(t({ ja: "AI相談室から返答を取得できませんでした。", en: "AI Consultation did not return a reply." }));
        } catch (attemptError) {
          lastError = attemptError;
          if (!(retryOnEmpty && attempt < maxAttempts && isEmptyReplyError(attemptError))) {
            throw attemptError;
          }
          setError(t({ ja: `空返答だったため、同じ質問を再送しています...（${attempt}/${retryCount}）`, en: `The reply was empty, so the same question is being retried... (${attempt}/${retryCount})` }));
        }
      }
      if (!reply) {
        throw lastError || new Error(t({ ja: "AI相談室から返答を取得できませんでした。", en: "AI Consultation did not return a reply." }));
      }
      upsertSession(sessionId, sessionTitle, [...nextMessages, { role: "assistant", content: reply }]);
      setError("");
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "AI相談室への送信に失敗しました。", en: "Failed to send to AI Consultation." })));
      const rollbackMessages = messages.slice(-40);
      if (rollbackMessages.length > 0) {
        upsertSession(sessionId, sessionTitle, rollbackMessages);
      } else {
        setSessions((prev) => prev.filter((item) => item.id !== sessionId));
        setActiveSessionId("");
      }
      setInput(question);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 1080, margin: "0 auto", padding: "8px 0 32px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>{t({ ja: "AI相談室", en: "AI Consultation" })}</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <select
            className="input"
            value={activeSessionId}
            onChange={(event) => setActiveSessionId(event.target.value)}
            aria-label={t({ ja: "履歴", en: "History" })}
            disabled={loading || sessions.length === 0}
            style={{ minWidth: 220 }}
          >
            {sessions.length === 0 ? (
              <option value="">{t({ ja: "履歴なし", en: "No history" })}</option>
            ) : (
              sessions.map((session) => (
                <option key={session.id} value={session.id}>
                  {session.title}
                </option>
              ))
            )}
          </select>
          <button type="button" className="btn btn-border" onClick={handleNewSession} disabled={loading}>
            {t({ ja: "新規", en: "New" })}
          </button>
          <button type="button" className="btn btn-border" onClick={handleDeleteSession} disabled={loading || !activeSessionId}>
            {t({ ja: "削除", en: "Delete" })}
          </button>
          <select
            className="input"
            value={model}
            onChange={(event) => setModel(event.target.value)}
            aria-label={t({ ja: "相談モデル", en: "Consultation model" })}
            title={t({ ja: "相談モデル", en: "Consultation model" })}
            style={{ minWidth: 150 }}
          >
            {MODEL_OPTIONS.map((item) => (
              <option key={item.value || "auto"} value={item.value}>
                {lang === "en" ? item.en : item.ja}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ color: accessStatus?.needs_upgrade ? "#9b2c2c" : "#6d6558", fontSize: 13, margin: "-4px 0 12px" }}>
        {accessLoading && !accessStatus
          ? t({ ja: "利用状況を確認中...", en: "Checking usage..." })
          : accessStatus
            ? t({
                ja: `今月のAI相談室: ${formatTokens(accessStatus.used_tokens)} / ${formatTokens(accessStatus.allowed_tokens)} トークン（残り ${formatTokens(accessStatus.remaining_tokens)}）`,
                en: `AI Consultation this month: ${formatTokens(accessStatus.used_tokens)} / ${formatTokens(accessStatus.allowed_tokens)} tokens (${formatTokens(accessStatus.remaining_tokens)} left)`,
              })
            : t({ ja: "利用状況を取得できませんでした。", en: "Could not load usage status." })}
      </div>

      <div
        style={{
          minHeight: 420,
          maxHeight: "calc(100vh - 300px)",
          overflowY: "auto",
          border: "1px solid #ded7c8",
          borderRadius: 8,
          background: "#fffdf8",
          padding: 16,
        }}
      >
        {messages.length === 0 ? (
          <div style={{ color: "#6d6558", padding: "120px 16px", textAlign: "center" }}>
            {t({ ja: "質問を入力してください。", en: "Enter a question." })}
          </div>
        ) : (
          messages.map((message, index) => {
            const isUser = message.role === "user";
            return (
              <div
                key={`${message.role}-${index}`}
                style={{
                  display: "flex",
                  justifyContent: isUser ? "flex-end" : "flex-start",
                  marginBottom: 12,
                }}
              >
                <div
                  style={{
                    maxWidth: "min(760px, 86%)",
                    border: "1px solid " + (isUser ? "#b9d3c2" : "#ddd3c2"),
                    background: isUser ? "#effaf2" : "#ffffff",
                    borderRadius: 8,
                    padding: "10px 12px",
                    whiteSpace: "pre-wrap",
                    lineHeight: 1.75,
                    overflowWrap: "anywhere",
                  }}
                >
                  <div style={{ fontSize: 12, color: "#6d6558", marginBottom: 4 }}>
                    {isUser ? t({ ja: "あなた", en: "You" }) : t({ ja: "AI相談室", en: "AI Consultation" })}
                  </div>
                  {message.content}
                </div>
              </div>
            );
          })
        )}
        {loading && (
          <div style={{ color: "#6d6558", padding: "4px 0" }}>
            {t({ ja: "回答中...", en: "Answering..." })}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}

      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginTop: 12 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8, color: "#4f4638", fontSize: 14 }}>
          <input
            type="checkbox"
            checked={retryOnEmpty}
            onChange={(event) => setRetryOnEmpty(event.target.checked)}
            disabled={loading}
          />
          {t({ ja: "空返答時に再試行", en: "Retry empty replies" })}
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, color: "#4f4638", fontSize: 14 }}>
          {t({ ja: "回数", en: "Attempts" })}
          <input
            className="input"
            type="number"
            min={1}
            max={RETRY_ON_EMPTY_MAX}
            value={retryOnEmptyCount}
            onChange={(event) => {
              const value = Math.max(1, Math.min(RETRY_ON_EMPTY_MAX, Math.floor(Number(event.target.value) || 1)));
              setRetryOnEmptyCount(value);
            }}
            disabled={loading || !retryOnEmpty}
            style={{ width: 76, padding: "6px 8px" }}
          />
        </label>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
        <select
          className="input"
          value={novelModel}
          onChange={(event) => setNovelModel(event.target.value)}
          aria-label={t({ ja: "小説生成モデル", en: "Novel generation model" })}
          title={t({ ja: "小説生成モデル", en: "Novel generation model" })}
          disabled={loading}
          style={{ minWidth: 220 }}
        >
          {NOVEL_MODEL_OPTIONS.map((item) => (
            <option key={item.value} value={item.value}>
              {lang === "en" ? item.en : item.ja}
            </option>
          ))}
        </select>
        <button type="button" className="btn btn-border" onClick={handleStartNovelFromIdea} disabled={!canStartNovelGeneration}>
          {t({ ja: "このアイデアから小説生成", en: "Generate novel from this idea" })}
        </button>
        {chapterPlanCount >= 2 && (
          <span style={{ color: "#6d6558", fontSize: 13 }}>
            {t(
              { ja: "章見出しを検出: {{count}}ブロックで生成", en: "Detected chapter headings: {{count}} blocks" },
              { count: chapterPlanCount }
            )}
          </span>
        )}
      </div>

      <form onSubmit={handleSubmit} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 10, marginTop: 12, alignItems: "end" }}>
        <textarea
          className="input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          rows={3}
          enterKeyHint="enter"
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.stopPropagation();
            }
          }}
          maxLength={12000}
          placeholder={t({ ja: "AI相談室に質問", en: "Ask AI Consultation" })}
          style={{ resize: "vertical", minHeight: 76, lineHeight: 1.6 }}
        />
        <button type="submit" className="btn btn-primary" disabled={!canSend} style={{ minWidth: 96, height: 44 }}>
          {loading ? t({ ja: "送信中", en: "Sending" }) : t({ ja: "送信", en: "Send" })}
        </button>
      </form>
    </div>
  );
}
