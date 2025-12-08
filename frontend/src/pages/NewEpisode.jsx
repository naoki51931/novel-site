import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

const API_BASE = "";
const draftKey = `draft_new_episode_${id}`;

export default function NewEpisode() {
  const { id } = useParams(); // novel_id
  const navigate = useNavigate();

  const [episodeNumber, setEpisodeNumber] = useState(1);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [tags, setTags] = useState("");          // ★ タグ用 state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // === auto-save episode draft start ===
  // マウント時に下書きを読み込む
  useEffect(() => {
    try {
      const raw = localStorage.getItem(draftKey);
      if (!raw) return;
      const draft = JSON.parse(raw);
      if (draft.episodeNumber !== undefined) setEpisodeNumber(draft.episodeNumber);
      if (draft.title) setTitle(draft.title);
      if (draft.body) setBody(draft.body);
      if (draft.tags) setTags(draft.tags);
    } catch (e) {
      console.error("failed to load episode draft", e);
    }
  }, []);

  // 入力が変わるたび 1秒後に自動保存
  useEffect(() => {
    const timer = setTimeout(() => {
      const payload = {
        episodeNumber,
        title,
        body,
        tags,
        saved_at: new Date().toISOString(),
      };
      try {
        localStorage.setItem(draftKey, JSON.stringify(payload));
      } catch (e) {
        console.error("failed to save episode draft", e);
      }
    }, 1000);

    return () => clearTimeout(timer);
  }, [episodeNumber, title, body, tags]);
  // === auto-save episode draft end ===


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
      // ★ カンマ区切りの文字列 → 配列に変換
      tag_names: tags
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s.length > 0),
    };

    console.log("📥 POST /api/novels/:id/episodes payload:", payload);

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/novels/${id}/episodes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + localStorage.getItem("token"),
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

      // 成功したら下書きを消して小説詳細へ戻る
      localStorage.removeItem(draftKey);
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

        {/* ★ タグ入力欄 */}
        <div style={{ marginBottom: 8 }}>
          <label>
            タグ (カンマ区切り)
            <br />
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="例: バトル, 日常, 百合"
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

