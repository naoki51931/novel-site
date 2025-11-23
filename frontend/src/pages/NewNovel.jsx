import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

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

    const token = localStorage.getItem("token");
    if (!token) {
      setError("小説を投稿するにはログインが必要です。");
      navigate("/login");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/novels`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        body: JSON.stringify({
          title,
          description,
        }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || `投稿に失敗しました (status=${res.status})`);
      }

      navigate(`/novels/${data.id}`);
    } catch (err) {
      console.error(err);
      setError(err.message || "投稿に失敗しました。");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← 一覧に戻る</Link>
      </div>
      <h2>新規小説投稿</h2>
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
        {error && (
          <p style={{ color: "red", marginTop: 4, marginBottom: 8 }}>{error}</p>
        )}
        <button className="btn btn-border" type="submit" disabled={loading}>
          {loading ? "投稿中..." : "投稿する"}
        </button>
      </form>
    </div>
  );
}
