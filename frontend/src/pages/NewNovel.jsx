import { useState } from "react";
import { useNavigate } from "react-router-dom";

const API_BASE = "http://35.179.170.65";

export default function NewNovel() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!title.trim()) {
      setError("タイトルは必須です。");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/novels`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title,
          description: description || null,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "投稿に失敗しました");
      }

      const novel = await res.json();
      navigate(`/novels/${novel.id}`);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>新しい小説を投稿</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            タイトル（必須）
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
            説明・あらすじ（任意）
            <br />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? "投稿中..." : "投稿する"}
        </button>
      </form>
    </div>
  );
}
