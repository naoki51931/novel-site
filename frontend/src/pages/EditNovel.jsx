import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://18.169.218.56/api";

function EditNovel() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchNovel = async () => {
      try {
        const res = await fetch(`${API_BASE}/novels/${id}`);
        if (!res.ok) {
          throw new Error(\`小説情報の取得に失敗しました (\${res.status})\`);
        }
        const data = await res.json();
        setTitle(data.title);
        setDescription(data.description);
      } catch (err) {
        console.error(err);
        setError(err.message || "小説情報の取得に失敗しました");
      } finally {
        setLoading(false);
      }
    };

    fetchNovel();
  }, [id]);

  const handleUpdate = async (e) => {
    e.preventDefault();
    setError("");

    try {
      const res = await fetch(`${API_BASE}/novels/${id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ title, description }),
      });

      if (!res.ok) {
        throw new Error(\`更新に失敗しました (\${res.status})\`);
      }

      navigate(`/novels/${id}`);
    } catch (err) {
      console.error(err);
      setError(err.message || "更新に失敗しました");
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("この小説を削除しますか？（エピソードも削除されます）")) return;

    try {
      const res = await fetch(`${API_BASE}/novels/${id}`, {
        method: "DELETE",
      });

      if (!res.ok && res.status !== 204) {
        throw new Error(\`削除に失敗しました (\${res.status})\`);
      }

      navigate("/");
    } catch (err) {
      console.error(err);
      setError(err.message || "削除に失敗しました");
    }
  };

  if (loading) return <div>読み込み中...</div>;

  return (
    <div className="edit-novel-container">
      <h1>小説を編集</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <form onSubmit={handleUpdate}>
        <div>
          <label>タイトル</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        <div>
          <label>あらすじ</label>
          <textarea
            rows={6}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />

        </div>

        <div className="edit-novel-actions">
          <button className="btn btn-border" type="submit">
            更新
          </button>
          <button
            className="btn btn-border"
            type="button"
            onClick={() => navigate(-1)}
          >
            戻る
          </button>
          <button
            className="btn btn-border"
            type="button"
            onClick={handleDelete}
          >
            削除
          </button>
        </div>
      </form>
    </div>
  );
}

export default EditNovel;
