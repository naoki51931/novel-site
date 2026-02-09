import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faPaperPlane } from "@fortawesome/free-regular-svg-icons";
import { useI18n } from "../lib/i18n";

const AI_CHAT_CHARACTER_NAME_KEY = "ai_chat_character_name_v1";
const AI_CHAT_PERSONALITY_KEY = "ai_chat_personality_v1";
const AI_CHAT_RELATIONSHIP_MEMO_HISTORY_KEY = "ai_chat_relationship_memo_history_v1";
const AUTO_DIALOGUE_STOP_WORDS = ["停止", "止める", "ストップ", "stop"];
const PREVIEW_BUBBLE_COUNT = 3;

const AI_MODELS = [
  { value: "gpt-4.1-mini", labelJa: "GPT-4.1 mini（OpenAI）", labelEn: "GPT-4.1 mini (OpenAI)" },
  { value: "openai/chatgpt-4o-latest", labelJa: "ChatGPT（OpenRouter）", labelEn: "ChatGPT (OpenRouter)" },
  { value: "z-ai/glm-4.6", labelJa: "GLM 4.6（OpenRouter）", labelEn: "GLM 4.6 (OpenRouter)" },
  { value: "moonshotai/kimi-k2", labelJa: "Kimi（OpenRouter）", labelEn: "Kimi (OpenRouter)" },
  { value: "deepseek/deepseek-chat", labelJa: "DeepSeek（OpenRouter）", labelEn: "DeepSeek (OpenRouter)" },
  { value: "deepseek:deepseek-chat", labelJa: "DeepSeek（公式）", labelEn: "DeepSeek (official)" },
];

function modelProvider(model) {
  if (!model) return "openai";
  if (model.startsWith("deepseek:")) return "deepseek";
  return model.includes("/") ? "openrouter" : "openai";
}

function normalizeSpeakerName(name) {
  return String(name || "").trim();
}

function compactText(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
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

export default function AiChatPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [model, setModel] = useState("gpt-4.1-mini");
  const [characterName, setCharacterName] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem(AI_CHAT_CHARACTER_NAME_KEY) || "";
  });
  const [personality, setPersonality] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem(AI_CHAT_PERSONALITY_KEY) || "";
  });
  const [mainSpeechGender, setMainSpeechGender] = useState("auto");
  const [mode, setMode] = useState("say");
  const [autoDialogue, setAutoDialogue] = useState(false);
  const [longReply, setLongReply] = useState(false);
  const [shortReply, setShortReply] = useState(false);
  const [dailyTalkMode, setDailyTalkMode] = useState(false);
  const [iq80CrudeMode, setIq80CrudeMode] = useState(false);
  const [r18Mode, setR18Mode] = useState(false);
  const [fanficMode, setFanficMode] = useState(false);
  const [augmentLoading, setAugmentLoading] = useState(false);
  const [augmentNotes, setAugmentNotes] = useState("");
  const [castCharacters, setCastCharacters] = useState([]);
  const [userSpeakerKey, setUserSpeakerKey] = useState("you");
  const [randomSpeakerKeys, setRandomSpeakerKeys] = useState(["main"]);
  const [autoCharacterMode, setAutoCharacterMode] = useState(false);
  const [autoRandomSpeakerKeys, setAutoRandomSpeakerKeys] = useState(["main"]);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [selectedMessageIndex, setSelectedMessageIndex] = useState(null);
  const [loading, setLoading] = useState(false);
  const [autoContinuing, setAutoContinuing] = useState(false);
  const [error, setError] = useState("");
  const [isResending, setIsResending] = useState(false);
  const [creatingNovelFromChat, setCreatingNovelFromChat] = useState(false);
  const [lastRequest, setLastRequest] = useState(null);
  const [resendDraft, setResendDraft] = useState("");
  const [resendMode, setResendMode] = useState("say");
  const [savedCharacters, setSavedCharacters] = useState([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState("");
  const [charactersLoading, setCharactersLoading] = useState(false);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [chatAccess, setChatAccess] = useState(null);
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
  const [relationshipMemoHistory, setRelationshipMemoHistory] = useState(() => {
    if (typeof window === "undefined") return [];
    try {
      const raw = localStorage.getItem(AI_CHAT_RELATIONSHIP_MEMO_HISTORY_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed)
        ? parsed.map((v) => String(v || "").trim()).filter(Boolean).slice(0, 30)
        : [];
    } catch {
      return [];
    }
  });
  const fanficCacheRef = useRef(new Map());

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

  const historyPayload = useMemo(
    () =>
      messages.slice(-20).map((m) => ({
        role: m.role,
        content: m.speaker_name ? `[${m.speaker_name}] ${m.content}` : m.content,
        mode: m.mode,
      })),
    [messages]
  );
  const selectedCharacter = useMemo(
    () => savedCharacters.find((c) => c.id === selectedCharacterId) || null,
    [savedCharacters, selectedCharacterId]
  );
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
    relationship: "",
    fanfic_mode: true,
    speech_gender: "auto",
  });

  const updateCastCharacter = (key, patch) => {
    setCastCharacters((prev) =>
      prev.map((c) => (c.key === key ? { ...c, ...patch } : c))
    );
  };
  const rememberRelationshipMemo = (text) => {
    const v = compactText(text);
    if (!v) return;
    setRelationshipMemoHistory((prev) => {
      const next = [v, ...prev.filter((item) => item !== v)].slice(0, 30);
      return next;
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
    updateCastCharacter(castKey, {
      saved_id: selected.id,
      name: String(selected.name || "").trim(),
      personality: String(selected.personality || ""),
      speech_gender: normalizeSpeechGender(selected.speech_gender),
    });
  };

  const removeCastCharacter = (key) => {
    setCastCharacters((prev) => prev.filter((c) => c.key !== key));
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
    setCastCharacters((prev) => {
      const original = prev.find((c) => c.key === castKey);
      if (!original) return prev;
      const nextName = buildDuplicatedCastName(
        original.name,
        prev.map((c) => c.name)
      );
      const duplicate = {
        ...original,
        key: `cast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        saved_id: "",
        name: nextName,
      };
      return [...prev, duplicate];
    });
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
      const rel = String(c.relationship || "").trim();
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
    enabled,
    animeTitle = "",
  }) => {
    const normalizedName = String(name || "").trim();
    const normalizedPersonality = String(personalityText || "");
    const normalizedAnimeTitle = String(animeTitle || "").trim();
    if (!enabled) {
      return { characterName: normalizedName, personalityText: normalizedPersonality, notes: "" };
    }
    if (!normalizedName) {
      throw new Error(t({ ja: "二次創作モードではキャラ名が必要です。", en: "Character name is required in fanfic mode." }));
    }
    const cacheKey = `${normalizedName}::${normalizedAnimeTitle}::${normalizedPersonality}`;
    const cached = fanficCacheRef.current.get(cacheKey);
    if (cached?.personalityText) {
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
          model,
          provider: modelProvider(model),
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
    if (!token) {
      setChatAccess(null);
      return;
    }
    try {
      const res = await fetch("/api/ai/chat/access", {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) return;
      setChatAccess(data || null);
    } catch {
      // ignore
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
          model,
          provider: modelProvider(model),
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
    try {
      localStorage.setItem(
        AI_CHAT_RELATIONSHIP_MEMO_HISTORY_KEY,
        JSON.stringify((relationshipMemoHistory || []).slice(0, 30))
      );
    } catch {
      // ignore storage failures
    }
  }, [relationshipMemoHistory]);

  const maybeAugmentCharacterProfile = async ({
    nameOverride,
    personalityOverride,
    force = false,
  } = {}) => {
    const currentName = String((nameOverride ?? characterName) || "").trim();
    const currentPersonality = String((personalityOverride ?? personality) || "");
    if (!fanficMode) {
      return {
        characterName: currentName,
        personalityText: currentPersonality,
      };
    }
    const resolved = await runCharacterAugment({
      name: currentName,
      personalityText: currentPersonality,
      enabled: fanficMode,
      animeTitle: selectedAnimeTitle,
    });
    if (resolved?.animeTitle) {
      setSelectedAnimeTitle(String(resolved.animeTitle || "").trim());
    }
    if (!force && resolved.personalityText && resolved.personalityText !== personality) {
      setPersonality(resolved.personalityText);
    }
    setAugmentNotes(String(resolved.notes || ""));
    return resolved;
  };

  useEffect(() => {
    const token = getStoredAuthToken();
    if (!token) {
      setSavedCharacters([]);
      setSelectedCharacterId("");
      return;
    }

    (async () => {
      try {
        setCharactersLoading(true);
        const res = await fetch("/api/ai/chat/characters", {
          headers: { Authorization: `Bearer ${token}` },
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
            .map((c) => ({
              id: String(c.id),
              name: String(c.name || "").trim(),
              personality: String(c.personality || ""),
              speech_gender: normalizeSpeechGender(c.speech_gender),
              is_public: !!c.is_public,
              published_at: c.published_at || null,
            }))
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
  }, [t]);

  const saveCharacter = () => {
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
        force: true,
      });
      const selected = savedCharacters.find((c) => c.id === selectedCharacterId) || null;
      const shouldUpdateExisting =
        !!selected && selected.name.trim() === name;
      const url = shouldUpdateExisting
        ? `/api/ai/chat/characters/${encodeURIComponent(selectedCharacterId)}`
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
          personality: augmented.personalityText || personality,
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

      const saved = {
        id: String(data.id),
        name: String(data.name || "").trim(),
        personality: String(data.personality || ""),
        speech_gender: normalizeSpeechGender(data.speech_gender),
        is_public: !!data.is_public,
        published_at: data.published_at || null,
      };
      setSavedCharacters((prev) => {
        const without = prev.filter((c) => c.id !== saved.id);
        return [saved, ...without];
      });
      setSelectedCharacterId(saved.id);
      setMainSpeechGender(normalizeSpeechGender(saved.speech_gender));
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

  const applySelectedCharacter = (id) => {
    if (!id) {
      setSelectedCharacterId("");
      setMainSpeechGender("auto");
      setMessages([]);
      setLastRequest(null);
      setResendDraft("");
      setLatestPromptPreview(null);
      return;
    }
    const item = savedCharacters.find((c) => c.id === id);
    if (!item) return;
    setSelectedCharacterId(item.id);
    setCharacterName(item.name || "");
    setPersonality(item.personality || "");
    setMainSpeechGender(normalizeSpeechGender(item.speech_gender));
    setSelectedAnimeTitle("");
    setLatestPromptPreview(null);
    setError("");
  };

  const deleteSelectedCharacter = () => {
    const run = async () => {
      if (!selectedCharacterId) return;
      const token = getStoredAuthToken();
      if (!token) {
        throw new Error(t({ ja: "キャラ削除はログインが必要です。", en: "Login is required to delete characters." }));
      }
      const res = await fetch(`/api/ai/chat/characters/${encodeURIComponent(selectedCharacterId)}`, {
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
      setSavedCharacters((prev) => prev.filter((c) => c.id !== selectedCharacterId));
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
      if (!selectedCharacterId) return;
      const token = getStoredAuthToken();
      if (!token) {
        throw new Error(t({ ja: "公開設定はログインが必要です。", en: "Login is required for publish settings." }));
      }
      const nextPublic = !(selectedCharacter?.is_public || false);
      const res = await fetch(`/api/ai/chat/characters/${encodeURIComponent(selectedCharacterId)}/publish`, {
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
          c.id === selectedCharacterId
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
          force: true,
        });
        if (augmented.characterName && augmented.characterName !== characterName) {
          setCharacterName(augmented.characterName);
        }
        if (augmented.personalityText && augmented.personalityText !== personality) {
          setPersonality(augmented.personalityText);
        }
        return;
      }

      if (selected) {
        setCharacterName(selected.name || "");
        setPersonality(selected.personality || "");
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
      if (!nextName) {
        throw new Error(t({ ja: "キャラ名を入力してください。", en: "Please enter a character name." }));
      }
      // 「性格設定を変更」は入力値をそのまま確定させる。自動補完はここでは行わない。
      if (nextName !== characterName) setCharacterName(nextName);
      if (nextPersonality !== personality) setPersonality(nextPersonality);

      if (!selectedCharacterId) {
        return;
      }
      const token = getStoredAuthToken();
      if (!token) {
        throw new Error(t({ ja: "性格設定の変更はログインが必要です。", en: "Login is required to update personality." }));
      }
      const res = await fetch(`/api/ai/chat/characters/${encodeURIComponent(selectedCharacterId)}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: nextName,
          personality: nextPersonality,
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
      const updated = {
        id: String(data.id || selectedCharacterId),
        name: String(data.name || nextName).trim(),
        personality: String(data.personality || nextPersonality || ""),
        speech_gender: normalizeSpeechGender(data.speech_gender ?? mainSpeechGender),
        is_public: !!data.is_public,
        published_at: data.published_at || null,
      };
      setSavedCharacters((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      setCharacterName(updated.name);
      setPersonality(updated.personality);
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
        enabled: !!cast.fanfic_mode,
        animeTitle: "",
      });
      const method = cast.saved_id ? "PUT" : "POST";
      const url = cast.saved_id
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
          personality: resolved.personalityText || cast.personality || "",
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
      updateCastCharacter(castKey, {
        saved_id: savedId,
        name: String(data.name || resolved.characterName || name).trim(),
        personality: String(data.personality || resolved.personalityText || cast.personality || ""),
        speech_gender: normalizeSpeechGender(data.speech_gender || cast.speech_gender),
      });
      if (savedId) {
        setSavedCharacters((prev) => {
          const normalized = {
            id: savedId,
            name: String(data.name || resolved.characterName || name).trim(),
            personality: String(data.personality || resolved.personalityText || cast.personality || ""),
            speech_gender: normalizeSpeechGender(data.speech_gender || cast.speech_gender),
            is_public: !!data.is_public,
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
    if (!selectedCharacterId || previewLoading) return;
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
        `/api/ai/chat/characters/${encodeURIComponent(selectedCharacterId)}/latest_prompt_preview?${previewParams.toString()}`,
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
      const res = await fetch("/api/ai/chat", {
        method: "POST",
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
          model,
          provider: modelProvider(model),
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
          const next = [...prev, { id: null, role: "assistant", mode: "say", is_auto_dialogue: false, content: reply, speaker_name: characterNameAtSend ?? characterName }];
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
            });
          });
          return next;
        }
        const next = [...prev, { id: null, role: "assistant", mode: "do", is_auto_dialogue: false, content: reply, speaker_name: characterNameAtSend ?? characterName }];
        if (sayText) {
          next.push({ id: null, role: "assistant", mode: "say", is_auto_dialogue: false, content: sayText, speaker_name: characterNameAtSend ?? characterName });
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
        e?.message ||
          t({ ja: "AIチャット中にエラーが発生しました。", en: "AI chat error occurred." })
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
      const res = await fetch("/api/ai/chat/auto_continue", {
        method: "POST",
        headers,
        body: JSON.stringify({
          r18: r18Mode,
          character_id: selectedCharacterId ? Number(selectedCharacterId) : null,
          character_name: assistantName,
          personality: `${assistantPersonality}${buildParticipantsContext(assistantKey)}${buildRoleplayConstraint(assistantName)}${buildSpeechGenderConstraint(assistantName, assistantSpeechGender)}`,
          long_reply: longReply,
          short_reply: shortReply,
          language_style: languageStyle,
          model,
          provider: modelProvider(model),
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
        { id: null, role: "assistant", mode: "say", is_auto_dialogue: true, content: reply, speaker_name: assistantName },
      ]);
      return true;
    } catch (e) {
      setError(
        e?.message ||
          t({ ja: "自動会話中にエラーが発生しました。", en: "An error occurred during auto dialogue." })
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
    const resolvedSpeechGender = String(assistantProfile?.speech_gender || "auto");
    const userSpeakerNameAtSend = String(userSpeakerProfile?.name || characterName || "").trim();
    const activeFanfic = !!assistantProfile?.fanfic_mode;
    try {
      const augmented =
        assistantKey === "main"
          ? await maybeAugmentCharacterProfile({ nameOverride: resolvedCharacterName, personalityOverride: resolvedPersonality })
          : await runCharacterAugment({
              name: resolvedCharacterName,
              personalityText: resolvedPersonality,
              enabled: activeFanfic,
            });
      resolvedCharacterName = augmented.characterName || resolvedCharacterName;
      resolvedPersonality = augmented.personalityText || resolvedPersonality;
      setAugmentNotes(String(augmented.notes || ""));
      if (assistantKey !== "main") {
        updateCastCharacter(assistantKey, {
          name: resolvedCharacterName,
          personality: resolvedPersonality,
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

      if (selectedCharacterId && token && target?.id != null) {
        const res = await fetch(
          `/api/ai/chat/characters/${encodeURIComponent(selectedCharacterId)}/messages/${encodeURIComponent(target.id)}`,
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
      }

      setMessages((prev) => prev.slice(0, selectedMessageIndex));
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
      const resolvedSpeechGender = String(assistantProfile?.speech_gender || "auto");
      const userSpeakerNameAtSend = String(userSpeakerProfile?.name || characterName || "").trim();
      const activeFanfic = !!assistantProfile?.fanfic_mode;
      try {
        const augmented =
          assistantKey === "main"
            ? await maybeAugmentCharacterProfile({ nameOverride: resolvedCharacterName, personalityOverride: resolvedPersonality })
            : await runCharacterAugment({
                name: resolvedCharacterName,
                personalityText: resolvedPersonality,
                enabled: activeFanfic,
              });
        resolvedCharacterName = augmented.characterName || resolvedCharacterName;
        resolvedPersonality = augmented.personalityText || resolvedPersonality;
        setAugmentNotes(String(augmented.notes || ""));
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
      if (!token || !selectedCharacterId) {
      if (!selectedCharacterId) setMessages([]);
      if (!selectedCharacterId) {
        setLastRequest(null);
        setResendDraft("");
      }
      return;
    }

    (async () => {
      try {
        setMessagesLoading(true);
        const res = await fetch(
          `/api/ai/chat/characters/${encodeURIComponent(selectedCharacterId)}/messages`,
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
        const list = Array.isArray(data) ? data : [];
        setMessages(
          list.map((m) => ({
            id: m?.id != null ? Number(m.id) : null,
            role: m?.role === "assistant" ? "assistant" : "user",
            mode: m?.mode === "do" ? "do" : "say",
            is_auto_dialogue: !!m?.is_auto_dialogue,
            content: String(m?.content || ""),
            speaker_name: String(characterName || ""),
          }))
        );
        const lastUser = [...list].reverse().find((m) => (m?.role || "") === "user");
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
      } catch (e) {
        setError(
          e?.message ||
            t({ ja: "チャット履歴の取得中にエラーが発生しました。", en: "Failed to load chat history." })
        );
      } finally {
        setMessagesLoading(false);
      }
    })();
  }, [selectedCharacterId, t, mode]);

  useEffect(() => {
    loadChatAccess();
  }, [selectedCharacterId]);

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
            model,
            provider: modelProvider(model),
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
    model,
    personality,
    r18Mode,
    selectedCharacterId,
    t,
    userSpeakerKey,
    userSpeakerProfile,
  ]);

  const toggleR18Mode = () => {
    if (loading) return;
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

  return (
    <div style={{ maxWidth: 960, margin: "0 auto" }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <Link to="/" className="btn btn-border">{t({ ja: "トップへ", en: "Home" })}</Link>
        <Link to="/ai-novel" className="btn btn-border">{t({ ja: "AI小説", en: "AI Novel" })}</Link>
        <button
          type="button"
          className="btn btn-border"
          onClick={handleCreateNovelFromConversation}
          disabled={loading || creatingNovelFromChat || messages.length < 2}
        >
          {creatingNovelFromChat
            ? t({ ja: "書き出し中...", en: "Exporting..." })
            : t({ ja: "先頭からAI小説化して書き出す", en: "Convert full chat to AI novel" })}
        </button>
        <Link to="/ai_chat/public" className="btn btn-border">
          {t({ ja: "公開チャット検索", en: "Public Chat Search" })}
        </Link>
      </div>
      <h2>{t({ ja: "AIチャット", en: "AI Chat" })}</h2>
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
          {chatAccess.show_premium_prompt && (
            <div style={{ fontSize: "0.9rem", color: "#5b4a1f", marginBottom: chatAccess.needs_upgrade ? 8 : 0 }}>
              {t({
                ja: `無料枠到達以降はプレミアム登録、または${Number(chatAccess.block_tokens || 0).toLocaleString()}トークンごと${Number(chatAccess.block_price_yen || 0).toLocaleString()}円の追加課金で継続できます。`,
                en: `After the free quota, continue with premium or ¥${Number(chatAccess.block_price_yen || 0).toLocaleString()} per extra ${Number(chatAccess.block_tokens || 0).toLocaleString()} tokens.`,
              })}
            </div>
          )}
          {chatAccess.needs_upgrade && !chatAccess.demo_bypass && (
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
              {savedCharacters.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
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
              disabled={!selectedCharacterId}
            >
              {t({ ja: "選択キャラ削除", en: "Delete selected" })}
            </button>
            <button
              type="button"
              className="btn btn-border"
              onClick={togglePublishSelectedCharacter}
              disabled={!selectedCharacterId}
            >
              {selectedCharacter?.is_public
                ? t({ ja: "公開を停止", en: "Unpublish" })
                : t({ ja: "チャットを公開", en: "Publish chat" })}
            </button>
            <button
              type="button"
              className="btn btn-border"
              onClick={loadLatestPromptPreview}
              disabled={!selectedCharacterId || previewLoading}
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
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, fontSize: "0.92rem" }}>
            <input
              type="checkbox"
              checked={fanficMode}
              onChange={(e) => setFanficMode(e.target.checked)}
              disabled={loading || augmentLoading}
            />
            <span>
              {t({
                ja: "二次創作モード（アニメ系のキャラ名を検索して性格設定を自動補完）",
                en: "Fanfic mode (search anime-like character names and auto-augment personality)",
              })}
            </span>
          </label>
          {(augmentLoading || augmentNotes) && (
            <div style={{ marginTop: 4, fontSize: "0.85rem", color: augmentLoading ? "#235a93" : "#666" }}>
              {augmentLoading
                ? t({ ja: "二次創作向けのキャラ設定を補完中...", en: "Augmenting fanfic character profile..." })
                : augmentNotes}
            </div>
          )}
        </label>

        <label>
          {t({ ja: "チャットAI", en: "Chat AI" })}
          <select value={model} onChange={(e) => setModel(e.target.value)} style={{ width: "100%", marginTop: 4 }}>
            {AI_MODELS.map((m) => (
              <option key={m.value} value={m.value}>
                {t({ ja: m.labelJa, en: m.labelEn })}
              </option>
            ))}
          </select>
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
                {savedCharacters.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
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
                rows={2}
                placeholder={t({ ja: "サブキャラの性格設定", en: "Sub character personality" })}
                style={{ width: "100%", marginTop: 6 }}
              />
              <input
                value={cast.relationship || ""}
                onChange={(e) => updateCastCharacter(cast.key, { relationship: e.target.value })}
                onBlur={(e) => rememberRelationshipMemo(e.target.value)}
                placeholder={t({ ja: "関係性メモ（例: 幼なじみ/恋人/師弟）", en: "Relationship note (e.g. childhood friend / partner / mentor)" })}
                list="relationship-memo-history"
                autoComplete="on"
                style={{ width: "100%", marginTop: 6 }}
              />
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
            </div>
          ))}
          <datalist id="relationship-memo-history">
            {relationshipMemoHistory.map((memo, idx) => (
              <option key={`relationship-memo-${idx}`} value={memo} />
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
            rows={3}
            style={{ width: "100%", marginTop: 4 }}
          />
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

      <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 10, minHeight: 260, marginBottom: 10 }}>
        {messagesLoading && (
          <p style={{ color: "#666" }}>
            {t({ ja: "履歴を読み込み中...", en: "Loading history..." })}
          </p>
        )}
        {messages.length === 0 && (
          <p style={{ color: "#777" }}>
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
                  color: "#6f4a1f",
                  borderRadius: 8,
                  padding: "8px 10px",
                  whiteSpace: "pre-wrap",
                  lineHeight: 1.6,
                }}
              >
                <div style={{ fontSize: "0.78rem", color: "#7b5a31", marginBottom: 4, fontWeight: 700 }}>
                  {(m.role === "user"
                    ? (m.speaker_name?.trim() || t({ ja: "あなた", en: "You" }))
                    : (m.speaker_name?.trim() || characterName.trim() || t({ ja: "AI", en: "AI" })) ) +
                    " / do"}
                  {m.is_auto_dialogue
                    ? ` ${t({ ja: "[自動会話]", en: "[Auto]" })}`
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
                  }}
                >
                  <div style={{ fontSize: "0.78rem", color: "#5f6675", marginBottom: 4 }}>
                    {m.role === "user"
                      ? (m.speaker_name?.trim() || t({ ja: "あなた", en: "You" }))
                      : (m.speaker_name?.trim() || characterName.trim() || t({ ja: "AI", en: "AI" }))}{" "}
                    / say
                    {m.is_auto_dialogue
                      ? ` ${t({ ja: "[自動会話]", en: "[Auto]" })}`
                      : ""}
                  </div>
                  <div>{m.content}</div>
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
                  background: "#f6f7fb",
                  border: "1px solid #cfd4e2",
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

      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submitChat();
            }
          }}
          placeholder={t({ ja: "メッセージを入力", en: "Type a message" })}
          style={{ flex: 1 }}
          disabled={loading}
        />
        <button type="button" className="btn btn-border" onClick={() => submitChat()} disabled={loading || !input.trim()}>
          {loading ? t({ ja: "送信中...", en: "Sending..." }) : t({ ja: "送信", en: "Send" })}
        </button>
      </div>
      <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, fontSize: "0.92rem" }}>
        <input
          type="checkbox"
          checked={autoDialogue}
          onChange={(e) => setAutoDialogue(e.target.checked)}
          disabled={loading}
        />
        <span>
          {t({
            ja: "自動会話モード（キャラ同士の会話を自動で続ける。「停止」「止める」で停止）",
            en: "Auto dialogue mode (continue character-to-character conversation; type stop to halt)",
          })}
        </span>
      </label>
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
          disabled={loading}
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
        <span style={{ fontSize: "0.85rem", color: "#666" }}>
          {t({
            ja: "ON時は年齢確認済みとして扱います。",
            en: "When ON, age confirmation is considered accepted.",
          })}
        </span>
      </div>
      {autoDialogue && (
        <div style={{ marginTop: 4, fontSize: "0.85rem", color: autoContinuing ? "#235a93" : "#666" }}>
          {autoContinuing
            ? t({ ja: "キャラ会話を自動生成中...", en: "Generating auto character dialogue..." })
            : t({ ja: "自動会話が有効です。停止したい場合は「停止」または「止める」を送信してください。", en: "Auto dialogue is active. Send \"stop\" to halt." })}
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
          className={mode === "say" ? "btn btn-border" : "btn"}
          onClick={() => setMode("say")}
          disabled={loading}
          aria-pressed={mode === "say"}
          style={{
            fontWeight: mode === "say" ? 700 : 400,
            background: mode === "say" ? "#dbeeff" : undefined,
            borderColor: mode === "say" ? "#4a87c2" : undefined,
          }}
        >
          {t({ ja: "say（発言）", en: "say (speech)" })}
        </button>
        <button
          type="button"
          className={mode === "do" ? "btn btn-border" : "btn"}
          onClick={() => setMode("do")}
          disabled={loading}
          aria-pressed={mode === "do"}
          style={{
            fontWeight: mode === "do" ? 700 : 400,
            background: mode === "do" ? "#ffe7d1" : undefined,
            borderColor: mode === "do" ? "#cf7a24" : undefined,
          }}
        >
          {t({ ja: "do（行動）", en: "do (action)" })}
        </button>
      </div>
    </div>
  );
}
