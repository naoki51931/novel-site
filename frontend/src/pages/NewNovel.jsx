import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { trackEvent } from "../lib/analytics";
import { useI18n } from "../lib/i18n";

const API_BASE = import.meta.env.VITE_BACKEND_ORIGIN || "https://shosetsu-toukou-site.org";
const DRAFT_KEY = "draft_new_novel";

export default function NewNovel() {
  const navigate = useNavigate();
  const { t } = useI18n();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tagNamesInput, setTagNamesInput] = useState("");

  const [ageLimit, setAgeLimit] = useState("all");           // 全年齢 / R15 / R18
  const [isAIGenerated, setIsAIGenerated] = useState(false); // AI創作フラグ
  const [creativeType, setCreativeType] = useState("original"); // オリジナル / 二次創作
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const countChars = (value) => (value || "").length;

  // 🔹 AI小説生成ページへ移動
  const handleOpenAINovel = () => {
    navigate("/ai-novel");
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
        saved_at: new Date().toISOString(),
      };
      try {
        localStorage.setItem(DRAFT_KEY, JSON.stringify(payload));
      } catch (e) {
        console.error("failed to save draft", e);
      }
    }, 1000);

    return () => clearTimeout(timer);
  }, [title, description, tagNamesInput]);
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

      if (data.id) {
        localStorage.removeItem(DRAFT_KEY);
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

      <h2>{t({ ja: "新しい小説を作成", en: "Create New Novel" })}</h2>

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
