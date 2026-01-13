import {useEffect, useState, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";

const API_BASE = "";
const EDIT_EPISODE_DRAFT_PREFIX = "edit_episode_draft";
const ILLUST_TAG_PREFIX = "illust:";
const ILLUST_TAG_RE = /^illust:(\d{8})$/;
const ILLUST_TAG_BRACKET_RE = /^\[\[illust:(\d{8})\]\]$/;

const generateIllustTag = (usedTags) => {
  const makeCandidate = () =>
    `${ILLUST_TAG_PREFIX}${Math.floor(10000000 + Math.random() * 90000000)}`;
  let candidate = makeCandidate();
  let attempts = 0;
  while (usedTags.has(candidate) && attempts < 10) {
    candidate = makeCandidate();
    attempts += 1;
  }
  if (usedTags.has(candidate)) {
    const fallback = `${ILLUST_TAG_PREFIX}${String(Date.now()).slice(-8)}`;
    if (!usedTags.has(fallback)) {
      return fallback;
    }
  }
  return candidate;
};

const normalizeIllustTag = (rawTag) => {
  const trimmed = (rawTag || "").trim();
  if (!trimmed) return null;
  let match = trimmed.match(ILLUST_TAG_RE);
  if (match) return `${ILLUST_TAG_PREFIX}${match[1]}`;
  match = trimmed.match(ILLUST_TAG_BRACKET_RE);
  if (match) return `${ILLUST_TAG_PREFIX}${match[1]}`;
  return null;
};

const formatIllustTag = (tag) => {
  const match = (tag || "").trim().match(ILLUST_TAG_RE);
  if (!match) return tag;
  return `[[illust:${match[1]}]]`;
};

export default function EditEpisode() {
  const { id } = useParams(); // episode_id
  const navigate = useNavigate();
  const { t } = useI18n();

  const [novelId, setNovelId] = useState(null);
  const [episodeNumber, setEpisodeNumber] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [tags, setTags] = useState(""); // ★ タグ state
  const [status, setStatus] = useState("public"); // "public" / "draft"

  // ★ 表紙・押絵用の state
  const [coverImageUrl, setCoverImageUrl] = useState("");
  const [illusts, setIllusts] = useState([]);

  const [coverFile, setCoverFile] = useState(null);
  const [isUploadingCover, setIsUploadingCover] = useState(false);

  const [illustFile, setIllustFile] = useState(null);
  const [illustCaption, setIllustCaption] = useState("");
  const [illustTag, setIllustTag] = useState("");
  const [illustMetaTags, setIllustMetaTags] = useState("");
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
      if (draft.status) setStatus(draft.status);
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
        status,
        saved_at: new Date().toISOString(),
      };
      try {
        localStorage.setItem(key, JSON.stringify(payload));
      } catch (e) {
        console.error("failed to save edit episode draft", e);
      }
    }, 1000);
    return () => clearTimeout(timer);
  }, [id, episodeNumber, title, body, tags, status]);
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
          throw new Error(
            t(
              { ja: "エピソード情報の取得に失敗しました ({{status}})", en: "Failed to load episode info ({{status}})" },
              { status: res.status }
            )
          );
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
          if (data.status === "draft" || data.is_public === false) {
            setStatus("draft");
          } else {
            setStatus("public");
          }
        }


        // ★ 表紙・押絵も state に取り込む
        setCoverImageUrl(data.cover_image_url || "");
        setIllusts(Array.isArray(data.illusts) ? data.illusts : []);
      } catch (err) {
        console.error(err);
        setError(
          err.message || t({ ja: "エピソード情報の取得中にエラーが発生しました", en: "An error occurred while loading episode info." })
        );
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
      setError(t({ ja: "話数は数字で入力してください。", en: "Episode number must be a number." }));
      return;
    }
    if (!title.trim()) {
      setError(t({ ja: "タイトルは必須です。", en: "Title is required." }));
      return;
    }
    if (!body.trim()) {
      setError(t({ ja: "本文は必須です。", en: "Body is required." }));
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));
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
          status,
          is_public: status === "public",
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
        throw new Error(
          data.detail || t({ ja: "エピソードの更新に失敗しました", en: "Failed to update episode." })
        );
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
        navigate("/");
      }
    } catch (err) {
      console.error(err);
      setError(
        err.message || t({ ja: "エピソードの更新中にエラーが発生しました", en: "An error occurred while updating the episode." })
      );
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    if (novelId != null) {
      navigate(`/novels/${novelId}`);
    } else {
      navigate("/");
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
      alert(t({ ja: "表紙画像ファイルを選択してください", en: "Please select a cover image file." }));
      return;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      alert(t({ ja: "ログインが必要です。", en: "Login required." }));
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
        throw new Error(
          data.detail || t({ ja: "表紙のアップロードに失敗しました", en: "Failed to upload cover image." })
        );
      }

      const data = await res.json();
      setCoverImageUrl(data.cover_image_url || "");
      setCoverFile(null);
      alert(t({ ja: "表紙画像を更新しました", en: "Cover image updated." }));
    } catch (e) {
      console.error(e);
      alert(
        e.message || t({ ja: "表紙のアップロード中にエラーが発生しました", en: "An error occurred while uploading the cover image." })
      );
    } finally {
      setIsUploadingCover(false);
    }
  };

  const handleCoverDelete = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      alert(t({ ja: "ログインが必要です", en: "Login required." }));
      return;
    }
    if (!window.confirm(t({ ja: "本当に表紙を削除しますか？", en: "Delete the cover image?" }))) return;

    const res = await fetch(`${API_BASE}/api/episodes/${id}/cover-image`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      alert(t({ ja: "削除に失敗しました", en: "Failed to delete." }));
      return;
    }

    setCoverImageUrl("");
    alert(t({ ja: "表紙を削除しました", en: "Cover image deleted." }));
  };

  // =========================
  // 押絵アップロード系
  // =========================
  const handleIllustFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setIllustFile(e.target.files[0]);
      if (!(illustTag || "").trim()) {
        const usedTags = new Set(
          illusts
            .map((it) => (it.illust_tag || "").trim())
            .filter((tag) => tag.length > 0)
        );
        setIllustTag(generateIllustTag(usedTags));
      }
    }
  };

  const handleIllustUpload = async () => {
    if (!illustFile) {
      alert(t({ ja: "押絵画像ファイルを選択してください", en: "Please select an illustration file." }));
      return;
    }
    const normalizedTag = normalizeIllustTag(illustTag);
    if (!normalizedTag) {
      alert(
        t({
          ja: "illustタグは [[illust:12345678]] の形式で指定してください",
          en: "Illust tags must be in the form [[illust:12345678]].",
        })
      );
      return;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      alert(t({ ja: "ログインが必要です。", en: "Login required." }));
      navigate("/login");
      return;
    }

    const formData = new FormData();
    formData.append("file", illustFile);
    formData.append("caption", illustCaption || "");
    formData.append("illust_tag", normalizedTag);
    formData.append("meta_tags", illustMetaTags || "");

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
        throw new Error(
          data.detail || t({ ja: "押絵のアップロードに失敗しました", en: "Failed to upload illustration." })
        );
      }

      const newIllust = await res.json();
      setIllusts((prev) => [...prev, newIllust]);
      setIllustFile(null);
      setIllustCaption("");
      setIllustTag("");
      setIllustMetaTags("");
      alert(t({ ja: "押絵を追加しました", en: "Illustration added." }));
    } catch (e) {
      console.error(e);
      alert(
        e.message || t({ ja: "押絵のアップロード中にエラーが発生しました", en: "An error occurred while uploading the illustration." })
      );
    } finally {
      setIsUploadingIllust(false);
    }
  };

  const handleIllustDelete = async (illustId) => {
    const token = localStorage.getItem("token");
    if (!token) {
      alert(t({ ja: "ログインが必要です", en: "Login required." }));
      return;
    }
    if (!window.confirm(t({ ja: "押絵を削除しますか？", en: "Delete this illustration?" }))) return;

    const res = await fetch(
      `${API_BASE}/api/episodes/${id}/illusts/${illustId}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      }
    );

    if (!res.ok) {
      alert(t({ ja: "削除に失敗しました", en: "Failed to delete." }));
      return;
    }

    setIllusts((prev) => prev.filter((ill) => ill.id !== illustId));
    alert(t({ ja: "押絵を削除しました", en: "Illustration deleted." }));
  };

  if (loading) {
    return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;
  }

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        {novelId != null ? (
          <Link to={`/novels/${novelId}`}>
            {t({ ja: "← 小説詳細に戻る", en: "← Back to Novel" })}
          </Link>
        ) : (
          <button
            className="btn btn-border"
            type="button"
            onClick={() => navigate("/")}
          >
            {t({ ja: "← 戻る", en: "← Back" })}
          </button>
        )}
      </div>

      <h2>{t({ ja: "エピソードを編集", en: "Edit Episode" })}</h2>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
        <Link to={`/ai-novel?edit_episode_id=${id}`} className="btn btn-border">
          {t({ ja: "AI編集", en: "Edit with AI" })}
        </Link>
        <Link to={`/ai-novel?episode_id=${id}`} className="btn btn-border">
          {t({ ja: "AIで続きを生成", en: "Generate continuation with AI" })}
        </Link>
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "話数（例: 1, 2, 3）", en: "Episode number (e.g., 1, 2, 3)" })}
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
            {t({ ja: "タイトル", en: "Title" })}
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
            {t({ ja: "タグ (カンマ区切り)", en: "Tags (comma-separated)" })}
            <br />
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder={t({ ja: "例: バトル, 日常, 百合", en: "e.g., Battle, Slice of Life, Yuri" })}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "公開ステータス", en: "Visibility" })}
            <br />
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              style={{ width: "100%", padding: 4 }}
            >
              <option value="public">{t({ ja: "公開", en: "Public" })}</option>
              <option value="draft">{t({ ja: "下書き", en: "Draft" })}</option>
            </select>
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "本文", en: "Body" })}
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
            {saving ? t({ ja: "更新中...", en: "Updating..." }) : t({ ja: "更新する", en: "Update" })}
          </button>
          <button
            className="btn btn-border"
            type="button"
            onClick={handleCancel}
          >
            {t({ ja: "キャンセル", en: "Cancel" })}
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
        <h3 style={{ marginTop: 0 }}>{t({ ja: "表紙画像", en: "Cover image" })}</h3>

        {coverImageUrl ? (
          <div style={{ marginBottom: 12 }}>
            <img
              src={coverImageUrl}
              alt={t({ ja: "表紙画像", en: "Cover image" })}
              style={{ maxWidth: "100%", borderRadius: 8 }}
            />
            <div style={{ marginTop: 8 }}>
              <button
                type="button"
                className="btn btn-border"
                onClick={handleCoverDelete}
              >
                {t({ ja: "表紙を削除", en: "Delete cover" })}
              </button>
            </div>
          </div>
        ) : (
          <p style={{ color: "#777" }}>
            {t({ ja: "表紙画像はまだ設定されていません。", en: "No cover image set yet." })}
          </p>
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
            {isUploadingCover
              ? t({ ja: "アップロード中...", en: "Uploading..." })
              : t({ ja: "表紙としてアップロード", en: "Upload as cover" })}
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
        <h3 style={{ marginTop: 0 }}>{t({ ja: "押絵", en: "Illustrations" })}</h3>

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
                  alt={illust.caption || t({ ja: "押絵", en: "Illustration" })}
                  style={{ maxWidth: "100%", borderRadius: 4 }}
                />
                {illust.illust_tag && (
                  <div style={{ marginTop: 6, fontSize: 12, color: "#444" }}>
                    {formatIllustTag(illust.illust_tag)}
                  </div>
                )}
                {Array.isArray(illust.meta_tags) && illust.meta_tags.length > 0 && (
                  <div style={{ marginTop: 4, fontSize: 11, color: "#777" }}>
                    {illust.meta_tags.join(", ")}
                  </div>
                )}
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
                    {t({ ja: "押絵を削除", en: "Delete illustration" })}
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: "#777" }}>
            {t({ ja: "まだ押絵が登録されていません。", en: "No illustrations yet." })}
          </p>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <input
            type="file"
            accept="image/*"
            onChange={handleIllustFileChange}
          />
          <input
            type="text"
            placeholder={t({ ja: "キャプション（任意）", en: "Caption (optional)" })}
            value={illustCaption}
            onChange={(e) => setIllustCaption(e.target.value)}
          />
          <input
            type="text"
            placeholder={t({ ja: "必須タグ（例: [[illust:12345678]]）", en: "Required tag (e.g., [[illust:12345678]])" })}
            value={illustTag}
            onChange={(e) => setIllustTag(e.target.value)}
          />
          <input
            type="text"
            placeholder={t({ ja: "補助タグ（例: type:scene, mood:soft）", en: "Optional tags (e.g., type:scene, mood:soft)" })}
            value={illustMetaTags}
            onChange={(e) => setIllustMetaTags(e.target.value)}
          />
          <button
            type="button"
            className="btn btn-border"
            onClick={handleIllustUpload}
            disabled={isUploadingIllust || !illustFile}
          >
            {isUploadingIllust
              ? t({ ja: "アップロード中...", en: "Uploading..." })
              : t({ ja: "押絵を追加", en: "Add illustration" })}
          </button>
        </div>
      </div>
    </div>
  );
}
