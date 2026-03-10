import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSavedTheme, setTheme } from "../theme";
import { useI18n } from "../lib/i18n";

const MYPAGE_SHOW_CHATBOT_STORAGE_KEY = "mypage_show_chatbot";
const BIRTH_YEAR_MIN = 1900;

const pad2 = (n) => String(n).padStart(2, "0");
const formatBirthDate = (year, month, day) => `${year}-${pad2(month)}-${pad2(day)}`;
const daysInMonth = (year, month) => new Date(year, month, 0).getDate();
const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
const formatApiErrorDetail = (detail, fallback, t) => {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const birthDateIssue = detail.find((item) => {
      const loc = Array.isArray(item?.loc) ? item.loc : [];
      return loc.includes("birth_date");
    });
    if (birthDateIssue) {
      return t({ ja: "生年月日は必須です。", en: "Birth date is required." });
    }
    const firstMsg = detail.find((item) => typeof item?.msg === "string" && item.msg.trim());
    if (firstMsg) return firstMsg.msg;
  }
  if (detail && typeof detail === "object") {
    if (typeof detail.message === "string" && detail.message.trim()) return detail.message;
    if (typeof detail.msg === "string" && detail.msg.trim()) return detail.msg;
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }
  return fallback;
};

const parseBirthDate = (value, maxYear) => {
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
  const [profileBio, setProfileBio] = useState("");
  const [profileIconUrl, setProfileIconUrl] = useState("");
  const [profileHeaderUrl, setProfileHeaderUrl] = useState("");
  const [profileWebsiteUrl, setProfileWebsiteUrl] = useState("");
  const [profileXUrl, setProfileXUrl] = useState("");
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

  const updateBirthDateBySlider = (part, rawValue) => {
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
      .then((data) => {
        if (!data) return;
        setUsername(data.username || "");
        setEmail(data.email || "");
        setBirthDate(data.birth_date || "");
        setFavoriteVisibility(
          data.favorite_visibility === "private" ? "private" : "public"
        );
        setProfileBio(data.profile_bio || "");
        setProfileIconUrl(data.profile_icon_url || "");
        setProfileHeaderUrl(data.profile_header_url || "");
        setProfileWebsiteUrl(data.profile_website_url || "");
        setProfileXUrl(data.profile_x_url || "");
      })
      .catch((e) =>
        setError(e.message || t({ ja: "プロフィール取得に失敗しました", en: "Failed to load profile." }))
      )
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleChangeTheme = (nextTheme) => {
    try {
      const normalized = setTheme(nextTheme);
      setThemeState(normalized);
    } catch {
      setThemeState(nextTheme === "dark" ? "dark" : "light");
    }
  };

  const handleSubmit = async (e) => {
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
          profile_bio: profileBio,
          profile_icon_url: profileIconUrl,
          profile_header_url: profileHeaderUrl,
          profile_website_url: profileWebsiteUrl,
          profile_x_url: profileXUrl,
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
        } catch (_) {
          msg = t(
            { ja: "保存に失敗しました (HTTP {{status}})", en: "Failed to save (HTTP {{status}})" },
            { status: res.status }
          );
        }
        throw new Error(msg);
      }

      localStorage.setItem("username", username);
      alert(t({ ja: "保存しました。", en: "Saved." }));
    } catch (e) {
      setError(e.message || t({ ja: "保存に失敗しました", en: "Failed to save." }));
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
                onChange={(e) => setShowChatbot(e.target.checked)}
              />
              <span>
                {t({
                  ja: "チャットbotを表示（AIチャットで使用モデルを表示）",
                  en: "Show chatbot info (show model in AI chat)",
                })}
              </span>
            </label>
          </fieldset>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "ユーザー名", en: "Username" })}<br />
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
            {t({ ja: "生年月日", en: "Birth date" })}<br />
            <input
              type="date"
              value={birthDate}
              onChange={(e)=>setBirthDate(e.target.value)}
              style={{ width:"100%", padding:4 }}
            />
          </label>
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
