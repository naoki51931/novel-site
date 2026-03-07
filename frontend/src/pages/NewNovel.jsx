import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { trackEvent } from "../lib/analytics";
import { useI18n } from "../lib/i18n";
import { mergeTagsInput, parseTagsInput } from "../lib/tagSuggest";
import { getApiBase } from "../lib/apiBase";
import {
  dismissGuideBubble,
  getDismissedGuideBubbles,
  isOnboardingGuideEligible,
} from "../lib/onboardingGuide";

const API_BASE = getApiBase();
const DRAFT_KEY = "draft_new_novel";
const GUIDE_REGISTER_VISITED_KEY = "onboarding_register_visited_v1";
const GUIDE_CREATED_NOVEL_ID_KEY = "onboarding_created_novel_id_v1";
const GUIDE_NOVEL_CREATED_USERS_KEY = "onboarding_novel_created_users_v1";

export default function NewNovel() {
  const navigate = useNavigate();
  const { t } = useI18n();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tagNamesInput, setTagNamesInput] = useState("");

  const [ageLimit, setAgeLimit] = useState("all");           // 全年齢 / R15 / R18
  const [isAIGenerated, setIsAIGenerated] = useState(false); // AI創作フラグ
  const [creativeType, setCreativeType] = useState("original"); // オリジナル / 二次創作
  const [fanficSourceTitle, setFanficSourceTitle] = useState("");
  const [fanficCharacters, setFanficCharacters] = useState("");
  const [fanficCoupling, setFanficCoupling] = useState("");
  const [fanficNotes, setFanficNotes] = useState("");
  const [seriesName, setSeriesName] = useState("");
  const [seriesOrder, setSeriesOrder] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [tagCandidates, setTagCandidates] = useState([]);
  const [selectedTagCandidates, setSelectedTagCandidates] = useState(() => new Set());
  const [tagSuggestError, setTagSuggestError] = useState("");
  const [tagSuggestLoading, setTagSuggestLoading] = useState(false);
  const [titleSuggestLoading, setTitleSuggestLoading] = useState(false);
  const [titleSuggestError, setTitleSuggestError] = useState("");
  const [titleCandidates, setTitleCandidates] = useState([]);
  const [summarySuggestLoading, setSummarySuggestLoading] = useState(false);
  const [summarySuggestError, setSummarySuggestError] = useState("");
  const [summaryCandidates, setSummaryCandidates] = useState([]);
  const [dismissedBubbles, setDismissedBubbles] = useState(() => getDismissedGuideBubbles());
  const [expandedBubble, setExpandedBubble] = useState("");

  const countChars = (value) => (value || "").length;
  const isLoggedIn = typeof window !== "undefined" && Boolean(localStorage.getItem("token"));
  const canShowGuides = isOnboardingGuideEligible();
  const isBubbleVisible = (key) => !dismissedBubbles.has(String(key));
  const handleDismissBubble = (e, key) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    dismissGuideBubble(key);
    setDismissedBubbles(getDismissedGuideBubbles());
    setExpandedBubble((prev) => (prev === key ? "" : prev));
  };
  const hasRegistered =
    isLoggedIn ||
    (typeof window !== "undefined" && localStorage.getItem(GUIDE_REGISTER_VISITED_KEY) === "1");
  const activeGuideStep = isLoggedIn ? "create" : hasRegistered ? "login" : "register";

  // 🔹 AI小説生成ページへ移動
  const handleOpenAINovel = () => {
    navigate("/ai-novel");
  };

  const handleSuggestTags = async () => {
    setTagSuggestError("");
    const sourceText = [title, description].filter(Boolean).join("\n");
    if (!sourceText.trim()) {
      setTagSuggestError(
        t({
          ja: "本文/説明がないため候補を生成できません。",
          en: "No text available to generate tags.",
        })
      );
      return;
    }
    try {
      setTagSuggestLoading(true);
      const token = localStorage.getItem("token");
      if (!token) {
        throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));
      }
      const res = await fetch(`${API_BASE}/api/ai/tag_candidates`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ text: sourceText.slice(0, 1000) }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "タグ候補の生成に失敗しました。", en: "Failed to generate tags." }));
      }
      const existing = parseTagsInput(tagNamesInput);
      const existingSet = new Set(existing.map((tag) => tag.toLowerCase()));
      const candidates = (data?.candidates || []).filter(
        (tag) => tag && !existingSet.has(tag.toLowerCase())
      );
      if (!candidates.length) {
        setTagSuggestError(
          t({ ja: "追加できるタグ候補がありません。", en: "No tag candidates to add." })
        );
        setTagCandidates([]);
        setSelectedTagCandidates(new Set());
        return;
      }
      setTagCandidates(candidates);
      setSelectedTagCandidates(new Set(candidates));
    } catch (err) {
      console.error(err);
      setTagSuggestError(
        err.message || t({ ja: "タグ候補の生成に失敗しました。", en: "Failed to generate tags." })
      );
    } finally {
      setTagSuggestLoading(false);
    }
  };

  const handleSuggestTitles = async () => {
    setTitleSuggestError("");
    setTitleCandidates([]);
    const sourceText = [description, title].filter(Boolean).join("\n");
    if (!sourceText.trim()) {
      setTitleSuggestError(
        t({
          ja: "説明文がないためタイトル候補を生成できません。",
          en: "No description text available to generate title candidates.",
        })
      );
      return;
    }
    try {
      setTitleSuggestLoading(true);
      const token = localStorage.getItem("token");
      if (!token) {
        throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));
      }
      const res = await fetch(`${API_BASE}/api/ai/title_candidates`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ text: sourceText.slice(0, 2200), suggestions_count: 5 }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data.detail || t({ ja: "タイトル候補の生成に失敗しました。", en: "Failed to generate title candidates." })
        );
      }
      const nextCandidates = Array.isArray(data?.candidates)
        ? data.candidates.map((v) => String(v || "").trim()).filter(Boolean)
        : [];
      if (!nextCandidates.length) {
        throw new Error(
          t({ ja: "タイトル候補を取得できませんでした。", en: "Failed to get title candidates." })
        );
      }
      setTitleCandidates(nextCandidates);
      setTitle(nextCandidates[0]);
    } catch (err) {
      console.error(err);
      setTitleSuggestError(
        err.message || t({ ja: "タイトル候補の生成に失敗しました。", en: "Failed to generate title candidates." })
      );
    } finally {
      setTitleSuggestLoading(false);
    }
  };

  const handleSuggestSummaries = async () => {
    setSummarySuggestError("");
    setSummaryCandidates([]);
    const sourceText = [
      title,
      description,
      tagNamesInput,
      creativeType === "fanfic" ? fanficSourceTitle : "",
      creativeType === "fanfic" ? fanficCharacters : "",
      creativeType === "fanfic" ? fanficCoupling : "",
      creativeType === "fanfic" ? fanficNotes : "",
    ]
      .filter(Boolean)
      .join("\n");
    if (!sourceText.trim()) {
      setSummarySuggestError(
        t({
          ja: "入力がないためあらすじ候補を生成できません。",
          en: "No input text to generate summary candidates.",
        })
      );
      return;
    }
    try {
      setSummarySuggestLoading(true);
      const token = localStorage.getItem("token");
      if (!token) {
        throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));
      }
      const res = await fetch(`${API_BASE}/api/ai/summary_candidates`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ text: sourceText.slice(0, 3000), suggestions_count: 4 }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data.detail || t({ ja: "あらすじ候補の生成に失敗しました。", en: "Failed to generate summary candidates." })
        );
      }
      const candidates = Array.isArray(data?.candidates)
        ? data.candidates.map((v) => String(v || "").trim()).filter(Boolean)
        : [];
      if (!candidates.length) {
        throw new Error(
          t({ ja: "あらすじ候補を取得できませんでした。", en: "Failed to get summary candidates." })
        );
      }
      setSummaryCandidates(candidates);
      setDescription(candidates[0]);
    } catch (err) {
      console.error(err);
      setSummarySuggestError(
        err.message || t({ ja: "あらすじ候補の生成に失敗しました。", en: "Failed to generate summary candidates." })
      );
    } finally {
      setSummarySuggestLoading(false);
    }
  };

  const handleToggleCandidate = (candidate) => {
    setSelectedTagCandidates((prev) => {
      const next = new Set(prev);
      if (next.has(candidate)) {
        next.delete(candidate);
      } else {
        next.add(candidate);
      }
      return next;
    });
  };

  const handleAddSuggestedTags = () => {
    if (!selectedTagCandidates.size) return;
    const selected = tagCandidates.filter((tag) => selectedTagCandidates.has(tag));
    const nextInput = mergeTagsInput(tagNamesInput, selected);
    setTagNamesInput(nextInput);
    const remaining = tagCandidates.filter((tag) => !selectedTagCandidates.has(tag));
    setTagCandidates(remaining);
    setSelectedTagCandidates(new Set());
  };

  // === auto-save draft start ===
  // マウント時に下書きを読み込む
  useEffect(() => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (!raw) return;
      const draft = JSON.parse(raw);
      if (draft.title) setTitle(draft.title);
      if (draft.description) setDescription(draft.description);
      if (draft.tagNamesInput) setTagNamesInput(draft.tagNamesInput);
      if (draft.creativeType) setCreativeType(draft.creativeType);
      if (draft.fanficSourceTitle) setFanficSourceTitle(draft.fanficSourceTitle);
      if (draft.fanficCharacters) setFanficCharacters(draft.fanficCharacters);
      if (draft.fanficCoupling) setFanficCoupling(draft.fanficCoupling);
      if (draft.fanficNotes) setFanficNotes(draft.fanficNotes);
      if (draft.seriesName) setSeriesName(draft.seriesName);
      if (draft.seriesOrder) setSeriesOrder(String(draft.seriesOrder));
    } catch (e) {
      console.error("failed to load draft", e);
    }
  }, []);

  // 入力が変わるたび 1秒後に自動保存
  useEffect(() => {
    const timer = setTimeout(() => {
      const payload = {
        title,
        description,
        tagNamesInput,
        creativeType,
        fanficSourceTitle,
        fanficCharacters,
        fanficCoupling,
        fanficNotes,
        seriesName,
        seriesOrder,
        saved_at: new Date().toISOString(),
      };
      try {
        localStorage.setItem(DRAFT_KEY, JSON.stringify(payload));
      } catch (e) {
        console.error("failed to save draft", e);
      }
    }, 1000);

    return () => clearTimeout(timer);
  }, [
    title,
    description,
    tagNamesInput,
    creativeType,
    fanficSourceTitle,
    fanficCharacters,
    fanficCoupling,
    fanficNotes,
    seriesName,
    seriesOrder,
  ]);
  // === auto-save draft end ===


  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!title.trim()) {
      setError(t({ ja: "タイトルは必須です。", en: "Title is required." }));
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));
      }

      const payload = {
        title,
        description,
        age_limit: ageLimit,
        is_ai_generated: isAIGenerated,
        tag_names: tagNamesInput
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        creative_type: creativeType,
        fanfic_source_title: creativeType === "fanfic" ? fanficSourceTitle : "",
        fanfic_characters: creativeType === "fanfic" ? fanficCharacters : "",
        fanfic_coupling: creativeType === "fanfic" ? fanficCoupling : "",
        fanfic_notes: creativeType === "fanfic" ? fanficNotes : "",
        series_name: seriesName,
        series_order: seriesOrder === "" ? null : Number(seriesOrder),
      };

      const res = await fetch(`${API_BASE}/api/novels`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "小説の作成に失敗しました", en: "Failed to create novel." }));
      }

      try {
        const username = localStorage.getItem("username");
        if (username) {
          const raw = localStorage.getItem(GUIDE_NOVEL_CREATED_USERS_KEY);
          const parsed = JSON.parse(raw || "[]");
          const users = Array.isArray(parsed) ? parsed : [];
          if (!users.includes(username)) {
            users.push(username);
            localStorage.setItem(GUIDE_NOVEL_CREATED_USERS_KEY, JSON.stringify(users));
          }
        }
      } catch {
        // ignore
      }

      if (data.id) {
        localStorage.removeItem(DRAFT_KEY);
        localStorage.setItem(GUIDE_CREATED_NOVEL_ID_KEY, String(data.id));
        trackEvent("novel_created", {
          novel_id: data.id,
          creative_type: creativeType,
          age_limit: ageLimit,
          is_ai_generated: isAIGenerated,
        });
        navigate(`/novels/${data.id}`);
      } else {
        localStorage.removeItem(DRAFT_KEY);
        trackEvent("novel_created", {
          creative_type: creativeType,
          age_limit: ageLimit,
          is_ai_generated: isAIGenerated,
        });
        navigate("/");
      }
    } catch (err) {
      console.error(err);
      setError(
        err.message || t({ ja: "小説の作成中にエラーが発生しました", en: "An error occurred while creating the novel." })
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">{t({ ja: "← 小説一覧に戻る", en: "← Back to novel list" })}</Link>
      </div>

      <div style={{ marginTop: 6, marginBottom: 12, fontSize: 14 }}>
        <Link
          to="/register"
          className={`btn btn-border ${isLoggedIn ? "" : "novel-register-cta"}`}
          style={{ display: "inline-block", fontSize: 18, padding: "14px 22px", fontWeight: 700 }}
        >
          {t({
            ja: isLoggedIn ? "会員登録済みです。投稿準備を進めましょう" : "まずは会員登録してください",
            en: isLoggedIn ? "Registration complete. Continue posting setup." : "Please register first",
          })}
        </Link>
      </div>
      <h2>{t({ ja: "新しい小説を作成", en: "Create New Novel" })}</h2>

      {canShowGuides && (
      <section className="novel-post-guide" aria-label={t({ ja: "投稿ガイド", en: "Posting guide" })}>
        <div
          className={`novel-post-guide-bubble ${
            hasRegistered ? "is-done" : activeGuideStep === "register" ? "is-current" : ""
          } ${expandedBubble === "newnovel_step1" ? "is-expanded" : ""}`.trim()}
          onClick={() => setExpandedBubble((prev) => (prev === "newnovel_step1" ? "" : "newnovel_step1"))}
        >
          {isBubbleVisible("newnovel_step1") && (
            <div className="novel-post-guide-actions">
              <button type="button" className="onboarding-guide-dismiss" onClick={(e) => handleDismissBubble(e, "newnovel_step1")}>
                {t({ ja: "吹き出しを消す", en: "Dismiss bubble" })}
              </button>
              <button type="button" className="onboarding-guide-close" onClick={(e) => handleDismissBubble(e, "newnovel_step1")}>×</button>
            </div>
          )}
          {!isBubbleVisible("newnovel_step1") ? null : (
            <>
          <strong>{t({ ja: "STEP 1", en: "STEP 1" })}</strong>
          <span>
            {hasRegistered
              ? t({
                  ja: "会員登録は完了しています。",
                  en: "Registration is complete.",
                })
              : t({
                  ja: "まずは、会員登録をしてください。",
                  en: "First, please create an account.",
                })}
          </span>
            </>
          )}
        </div>
        <div
          className={`novel-post-guide-bubble ${
            isLoggedIn ? "is-done" : activeGuideStep === "login" ? "is-current" : ""
          } ${expandedBubble === "newnovel_step2" ? "is-expanded" : ""}`.trim()}
          onClick={() => setExpandedBubble((prev) => (prev === "newnovel_step2" ? "" : "newnovel_step2"))}
        >
          {isBubbleVisible("newnovel_step2") && (
            <div className="novel-post-guide-actions">
              <button type="button" className="onboarding-guide-dismiss" onClick={(e) => handleDismissBubble(e, "newnovel_step2")}>
                {t({ ja: "吹き出しを消す", en: "Dismiss bubble" })}
              </button>
              <button type="button" className="onboarding-guide-close" onClick={(e) => handleDismissBubble(e, "newnovel_step2")}>×</button>
            </div>
          )}
          {!isBubbleVisible("newnovel_step2") ? null : (
            <>
          <strong>{t({ ja: "STEP 2", en: "STEP 2" })}</strong>
          <span>
            {isLoggedIn
              ? t({
                  ja: "ログインは完了しています。",
                  en: "Login is complete.",
                })
              : t({
                  ja: "次は、ログインしてください。",
                  en: "Next, please log in.",
                })}
          </span>
            </>
          )}
        </div>
        <div
          className={`novel-post-guide-bubble ${
            activeGuideStep === "create" ? "is-ready" : ""
          } ${expandedBubble === "newnovel_step3" ? "is-expanded" : ""}`.trim()}
          onClick={() => setExpandedBubble((prev) => (prev === "newnovel_step3" ? "" : "newnovel_step3"))}
        >
          {isBubbleVisible("newnovel_step3") && (
            <div className="novel-post-guide-actions">
              <button type="button" className="onboarding-guide-dismiss" onClick={(e) => handleDismissBubble(e, "newnovel_step3")}>
                {t({ ja: "吹き出しを消す", en: "Dismiss bubble" })}
              </button>
              <button type="button" className="onboarding-guide-close" onClick={(e) => handleDismissBubble(e, "newnovel_step3")}>×</button>
            </div>
          )}
          {!isBubbleVisible("newnovel_step3") ? null : (
            <>
          <strong>{t({ ja: "STEP 3", en: "STEP 3" })}</strong>
          <span>
            {isLoggedIn
              ? t({
                  ja: "最後に、小説を作成してください。",
                  en: "Finally, create your novel.",
                })
              : t({
                  ja: "ログイン後に小説を作成してください。",
                  en: "Create your novel after logging in.",
                })}
          </span>
            </>
          )}
        </div>
        <div
          className={`novel-post-guide-bubble is-optional ${expandedBubble === "newnovel_step4" ? "is-expanded" : ""}`.trim()}
          onClick={() => setExpandedBubble((prev) => (prev === "newnovel_step4" ? "" : "newnovel_step4"))}
        >
          {isBubbleVisible("newnovel_step4") && (
            <div className="novel-post-guide-actions">
              <button type="button" className="onboarding-guide-dismiss" onClick={(e) => handleDismissBubble(e, "newnovel_step4")}>
                {t({ ja: "吹き出しを消す", en: "Dismiss bubble" })}
              </button>
              <button type="button" className="onboarding-guide-close" onClick={(e) => handleDismissBubble(e, "newnovel_step4")}>×</button>
            </div>
          )}
          {!isBubbleVisible("newnovel_step4") ? null : (
            <>
          <strong>{t({ ja: "STEP 4", en: "STEP 4" })}</strong>
          <span>
            {t({
              ja: "小説作成の次は、エピソードを作成してください。",
              en: "After creating the novel, create an episode.",
            })}
          </span>
            </>
          )}
        </div>
      </section>
      )}

      {/* 🔹 AI小説生成ページへのショートカットボタン */}
      <div style={{ marginBottom: 16 }}>
        <button
          type="button"
          className="btn btn-border"
          onClick={handleOpenAINovel}
        >
          {t({ ja: "AI小説生成ページへ", en: "Go to AI Novel Generator" })}
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "タイトル", en: "Title" })}
            <br />
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
          <div style={{ fontSize: "0.85rem", color: "#666", marginTop: 4 }}>
            {t({ ja: "現在の文字数", en: "Current chars" })}: {countChars(title)}
          </div>
          <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
            <button
              type="button"
              className="btn btn-border"
              onClick={handleSuggestTitles}
              disabled={titleSuggestLoading}
            >
              {titleSuggestLoading
                ? t({ ja: "タイトル候補を生成中...", en: "Generating title candidates..." })
                : t({ ja: "本文/説明からタイトル候補を生成", en: "Generate title candidates from text/description" })}
            </button>
          </div>
          {titleSuggestError && (
            <div style={{ marginTop: 6, color: "red" }}>{titleSuggestError}</div>
          )}
          {titleCandidates.length > 0 && (
            <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
              {titleCandidates.map((candidate, idx) => (
                <button
                  key={`${candidate}-${idx}`}
                  type="button"
                  className="btn btn-border"
                  onClick={() => setTitle(candidate)}
                  style={{ textAlign: "left" }}
                >
                  {candidate}
                </button>
              ))}
            </div>
          )}
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "説明（あらすじ）", en: "Description (summary)" })}
            <br />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
          <div style={{ fontSize: "0.85rem", color: "#666", marginTop: 4 }}>
            {t({ ja: "現在の文字数", en: "Current chars" })}: {countChars(description)}
          </div>
          <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
            <button
              type="button"
              className="btn btn-border"
              onClick={handleSuggestSummaries}
              disabled={summarySuggestLoading}
            >
              {summarySuggestLoading
                ? t({ ja: "あらすじ候補を生成中...", en: "Generating summary candidates..." })
                : t({ ja: "AIであらすじ候補を生成", en: "Generate summary candidates with AI" })}
            </button>
          </div>
          {summarySuggestError && (
            <div style={{ marginTop: 6, color: "red" }}>{summarySuggestError}</div>
          )}
          {summaryCandidates.length > 0 && (
            <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
              {summaryCandidates.map((candidate, idx) => (
                <button
                  key={`summary-${idx}-${candidate.slice(0, 16)}`}
                  type="button"
                  className="btn btn-border"
                  onClick={() => setDescription(candidate)}
                  style={{ textAlign: "left" }}
                >
                  {candidate}
                </button>
              ))}
            </div>
          )}
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "タグ（カンマ区切り）", en: "Tags (comma-separated)" })}
            <br />
            <input
              type="text"
              value={tagNamesInput}
              onChange={(e) => setTagNamesInput(e.target.value)}
              style={{ width: "100%", padding: 4 }}
              placeholder={t({ ja: "例: ファンタジー, バトル, 百合", en: "e.g., Fantasy, Battle, Yuri" })}
            />
          </label>
          <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
            <button
              type="button"
              className="btn btn-border"
              onClick={handleSuggestTags}
              disabled={tagSuggestLoading}
            >
              {tagSuggestLoading
                ? t({ ja: "抽出中...", en: "Extracting..." })
                : t({ ja: "本文/説明からタグ候補を抽出", en: "Suggest tags from text" })}
            </button>
            <span style={{ fontSize: "0.85rem", color: "#666" }}>
              {t({ ja: "候補を選んで追加できます", en: "Pick candidates to add" })}
            </span>
          </div>
          {tagSuggestError && (
            <div style={{ marginTop: 6, color: "red" }}>{tagSuggestError}</div>
          )}
          {tagCandidates.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {tagCandidates.map((candidate) => (
                  <label
                    key={candidate}
                    style={{
                      border: "1px solid var(--border)",
                      borderRadius: 999,
                      padding: "4px 10px",
                      background: "var(--surface-2)",
                      fontSize: "0.85rem",
                      display: "inline-flex",
                      gap: 6,
                      alignItems: "center",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedTagCandidates.has(candidate)}
                      onChange={() => handleToggleCandidate(candidate)}
                    />
                    {candidate}
                  </label>
                ))}
              </div>
              <div style={{ marginTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={handleAddSuggestedTags}
                  disabled={!selectedTagCandidates.size}
                >
                  {t({ ja: "選択したタグを追加", en: "Add selected tags" })}
                </button>
              </div>
            </div>
          )}
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "作品種別", en: "Work type" })}
            <br />
            <div style={{ display: "flex", gap: 12, marginTop: 4 }}>
              <label>
                <input
                  type="radio"
                  name="creative_type"
                  value="original"
                  checked={creativeType === "original"}
                  onChange={(e) => setCreativeType(e.target.value)}
                  style={{ marginRight: 4 }}
                />
                {t({ ja: "オリジナル", en: "Original" })}
              </label>
              <label>
                <input
                  type="radio"
                  name="creative_type"
                  value="fanfic"
                  checked={creativeType === "fanfic"}
                  onChange={(e) => setCreativeType(e.target.value)}
                  style={{ marginRight: 4 }}
                />
                {t({ ja: "二次創作", en: "Fanfiction" })}
              </label>
            </div>
          </label>
        </div>

        {creativeType === "fanfic" && (
          <section
            style={{
              marginBottom: 10,
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: 10,
            }}
          >
            <h3 style={{ marginTop: 0, marginBottom: 8 }}>
              {t({ ja: "二次創作向け入力", en: "Fanfic fields" })}
            </h3>
            <div style={{ marginBottom: 8 }}>
              <label>
                {t({ ja: "原作名", en: "Source title" })}<br />
                <input
                  type="text"
                  value={fanficSourceTitle}
                  onChange={(e) => setFanficSourceTitle(e.target.value)}
                  style={{ width: "100%", padding: 4 }}
                />
              </label>
            </div>
            <div style={{ marginBottom: 8 }}>
              <label>
                {t({ ja: "キャラ", en: "Characters" })}<br />
                <input
                  type="text"
                  value={fanficCharacters}
                  onChange={(e) => setFanficCharacters(e.target.value)}
                  style={{ width: "100%", padding: 4 }}
                  placeholder={t({ ja: "例: A, B, C", en: "e.g., A, B, C" })}
                />
              </label>
            </div>
            <div style={{ marginBottom: 8 }}>
              <label>
                {t({ ja: "カップリング", en: "Pairing" })}<br />
                <input
                  type="text"
                  value={fanficCoupling}
                  onChange={(e) => setFanficCoupling(e.target.value)}
                  style={{ width: "100%", padding: 4 }}
                  placeholder={t({ ja: "例: A×B", en: "e.g., A x B" })}
                />
              </label>
            </div>
            <div style={{ marginBottom: 0 }}>
              <label>
                {t({ ja: "注意事項", en: "Notes / warnings" })}<br />
                <textarea
                  rows={3}
                  value={fanficNotes}
                  onChange={(e) => setFanficNotes(e.target.value)}
                  style={{ width: "100%", padding: 4 }}
                />
              </label>
            </div>
          </section>
        )}

        <section
          style={{
            marginBottom: 10,
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: 10,
          }}
        >
          <h3 style={{ marginTop: 0, marginBottom: 8 }}>
            {t({ ja: "シリーズ設定（任意）", en: "Series (optional)" })}
          </h3>
          <div style={{ marginBottom: 8 }}>
            <label>
              {t({ ja: "シリーズ名", en: "Series name" })}<br />
              <input
                type="text"
                value={seriesName}
                onChange={(e) => setSeriesName(e.target.value)}
                style={{ width: "100%", padding: 4 }}
              />
            </label>
          </div>
          <div style={{ marginBottom: 0 }}>
            <label>
              {t({ ja: "シリーズ順", en: "Series order" })}<br />
              <input
                type="number"
                min="1"
                value={seriesOrder}
                onChange={(e) => setSeriesOrder(e.target.value)}
                style={{ width: "100%", padding: 4 }}
              />
            </label>
          </div>
        </section>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "年齢区分", en: "Age rating" })}
            <br />
            <select
              value={ageLimit}
              onChange={(e) => setAgeLimit(e.target.value)}
              style={{ width: "100%", padding: 4 }}
            >
              <option value="all">{t({ ja: "全年齢", en: "All ages" })}</option>
              <option value="r15">R15</option>
              <option value="r18">R18</option>
            </select>
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            <input
              type="checkbox"
              checked={isAIGenerated}
              onChange={(e) => setIsAIGenerated(e.target.checked)}
              style={{ marginRight: 4 }}
            />
            {t({ ja: "AI創作", en: "AI-generated" })}
          </label>
        </div>

        {error && (
          <p style={{ color: "red", marginTop: 4, marginBottom: 8 }}>{error}</p>
        )}

        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="btn btn-border"
            type="submit"
            disabled={saving}
          >
            {saving ? t({ ja: "作成中...", en: "Creating..." }) : t({ ja: "作成する", en: "Create" })}
          </button>
          <button
            className="btn btn-border"
            type="button"
            onClick={() => navigate("/")}
          >
            {t({ ja: "キャンセル", en: "Cancel" })}
          </button>
        </div>
      </form>
    </div>
  );
}
