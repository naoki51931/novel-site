import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getErrorMessage } from "../lib/errorUtils";
import { getSavedTheme, setTheme } from "../theme";
import { useI18n } from "../lib/i18n";
import {
  DEFAULT_USER_TIMEZONE,
  TIME_ZONE_OPTIONS,
  getUserTimeZone,
  setUserTimeZone,
} from "../lib/timezone";

const MYPAGE_SHOW_CHATBOT_STORAGE_KEY = "mypage_show_chatbot";
const BIRTH_YEAR_MIN = 1900;

type ThemeName = "light" | "dark";
type TranslationFn = (value: Record<string, string>, vars?: Record<string, string | number>) => string;
type BirthDateParts = { year: number; month: number; day: number };
type ApiValidationIssue = { loc?: unknown[]; msg?: string };
type AiModelOption = { value: string; labelJa: string; labelEn: string };
const DEFAULT_MY_PAGE_AI_MODEL = "google/gemini-2.5-flash";
const DEFAULT_TRANSLATION_AI_MODEL = "google/gemini-3-flash-preview";

const AI_MODEL_OPTIONS: AiModelOption[] = [
  { value: "google/gemini-3-flash-preview", labelJa: "Gemini 3 Flash Preview（OpenRouter）", labelEn: "Gemini 3 Flash Preview (OpenRouter)" },
  { value: "google/gemini-2.5-flash", labelJa: "Gemini 2.5 Flash（OpenRouter）", labelEn: "Gemini 2.5 Flash (OpenRouter)" },
  { value: "gpt-5.2", labelJa: "GPT-5.2", labelEn: "GPT-5.2" },
  { value: "gpt-5", labelJa: "GPT-5", labelEn: "GPT-5" },
  { value: "gpt-5-mini", labelJa: "GPT-5 Mini", labelEn: "GPT-5 Mini" },
  { value: "gpt-4.1", labelJa: "GPT-4.1", labelEn: "GPT-4.1" },
  { value: "gpt-4.1-mini", labelJa: "GPT-4.1 Mini", labelEn: "GPT-4.1 Mini" },
  { value: "openai/gpt-chat-latest", labelJa: "ChatGPT（OpenRouter）", labelEn: "ChatGPT (OpenRouter)" },
  { value: "google/gemini-2.5-pro", labelJa: "Gemini 2.5 Pro（OpenRouter）", labelEn: "Gemini 2.5 Pro (OpenRouter)" },
  { value: "moonshotai/kimi-k2", labelJa: "Kimi（OpenRouter）", labelEn: "Kimi (OpenRouter)" },
  { value: "moonshotai/kimi-k3", labelJa: "Kimi K3（OpenRouter）", labelEn: "Kimi K3 (OpenRouter)" },
  { value: "deepseek/deepseek-chat", labelJa: "DeepSeek（OpenRouter）", labelEn: "DeepSeek (OpenRouter)" },
  { value: "deepseek/deepseek-r1", labelJa: "DeepSeek R1（OpenRouter）", labelEn: "DeepSeek R1 (OpenRouter)" },
  { value: "deepseek:deepseek-chat", labelJa: "DeepSeek（公式）", labelEn: "DeepSeek (official)" },
  { value: "deepseek:deepseek-reasoner", labelJa: "DeepSeek Reasoner（公式）", labelEn: "DeepSeek Reasoner (official)" },
];

const pad2 = (n: number) => String(n).padStart(2, "0");
const formatBirthDate = (year: number, month: number, day: number) =>
  `${year}-${pad2(month)}-${pad2(day)}`;
const daysInMonth = (year: number, month: number) => new Date(year, month, 0).getDate();
const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);
const formatApiErrorDetail = (detail: unknown, fallback: string, t: TranslationFn) => {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const birthDateIssue = detail.find((item: ApiValidationIssue) => {
      const loc = Array.isArray(item?.loc) ? item.loc : [];
      return loc.includes("birth_date");
    });
    if (birthDateIssue) {
      return t({ ja: "生年月日は必須です。", en: "Birth date is required." });
    }
    const firstMsg = detail.find(
      (item: ApiValidationIssue) => typeof item?.msg === "string" && item.msg.trim()
    );
    if (firstMsg) return firstMsg.msg;
  }
  if (detail && typeof detail === "object") {
    const detailRecord = detail as { message?: string; msg?: string };
    if (typeof detailRecord.message === "string" && detailRecord.message.trim()) return detailRecord.message;
    if (typeof detailRecord.msg === "string" && detailRecord.msg.trim()) return detailRecord.msg;
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }
  return fallback;
};

const getRequiredFieldsHelp = (t: TranslationFn) =>
  t({
    ja: "必須項目: ユーザー名、生年月日",
    en: "Required fields: Username and birth date",
  });

const parseBirthDate = (value: unknown, maxYear: number): BirthDateParts | null => {
  const m = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return null;
  const year = clamp(Number(m[1]), BIRTH_YEAR_MIN, maxYear);
  const month = clamp(Number(m[2]), 1, 12);
  const maxDay = daysInMonth(year, month);
  const day = clamp(Number(m[3]), 1, maxDay);
  return { year, month, day };
};

export default function AccountSettings() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const today = new Date();
  const birthYearMax = today.getFullYear();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [favoriteVisibility, setFavoriteVisibility] = useState("public");
  const [timeZone, setTimeZone] = useState(() => getUserTimeZone());
  const [profileBio, setProfileBio] = useState("");
  const [profileIconUrl, setProfileIconUrl] = useState("");
  const [profileHeaderUrl, setProfileHeaderUrl] = useState("");
  const [profileWebsiteUrl, setProfileWebsiteUrl] = useState("");
  const [profileXUrl, setProfileXUrl] = useState("");
  const [aiSummaryModel, setAiSummaryModel] = useState(DEFAULT_MY_PAGE_AI_MODEL);
  const [aiTitleModel, setAiTitleModel] = useState(DEFAULT_MY_PAGE_AI_MODEL);
  const [aiTagModel, setAiTagModel] = useState(DEFAULT_MY_PAGE_AI_MODEL);
  const [aiChatModel, setAiChatModel] = useState(DEFAULT_MY_PAGE_AI_MODEL);
  const [aiTranslationModel, setAiTranslationModel] = useState(DEFAULT_TRANSLATION_AI_MODEL);
  const [aiStoryAgentModel, setAiStoryAgentModel] = useState(DEFAULT_MY_PAGE_AI_MODEL);
  const [aiCommentRevisionModel, setAiCommentRevisionModel] = useState(DEFAULT_MY_PAGE_AI_MODEL);
  const [aiStoryAgentVisible, setAiStoryAgentVisible] = useState(true);
  const [theme, setThemeState] = useState(() => {
    try {
      return getSavedTheme();
    } catch {
      return "light";
    }
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [showChatbot, setShowChatbot] = useState(() => {
    try {
      const v = localStorage.getItem(MYPAGE_SHOW_CHATBOT_STORAGE_KEY);
      if (v === null) return false; // default: unchecked
      return v === "1" || v === "true";
    } catch {
      return false;
    }
  });
  const [showBirthSlider, setShowBirthSlider] = useState(false);
  const birthParts =
    parseBirthDate(birthDate, birthYearMax) || { year: 2000, month: 1, day: 1 };

  const updateBirthDateBySlider = (part: "year" | "month" | "day", rawValue: string) => {
    const base = parseBirthDate(birthDate, birthYearMax) || { year: 2000, month: 1, day: 1 };
    let nextYear = base.year;
    let nextMonth = base.month;
    let nextDay = base.day;
    const value = Number(rawValue);

    if (part === "year") nextYear = clamp(value, BIRTH_YEAR_MIN, birthYearMax);
    if (part === "month") nextMonth = clamp(value, 1, 12);

    const maxDay = daysInMonth(nextYear, nextMonth);
    if (part === "day") nextDay = clamp(value, 1, maxDay);
    else nextDay = clamp(nextDay, 1, maxDay);

    setBirthDate(formatBirthDate(nextYear, nextMonth, nextDay));
  };

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { navigate("/login"); return; }

    fetch(`/api/users/me`, {
      headers: { Authorization: "Bearer " + token }
    })
      .then(async (res) => {
        if (res.status === 401) {
          navigate("/login");
          return null;
        }

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(
            data.detail || t({ ja: "プロフィール取得に失敗しました", en: "Failed to load profile." })
          );
        }

        return res.json();
      })
      .then((data: any) => {
        if (!data) return;
        setUsername(data.username || "");
        setEmail(data.email || "");
        setBirthDate(data.birth_date || "");
        setFavoriteVisibility(
          data.favorite_visibility === "private" ? "private" : "public"
        );
        const loadedTimeZone = setUserTimeZone(data.timezone || DEFAULT_USER_TIMEZONE);
        setTimeZone(loadedTimeZone);
        setProfileBio(data.profile_bio || "");
        setProfileIconUrl(data.profile_icon_url || "");
        setProfileHeaderUrl(data.profile_header_url || "");
        setProfileWebsiteUrl(data.profile_website_url || "");
        setProfileXUrl(data.profile_x_url || "");
        setAiSummaryModel(data.ai_summary_model || DEFAULT_MY_PAGE_AI_MODEL);
        setAiTitleModel(data.ai_title_model || DEFAULT_MY_PAGE_AI_MODEL);
        setAiTagModel(data.ai_tag_model || DEFAULT_MY_PAGE_AI_MODEL);
        setAiChatModel(data.ai_chat_model || DEFAULT_MY_PAGE_AI_MODEL);
        setAiTranslationModel(data.ai_translation_model || DEFAULT_TRANSLATION_AI_MODEL);
        setAiStoryAgentModel(data.ai_story_agent_model || DEFAULT_MY_PAGE_AI_MODEL);
        setAiCommentRevisionModel(data.ai_comment_revision_model || DEFAULT_MY_PAGE_AI_MODEL);
        setAiStoryAgentVisible(data.ai_story_agent_visible !== false);
      })
      .catch((e) =>
        setError(
          getErrorMessage(e, t({ ja: "プロフィール取得に失敗しました", en: "Failed to load profile." }))
        )
      )
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleChangeTheme = (nextTheme: ThemeName) => {
    try {
      const normalized = setTheme(nextTheme);
      setThemeState(normalized);
    } catch {
      setThemeState(nextTheme === "dark" ? "dark" : "light");
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      if (!birthDate) {
        throw new Error(t({ ja: "生年月日は必須です。", en: "Birth date is required." }));
      }

      const token = localStorage.getItem("token");
      if (!token) throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));

      const res = await fetch(`/api/users/me`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        body: JSON.stringify({
          username,
          email,
          birth_date: birthDate,
          favorite_visibility: favoriteVisibility,
          timezone: timeZone,
          profile_bio: profileBio,
          profile_icon_url: profileIconUrl,
          profile_header_url: profileHeaderUrl,
          profile_website_url: profileWebsiteUrl,
          profile_x_url: profileXUrl,
          ai_summary_model: aiSummaryModel,
          ai_title_model: aiTitleModel,
          ai_tag_model: aiTagModel,
          ai_chat_model: aiChatModel,
          ai_translation_model: aiTranslationModel,
          ai_story_agent_model: aiStoryAgentModel,
          ai_comment_revision_model: aiCommentRevisionModel,
          ai_story_agent_visible: aiStoryAgentVisible,
        }),
      });

      let msg = t({ ja: "保存しました。", en: "Saved." });
      if (res.status === 401) {
        navigate("/login");
        return;
      }

      if (!res.ok) {
        try {
          const d = await res.json();
          msg = formatApiErrorDetail(
            d?.detail,
            t(
              { ja: "保存に失敗しました (HTTP {{status}})", en: "Failed to save (HTTP {{status}})" },
              { status: res.status }
            ),
            t
          );
        } catch {
          msg = t(
            { ja: "保存に失敗しました (HTTP {{status}})", en: "Failed to save (HTTP {{status}})" },
            { status: res.status }
          );
        }
        if (res.status >= 500) {
          msg = `${msg} ${t({
            ja: "入力内容を確認してください。",
            en: "Please check your input.",
          })} ${getRequiredFieldsHelp(t)}.`;
        }
        throw new Error(msg);
      }

      localStorage.setItem("username", username);
      setUserTimeZone(timeZone);
      alert(t({ ja: "保存しました。", en: "Saved." }));
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "保存に失敗しました", en: "Failed to save." })));
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    try {
      localStorage.setItem(MYPAGE_SHOW_CHATBOT_STORAGE_KEY, showChatbot ? "1" : "0");
    } catch {
      // ignore storage errors
    }
  }, [showChatbot]);

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  return (
    <div>
      <h2>{t({ ja: "マイページ設定", en: "Account Settings" })}</h2>
      <p style={{ fontSize: 13, color: "var(--muted-text)" }}>
        {getRequiredFieldsHelp(t)}
      </p>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 16 }}>
          <fieldset style={{ padding: 12, border: "1px solid var(--border)" }}>
            <legend>{t({ ja: "テーマ", en: "Theme" })}</legend>
            <label style={{ marginRight: 12 }}>
              <input
                type="radio"
                name="theme"
                value="light"
                checked={theme === "light"}
                onChange={() => handleChangeTheme("light")}
              />{" "}
              {t({ ja: "ライト", en: "Light" })}
            </label>
            <label>
              <input
                type="radio"
                name="theme"
                value="dark"
                checked={theme === "dark"}
                onChange={() => handleChangeTheme("dark")}
              />{" "}
              {t({ ja: "ダーク", en: "Dark" })}
            </label>
            <div style={{ marginTop: 6, fontSize: 12, color: "var(--muted-text)" }}>
              {t({ ja: "テーマ設定はこのブラウザに保存されます。", en: "Theme settings are saved in this browser." })}
            </div>
          </fieldset>
        </div>

        <div style={{ marginBottom: 16 }}>
          <fieldset style={{ padding: 12, border: "1px solid var(--border)" }}>
            <legend>{t({ ja: "表示設定", en: "Display" })}</legend>
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={showChatbot}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setShowChatbot(e.target.checked)}
              />
              <span>
                {t({
                  ja: "チャットbotを表示（AIチャットで使用モデルを表示）",
                  en: "Show chatbot info (show model in AI chat)",
                })}
              </span>
            </label>
            <label style={{ display: "grid", gap: 4, marginTop: 12 }}>
              <span>{t({ ja: "タイムゾーン", en: "Time zone" })}</span>
              <select
                value={timeZone}
                onChange={(e) => setTimeZone(e.target.value)}
                style={{ width: "100%", padding: 4 }}
              >
                {TIME_ZONE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {t({ ja: option.labelJa, en: option.labelEn })} ({option.value})
                  </option>
                ))}
              </select>
              <span style={{ fontSize: 12, color: "var(--muted-text)" }}>
                {t({
                  ja: "小説・エピソード・通知・AI利用履歴などの日時表示に使用します。",
                  en: "Used for date/time display such as novels, episodes, notifications, and AI usage history.",
                })}
              </span>
            </label>
          </fieldset>
        </div>

        <div style={{ marginBottom: 16 }}>
          <fieldset style={{ padding: 12, border: "1px solid var(--border)" }}>
            <legend>{t({ ja: "AIモデル設定", en: "AI model preferences" })}</legend>
            <div style={{ display: "grid", gap: 12 }}>
              <label>
                {t({ ja: "概要生成", en: "Summary generation" })}<br />
                <select value={aiSummaryModel} onChange={(e) => setAiSummaryModel(e.target.value)} style={{ width: "100%", padding: 4 }}>
                  {AI_MODEL_OPTIONS.map((option) => (
                    <option key={`summary-${option.value || "default"}`} value={option.value}>
                      {t({ ja: option.labelJa, en: option.labelEn })}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t({ ja: "タイトル変更", en: "Title generation" })}<br />
                <select value={aiTitleModel} onChange={(e) => setAiTitleModel(e.target.value)} style={{ width: "100%", padding: 4 }}>
                  {AI_MODEL_OPTIONS.map((option) => (
                    <option key={`title-${option.value || "default"}`} value={option.value}>
                      {t({ ja: option.labelJa, en: option.labelEn })}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t({ ja: "タグ生成", en: "Tag generation" })}<br />
                <select value={aiTagModel} onChange={(e) => setAiTagModel(e.target.value)} style={{ width: "100%", padding: 4 }}>
                  {AI_MODEL_OPTIONS.map((option) => (
                    <option key={`tag-${option.value || "default"}`} value={option.value}>
                      {t({ ja: option.labelJa, en: option.labelEn })}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t({ ja: "AIチャット", en: "AI chat" })}<br />
                <select value={aiChatModel} onChange={(e) => setAiChatModel(e.target.value)} style={{ width: "100%", padding: 4 }}>
                  {AI_MODEL_OPTIONS.map((option) => (
                    <option key={`chat-${option.value || "default"}`} value={option.value}>
                      {t({ ja: option.labelJa, en: option.labelEn })}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t({ ja: "翻訳", en: "Translation" })}<br />
                <select value={aiTranslationModel} onChange={(e) => setAiTranslationModel(e.target.value)} style={{ width: "100%", padding: 4 }}>
                  {AI_MODEL_OPTIONS.map((option) => (
                    <option key={`translation-${option.value || "default"}`} value={option.value}>
                      {t({ ja: option.labelJa, en: option.labelEn })}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t({ ja: "AI小説ページの相談AI", en: "AI novel page helper" })}<br />
                <select value={aiStoryAgentModel} onChange={(e) => setAiStoryAgentModel(e.target.value)} style={{ width: "100%", padding: 4 }}>
                  {AI_MODEL_OPTIONS.map((option) => (
                    <option key={`agent-${option.value || "default"}`} value={option.value}>
                      {t({ ja: option.labelJa, en: option.labelEn })}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t({ ja: "AIコメント修正", en: "AI comment revision" })}<br />
                <select value={aiCommentRevisionModel} onChange={(e) => setAiCommentRevisionModel(e.target.value)} style={{ width: "100%", padding: 4 }}>
                  {AI_MODEL_OPTIONS.map((option) => (
                    <option key={`comment-revision-${option.value || "default"}`} value={option.value}>
                      {t({ ja: option.labelJa, en: option.labelEn })}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={aiStoryAgentVisible}
                  onChange={(e) => setAiStoryAgentVisible(e.target.checked)}
                />
                <span>
                  {t({
                    ja: "AI小説ページで小説相談AIを表示する",
                    en: "Show the novel helper AI on the AI novel page",
                  })}
                </span>
              </label>
            </div>
            <div style={{ marginTop: 8, fontSize: 12, color: "var(--muted-text)" }}>
              {t({
                ja: "初期設定は Gemini 3 Flash Preview です。項目ごとに別モデルへ変更できます。",
                en: "The default for these settings is Gemini 3 Flash Preview. You can still switch each feature to a different model.",
              })}
            </div>
          </fieldset>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "ユーザー名", en: "Username" })}{" "}
            <span style={{ color: "#c00" }}>*</span><br />
            <input
              type="text"
              value={username}
              onChange={(e)=>setUsername(e.target.value)}
              style={{ width:"100%", padding:4 }}
              required
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "メールアドレス", en: "Email" })}<br />
            <input
              type="email"
              value={email}
              onChange={(e)=>setEmail(e.target.value)}
              style={{ width:"100%", padding:4 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "ブックマーク公開設定", en: "Bookmark visibility" })}<br />
            <select
              value={favoriteVisibility}
              onChange={(e) => setFavoriteVisibility(e.target.value === "private" ? "private" : "public")}
              style={{ width: "100%", padding: 4 }}
            >
              <option value="public">{t({ ja: "公開", en: "Public" })}</option>
              <option value="private">{t({ ja: "非公開", en: "Private" })}</option>
            </select>
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "プロフィール文", en: "Profile bio" })}<br />
            <textarea
              value={profileBio}
              onChange={(e)=>setProfileBio(e.target.value)}
              rows={4}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "アイコン画像URL", en: "Icon image URL" })}<br />
            <input
              type="url"
              value={profileIconUrl}
              onChange={(e)=>setProfileIconUrl(e.target.value)}
              style={{ width:"100%", padding:4 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "ヘッダー画像URL", en: "Header image URL" })}<br />
            <input
              type="url"
              value={profileHeaderUrl}
              onChange={(e)=>setProfileHeaderUrl(e.target.value)}
              style={{ width:"100%", padding:4 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "WebサイトURL", en: "Website URL" })}<br />
            <input
              type="url"
              value={profileWebsiteUrl}
              onChange={(e)=>setProfileWebsiteUrl(e.target.value)}
              style={{ width:"100%", padding:4 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "X(Twitter) URL", en: "X (Twitter) URL" })}<br />
            <input
              type="url"
              value={profileXUrl}
              onChange={(e)=>setProfileXUrl(e.target.value)}
              style={{ width:"100%", padding:4 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "生年月日", en: "Birth date" })}{" "}
            <span style={{ color: "#c00" }}>*</span><br />
            <input
              type="date"
              value={birthDate}
              onChange={(e)=>setBirthDate(e.target.value)}
              style={{ width:"100%", padding:4 }}
              required
            />
          </label>
          <div style={{ marginTop: 4, fontSize: 12, color: "var(--muted-text)" }}>
            {t({
              ja: "年齢制限作品の閲覧に必要です。未入力だと保存や閲覧でエラーになる場合があります。",
              en: "This is required to view age-restricted works. If it is missing, saving or viewing may fail.",
            })}
          </div>
          <div style={{ marginTop: 8 }}>
            <button
              type="button"
              className="btn btn-border"
              onClick={() => setShowBirthSlider((prev) => !prev)}
            >
              {showBirthSlider
                ? t({ ja: "スライダー入力を閉じる", en: "Hide slider input" })
                : t({ ja: "スライダーで入力する", en: "Use slider input" })}
            </button>
          </div>
          {showBirthSlider && (
            <div style={{ marginTop: 8, display: "grid", gap: 8 }}>
              <label style={{ display: "grid", gap: 4 }}>
                <span>
                  {t({ ja: "年", en: "Year" })}: {birthParts.year}
                </span>
                <input
                  type="range"
                  min={BIRTH_YEAR_MIN}
                  max={birthYearMax}
                  value={birthParts.year}
                  onChange={(e) => updateBirthDateBySlider("year", e.target.value)}
                  style={{ width: "100%" }}
                />
              </label>
              <label style={{ display: "grid", gap: 4 }}>
                <span>
                  {t({ ja: "月", en: "Month" })}: {birthParts.month}
                </span>
                <input
                  type="range"
                  min={1}
                  max={12}
                  value={birthParts.month}
                  onChange={(e) => updateBirthDateBySlider("month", e.target.value)}
                  style={{ width: "100%" }}
                />
              </label>
              <label style={{ display: "grid", gap: 4 }}>
                <span>
                  {t({ ja: "日", en: "Day" })}: {birthParts.day}
                </span>
                <input
                  type="range"
                  min={1}
                  max={daysInMonth(birthParts.year, birthParts.month)}
                  value={birthParts.day}
                  onChange={(e) => updateBirthDateBySlider("day", e.target.value)}
                  style={{ width: "100%" }}
                />
              </label>
            </div>
          )}
        </div>

        {error && <p style={{ color:"red" }}>{error}</p>}

        <button className="btn btn-border" type="submit" disabled={saving}>
          {saving ? t({ ja: "保存中...", en: "Saving..." }) : t({ ja: "保存する", en: "Save" })}
        </button>
      </form>
    </div>
  );
}
