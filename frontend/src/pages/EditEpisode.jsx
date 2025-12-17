import {useEffect, useState, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

const API_BASE = "";
const EDIT_EPISODE_DRAFT_PREFIX = "edit_episode_draft";


export default function EditEpisode() {
  const { id } = useParams(); // episode_id
  const navigate = useNavigate();

  const [novelId, setNovelId] = useState(null);
  const [episodeNumber, setEpisodeNumber] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [tags, setTags] = useState(""); // ★ タグ state

  // ★ 表紙・押絵用の state
  const [coverImageUrl, setCoverImageUrl] = useState("");
  const [illusts, setIllusts] = useState([]);

  const [coverFile, setCoverFile] = useState(null);
  const [isUploadingCover, setIsUploadingCover] = useState(false);

  const [illustFile, setIllustFile] = useState(null);
  const [illustCaption, setIllustCaption] = useState("");
  const [isUploadingIllust, setIsUploadingIllust] = useState(false);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // draft を読んだかどうかのフラグ
  const hasDraftRef = useRef(false);

  // === auto-save edit episode draft start ===
  useEffect(() => {
    if (!id) return;
    const key = `${EDIT_EPISODE_DRAFT_PREFIX}_${id}`;
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return;
      const draft = JSON.parse(raw);
      hasDraftRef.current = true;
      if (draft.episodeNumber !== undefined && draft.episodeNumber !== null) {
        setEpisodeNumber(String(draft.episodeNumber));
      }
      if (draft.title) setTitle(draft.title);
      if (draft.body) setBody(draft.body);
      if (typeof draft.tags === "string") setTags(draft.tags);
    } catch (e) {
      console.error("failed to load edit episode draft", e);
    }
  }, [id]);

  useEffect(() => {
    if (!id) return;
    const key = `${EDIT_EPISODE_DRAFT_PREFIX}_${id}`;
    const timer = setTimeout(() => {
      const payload = {
        episodeNumber,
        title,
        body,
        tags,
        saved_at: new Date().toISOString(),
      };
      try {
        localStorage.setItem(key, JSON.stringify(payload));
      } catch (e) {
        console.error("failed to save edit episode draft", e);
      }
    }, 1000);
    return () => clearTimeout(timer);
  }, [id, episodeNumber, title, body, tags]);
  // === auto-save edit episode draft end ===

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

        const res = await fetch(`${API_BASE}/api/episodes/${id}/edit`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.status === 401) {
          try {
            localStorage.removeItem("token");
          } catch {}
          navigate("/login");
          return;
        }
        if (!res.ok) {
          throw new Error(`エピソード情報の取得に失敗しました (${res.status})`);
        }

        const data = await res.json();
        setNovelId(data.novel_id);

        // draft を読み込んでいない場合だけ API の内容で上書き
        if (!hasDraftRef.current) {
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
          if (Array.isArray(data.tags)) {
            setTags(data.tags.map((t) => t.name).join(", "));
          } else {
            setTags("");
          }
        }


        // ★ 表紙・押絵も state に取り込む
        setCoverImageUrl(data.cover_image_url || "");
        setIllusts(Array.isArray(data.illusts) ? data.illusts : []);
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
          // ★ 編集時も tag_names を送る
          tag_names: tags
            .split(",")
            .map((s) => s.trim())
            .filter((s) => s.length > 0),
        }),
      });

      const data = await res.json().catch(() => ({}));

      if (res.status === 401) {
        try {
          localStorage.removeItem("token");
        } catch {}
        navigate("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(data.detail || "エピソードの更新に失敗しました");
      }

      // 更新成功したので、このエピソードの下書きを削除
      if (id) {
        const key = `${EDIT_EPISODE_DRAFT_PREFIX}_${id}`;
        try {
          localStorage.removeItem(key);
        } catch (e) {
          console.error("failed to clear edit episode draft", e);
        }
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

  // =========================
  // 表紙アップロード系
  // =========================
  const handleCoverFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setCoverFile(e.target.files[0]);
    }
  };

  const handleCoverUpload = async () => {
    if (!coverFile) {
      alert("表紙画像ファイルを選択してください");
      return;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      alert("ログインが必要です。");
      navigate("/login");
      return;
    }

    const formData = new FormData();
    formData.append("file", coverFile);

    try {
      setIsUploadingCover(true);

      const res = await fetch(`${API_BASE}/api/episodes/${id}/cover-image`, {
        method: "POST",
        headers: {
          Authorization: "Bearer " + token,
        },
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "表紙のアップロードに失敗しました");
      }

      const data = await res.json();
      setCoverImageUrl(data.cover_image_url || "");
      setCoverFile(null);
      alert("表紙画像を更新しました");
    } catch (e) {
      console.error(e);
      alert(e.message || "表紙のアップロード中にエラーが発生しました");
    } finally {
      setIsUploadingCover(false);
    }
  };

  const handleCoverDelete = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      alert("ログインが必要です");
      return;
    }
    if (!window.confirm("本当に表紙を削除しますか？")) return;

    const res = await fetch(`${API_BASE}/api/episodes/${id}/cover-image`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      alert("削除に失敗しました");
      return;
    }

    setCoverImageUrl("");
    alert("表紙を削除しました");
  };

  // =========================
  // 押絵アップロード系
  // =========================
  const handleIllustFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setIllustFile(e.target.files[0]);
    }
  };

  const handleIllustUpload = async () => {
    if (!illustFile) {
      alert("押絵画像ファイルを選択してください");
      return;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      alert("ログインが必要です。");
      navigate("/login");
      return;
    }

    const formData = new FormData();
    formData.append("file", illustFile);
    formData.append("caption", illustCaption || "");

    try {
      setIsUploadingIllust(true);

      const res = await fetch(`${API_BASE}/api/episodes/${id}/illusts`, {
        method: "POST",
        headers: {
          Authorization: "Bearer " + token,
        },
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "押絵のアップロードに失敗しました");
      }

      const newIllust = await res.json();
      setIllusts((prev) => [...prev, newIllust]);
      setIllustFile(null);
      setIllustCaption("");
      alert("押絵を追加しました");
    } catch (e) {
      console.error(e);
      alert(e.message || "押絵のアップロード中にエラーが発生しました");
    } finally {
      setIsUploadingIllust(false);
    }
  };

  const handleIllustDelete = async (illustId) => {
    const token = localStorage.getItem("token");
    if (!token) {
      alert("ログインが必要です");
      return;
    }
    if (!window.confirm("押絵を削除しますか？")) return;

    const res = await fetch(
      `${API_BASE}/api/episodes/${id}/illusts/${illustId}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      }
    );

    if (!res.ok) {
      alert("削除に失敗しました");
      return;
    }

    setIllusts((prev) => prev.filter((ill) => ill.id !== illustId));
    alert("押絵を削除しました");
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

        {error && (
          <p style={{ color: "red", marginTop: 4, marginBottom: 8 }}>
            {error}
          </p>
        )}

        <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
          <button className="btn btn-border" type="submit" disabled={saving}>
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

      {/* =========================
          表紙編集セクション
          ========================= */}
      <div
        style={{
          marginTop: 16,
          marginBottom: 16,
          padding: 12,
          borderRadius: 8,
          border: "1px solid #ddd",
        }}
      >
        <h3 style={{ marginTop: 0 }}>表紙画像</h3>

        {coverImageUrl ? (
          <div style={{ marginBottom: 12 }}>
            <img
              src={coverImageUrl}
              alt="表紙画像"
              style={{ maxWidth: "100%", borderRadius: 8 }}
            />
            <div style={{ marginTop: 8 }}>
              <button
                type="button"
                className="btn btn-border"
                onClick={handleCoverDelete}
              >
                表紙を削除
              </button>
            </div>
          </div>
        ) : (
          <p style={{ color: "#777" }}>表紙画像はまだ設定されていません。</p>
        )}

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 8,
            alignItems: "center",
          }}
        >
          <input type="file" accept="image/*" onChange={handleCoverFileChange} />
          <button
            type="button"
            className="btn btn-border"
            onClick={handleCoverUpload}
            disabled={isUploadingCover || !coverFile}
          >
            {isUploadingCover ? "アップロード中..." : "表紙としてアップロード"}
          </button>
        </div>
      </div>

      {/* =========================
          押絵編集セクション
          ========================= */}
      <div
        style={{
          marginTop: 16,
          marginBottom: 16,
          padding: 12,
          borderRadius: 8,
          border: "1px solid #ddd",
        }}
      >
        <h3 style={{ marginTop: 0 }}>押絵</h3>

        {illusts.length > 0 ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))",
              gap: 12,
              marginBottom: 12,
            }}
          >
            {illusts.map((illust) => (
              <div
                key={illust.id ?? illust.image_url}
                style={{
                  border: "1px solid #eee",
                  borderRadius: 8,
                  padding: 8,
                  textAlign: "center",
                }}
              >
                <img
                  src={illust.image_url}
                  alt={illust.caption || "押絵"}
                  style={{ maxWidth: "100%", borderRadius: 4 }}
                />
                {illust.caption && (
                  <div style={{ marginTop: 4, fontSize: 12 }}>
                    {illust.caption}
                  </div>
                )}
                {illust.id && (
                  <button
                    type="button"
                    className="btn btn-border"
                    style={{ marginTop: 6 }}
                    onClick={() => handleIllustDelete(illust.id)}
                  >
                    押絵を削除
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: "#777" }}>まだ押絵が登録されていません。</p>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <input
            type="file"
            accept="image/*"
            onChange={handleIllustFileChange}
          />
          <input
            type="text"
            placeholder="キャプション（任意）"
            value={illustCaption}
            onChange={(e) => setIllustCaption(e.target.value)}
          />
          <button
            type="button"
            className="btn btn-border"
            onClick={handleIllustUpload}
            disabled={isUploadingIllust || !illustFile}
          >
            {isUploadingIllust ? "アップロード中..." : "押絵を追加"}
          </button>
        </div>
      </div>
    </div>
  );
}
