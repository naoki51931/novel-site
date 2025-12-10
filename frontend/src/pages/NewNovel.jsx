import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";

const API_BASE = "";
const DRAFT_KEY = "draft_new_novel";

export default function NewNovel() {
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tagNamesInput, setTagNamesInput] = useState("");

  const [ageLimit, setAgeLimit] = useState("all");           // 全年齢 / R15 / R18
  const [isAIGenerated, setIsAIGenerated] = useState(false); // AI創作フラグ
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

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
      setError("タイトルは必須です。");
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        throw new Error("ログインが必要です。");
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
        throw new Error(data.detail || "小説の作成に失敗しました");
      }

      if (data.id) {
        localStorage.removeItem(DRAFT_KEY);
        navigate(`/novels/${data.id}`);
      } else {
        localStorage.removeItem(DRAFT_KEY);
        navigate("/");
      }
    } catch (err) {
      console.error(err);
      setError(err.message || "小説の作成中にエラーが発生しました");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← 小説一覧に戻る</Link>
      </div>

      <h2>新しい小説を作成</h2>

      {/* 🔹 AI小説生成ページへのショートカットボタン */}
      <div style={{ marginBottom: 16 }}>
        <button
          type="button"
          className="btn btn-border"
          onClick={handleOpenAINovel}
        >
          AI小説生成ページへ
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            タイトル
            <br />
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            説明（あらすじ）
            <br />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            タグ（カンマ区切り）
            <br />
            <input
              type="text"
              value={tagNamesInput}
              onChange={(e) => setTagNamesInput(e.target.value)}
              style={{ width: "100%", padding: 4 }}
              placeholder="例: ファンタジー, バトル, 百合"
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            年齢区分
            <br />
            <select
              value={ageLimit}
              onChange={(e) => setAgeLimit(e.target.value)}
              style={{ width: "100%", padding: 4 }}
            >
              <option value="all">全年齢</option>
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
            AI創作
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
            {saving ? "作成中..." : "作成する"}
          </button>
          <button
            className="btn btn-border"
            type="button"
            onClick={() => navigate("/")}
          >
            キャンセル
          </button>
        </div>
      </form>
    </div>
  );
}
