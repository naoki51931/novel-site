import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function EditEpisode() {
  const { episodeId } = useParams();
  const navigate = useNavigate();
  const [novelId, setNovelId] = useState(null);
  const [episodeNumber, setEpisodeNumber] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const run = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/episodes/${episodeId}`);
        if (!res.ok) throw new Error("エピソードの取得に失敗しました");
        const data = await res.json();
        setNovelId(data.novel_id);
        setEpisodeNumber(data.episode_number);
        setTitle(data.title);
        setBody(data.body);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [episodeId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/episodes/${episodeId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          episode_number: Number(episodeNumber),
          title,
          body,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "更新に失敗しました");
      }
      navigate(`/novels/${novelId}`);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("このエピソードを削除しますか？")) return;
    try {
      const res = await fetch(`${API_BASE}/api/episodes/${episodeId}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "削除に失敗しました");
      }
      if (novelId) {
        navigate(`/novels/${novelId}`);
      } else {
        navigate("/");
      }
    } catch (e) {
      setError(String(e));
    }
  };

  if (loading) return <p>読み込み中...</p>;

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        {novelId && <Link to={`/novels/${novelId}`}>← 小説詳細に戻る</Link>}
      </div>
      <h2>エピソードを編集</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            話数
            <br />
            <input
              type="number"
              value={episodeNumber}
              onChange={(e) => setEpisodeNumber(e.target.value)}
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
              style={{ width: "100%" }}
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
              style={{ width: "100%" }}
            />
          </label>
        </div>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit" className="btn btn-border">
          更新する
        </button>
        <button
          type="button"
          className="btn btn-border"
          style={{ marginLeft: 8 }}
          onClick={handleDelete}
        >
          削除する
        </button>
      </form>
    </div>
  );
}
