import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function NewEpisode() {
  const { id } = useParams(); // novel_id
  const navigate = useNavigate();

  const [episodeNumber, setEpisodeNumber] = useState(1);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!title.trim()) {
      setError("タイトルは必須です。");
      return;
    }
    if (!body.trim()) {
      setError("本文は必須です。");
      return;
    }

    const payload = {
      episode_number: Number(episodeNumber),
      title,
      body,
    };

    console.log("📥 POST /api/novels/:id/episodes payload:", payload);

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/novels/${id}/episodes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      let data = null;
      try {
        data = await res.json();
      } catch (_) {}

      console.log("📤 /api/novels/:id/episodes response:", res.status, data);

      if (!res.ok) {
        throw new Error(
          (data && data.detail) ||
            `エピソードの投稿に失敗しました (status=${res.status})`
        );
      }

      // 成功したら小説詳細へ戻る
      navigate(`/novels/${id}`);
    } catch (err) {
      console.error("❌ NewEpisode error:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>新しいエピソードを投稿</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            話数
            <br />
            <input
              type="number"
              value={episodeNumber}
              onChange={(e) => setEpisodeNumber(e.target.value)}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>
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
            本文
            <br />
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={10}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button className="btn btn-border" type="submit" disabled={loading}>
          {loading ? "投稿中..." : "投稿する"}
        </button>
      </form>
    </div>
  );
}
