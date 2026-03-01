import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSavedTheme, setTheme } from "../theme";
import { useI18n } from "../lib/i18n";

const MYPAGE_SHOW_CHATBOT_STORAGE_KEY = "mypage_show_chatbot";

export default function AccountSettings() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [birthDate, setBirthDate] = useState("");
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
          if (d && d.detail) msg = d.detail;
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
            {t({ ja: "生年月日", en: "Birth date" })}<br />
            <input
              type="date"
              value={birthDate}
              onChange={(e)=>setBirthDate(e.target.value)}
              style={{ width:"100%", padding:4 }}
            />
          </label>
        </div>

        {error && <p style={{ color:"red" }}>{error}</p>}

        <button className="btn btn-border" type="submit" disabled={saving}>
          {saving ? t({ ja: "保存中...", en: "Saving..." }) : t({ ja: "保存する", en: "Save" })}
        </button>
      </form>
    </div>
  );
}
