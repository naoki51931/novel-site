import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function EditEpisode() {
  const { id } = useParams(); // episode_id
  const navigate = useNavigate();

  const [novelId, setNovelId] = useState(null);
  const [episodeNumber, setEpisodeNumber] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      navigate("/login");
      return;
    }

    const fetchEpisode = async () => {
      try {
        setLoading(true);
        setError("");

        const res = await fetch(`${API_BASE}/api/episodes/${id}`);
        if (!res.ok) {
          throw new Error(`エピソード情報の取得に失敗しました (${res.status})`);
        }

        const data = await res.json();
        setNovelId(data.novel_id);
        setEpisodeNumber(
          String(
            data.number != null
              ? data.number
              : data.episode_number != null
              ? data.episode_number
              : ""
          )
        );
        setTitle(data.title || "");
        setBody(data.body || "");
      } catch (err) {
        console.error(err);
        setError(err.message || "エピソード情報の取得中にエラーが発生しました");
      } finally {
        setLoading(false);
      }
    };

    fetchEpisode();
  }, [id, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!episodeNumber || isNaN(Number(episodeNumber))) {
      setError("話数は数字で入力してください。");
      return;
    }
    if (!title.trim()) {
      setError("タイトルは必須です。");
      return;
    }
    if (!body.trim()) {
      setError("本文は必須です。");
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        throw new Error("ログインが必要です。");
      }

      const res = await fetch(`${API_BASE}/api/episodes/${id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        body: JSON.stringify({
          episode_number: Number(episodeNumber),
          title,
          body,
        }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || "エピソードの更新に失敗しました");
      }

      const targetNovelId =
        (data && data.novel_id) != null ? data.novel_id : novelId;
      if (targetNovelId != null) {
        navigate(`/novels/${targetNovelId}`);
      } else {
        navigate(-1);
      }
    } catch (err) {
      console.error(err);
      setError(err.message || "エピソードの更新中にエラーが発生しました");
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    if (novelId != null) {
      navigate(`/novels/${novelId}`);
    } else {
      navigate(-1);
    }
  };

  if (loading) {
    return <p>読み込み中...</p>;
  }

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        {novelId != null ? (
          <Link to={`/novels/${novelId}`}>← 小説詳細に戻る</Link>
        ) : (
          <button
            className="btn btn-border"
            type="button"
            onClick={() => navigate(-1)}
          >
            ← 戻る
          </button>
        )}
      </div>

      <h2>エピソードを編集</h2>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            話数（例: 1, 2, 3）
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

        {error && (
          <p style={{ color: "red", marginTop: 4, marginBottom: 8 }}>{error}</p>
        )}

        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="btn btn-border"
            type="submit"
            disabled={saving}
          >
            {saving ? "更新中..." : "更新する"}
          </button>
          <button
            className="btn btn-border"
            type="button"
            onClick={handleCancel}
          >
            キャンセル
          </button>
        </div>
      </form>
    </div>
  );
}
