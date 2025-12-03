import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";

const API_BASE = "";

export default function NewNovel() {
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [ageLimit, setAgeLimit] = useState("all");           // 全年齢 / R15 / R18
  const [isAIGenerated, setIsAIGenerated] = useState(false); // AI創作フラグ
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

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

      const res = await fetch(`${API_BASE}/api/novels/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        body: JSON.stringify({
          title,
          description,
          age_limit: ageLimit,
          is_ai_generated: isAIGenerated,
        }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || "小説の作成に失敗しました");
      }

      if (data.id) {
        navigate(`/novels/${data.id}`);
      } else {
        navigate("/novels");
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
        <Link to="/novels">← 小説一覧に戻る</Link>
      </div>

      <h2>新しい小説を作成</h2>

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
            onClick={() => navigate("/novels")}
          >
            キャンセル
          </button>
        </div>
      </form>
    </div>
  );
}
