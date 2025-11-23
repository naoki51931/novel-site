import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://18.169.218.56/api";

function EditEpisode() {
  const { id } = useParams(); // episode id
  const navigate = useNavigate();

  const [novelId, setNovelId] = useState(null);
  const [number, setNumber] = useState(1);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchEpisode = async () => {
      try {
        const res = await fetch(`${API_BASE}/episodes/${id}`);
        if (!res.ok) {
          throw new Error("エピソード情報の取得に失敗しました (" + res.status + ")");
        }
        const data = await res.json();
        setNovelId(data.novel_id);
        setNumber(data.number);
        setTitle(data.title);
        setBody(data.body);
      } catch (err) {
        console.error(err);
        setError(err.message || "エピソード情報の取得に失敗しました");
      } finally {
        setLoading(false);
      }
    };

    fetchEpisode();
  }, [id]);

  const handleUpdate = async (e) => {
    e.preventDefault();
    setError("");

    try {
      const res = await fetch(`${API_BASE}/episodes/${id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          number,
          title,
          body,
        }),
      });

      if (!res.ok) {
        throw new Error("エピソード情報の取得に失敗しました (" + res.status + ")");
      }

      if (novelId) {
        navigate(`/novels/${novelId}`);
      } else {
        navigate(-1);
      }
    } catch (err) {
      console.error(err);
      setError(err.message || "更新に失敗しました");
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("このエピソードを削除しますか？")) return;

    try {
      const res = await fetch(`${API_BASE}/episodes/${id}`, {
        method: "DELETE",
      });

      if (!res.ok && res.status !== 204) {
        throw new Error("エピソード情報の取得に失敗しました (" + res.status + ")");
      }

      if (novelId) {
        navigate(`/novels/${novelId}`);
      } else {
        navigate("/");
      }
    } catch (err) {
      console.error(err);
      setError(err.message || "削除に失敗しました");
    }
  };

  if (loading) return <div>読み込み中...</div>;

  return (
    <div className="edit-episode-container">
      <h1>エピソードを編集</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <form onSubmit={handleUpdate}>
        <div>
          <label>話数</label>
          <input
            type="number"
            value={number}
            onChange={(e) => setNumber(Number(e.target.value))}
          />
        </div>

        <div>
          <label>タイトル</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        <div>
          <label>本文</label>
          <textarea
            rows={10}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        </div>

        <div className="edit-episode-actions">
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

export default EditEpisode;
