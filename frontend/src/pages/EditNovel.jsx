import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function EditNovel() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const run = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/novels/${id}`);
        if (!res.ok) throw new Error("小説の取得に失敗しました");
        const data = await res.json();
        setTitle(data.title);
        setDescription(data.description || "");
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [id]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/novels/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, description }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "更新に失敗しました");
      }
      navigate(`/novels/${id}`);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("この小説を削除しますか？（エピソードも削除されます）")) return;
    try {
      const res = await fetch(`${API_BASE}/api/novels/${id}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "削除に失敗しました");
      }
      navigate("/");
    } catch (e) {
      setError(String(e));
    }
  };

  if (loading) return <p>読み込み中...</p>;

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to={`/novels/${id}`}>← 小説詳細に戻る</Link>
      </div>
      <h2>小説を編集</h2>
      <form onSubmit={handleSubmit}>
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
            説明
            <br />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
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
