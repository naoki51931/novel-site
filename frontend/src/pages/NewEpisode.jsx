import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

const API_BASE = "";
const EP_DRAFT_KEY_PREFIX = "draft_new_episode"; // 作品ごとの下書き用プレフィックス
const ILLUST_TAG_PREFIX = "illust:";
const ILLUST_TAG_RE = /^illust:(\d{8})$/;
const ILLUST_TAG_BRACKET_RE = /^\[\[illust:(\d{8})\]\]$/;

const normalizeIllustTag = (rawTag) => {
  const trimmed = (rawTag || "").trim();
  if (!trimmed) return null;
  let match = trimmed.match(ILLUST_TAG_RE);
  if (match) return `${ILLUST_TAG_PREFIX}${match[1]}`;
  match = trimmed.match(ILLUST_TAG_BRACKET_RE);
  if (match) return `${ILLUST_TAG_PREFIX}${match[1]}`;
  return null;
};

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

export default function NewEpisode() {
  const { id } = useParams(); // novel_id
  const navigate = useNavigate();

  const [episodeNumber, setEpisodeNumber] = useState(1);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [tags, setTags] = useState("");          // タグ用 state

  // ★ 表紙・押絵（NewEpisode 用）
  const [coverFile, setCoverFile] = useState(null);
  const [isUploadingCover, setIsUploadingCover] = useState(false);

  // 押絵は複数選択できるようにする
  const [illustItems, setIllustItems] = useState([]); // [{file, caption, illustTag, metaTags}]
  const [isUploadingIllust, setIsUploadingIllust] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // この作品用のローカルストレージキー
  const draftKey = `${EP_DRAFT_KEY_PREFIX}_${id ?? "unknown"}`;

  // === auto-save episode draft start ===
  // マウント時に下書きを読み込む
  useEffect(() => {
    try {
      const raw = localStorage.getItem(draftKey);
      if (!raw) return;
      const draft = JSON.parse(raw);
      if (draft.episodeNumber !== undefined && draft.episodeNumber !== null) {
        setEpisodeNumber(draft.episodeNumber);
      }
      if (draft.title) setTitle(draft.title);
      if (draft.body) setBody(draft.body);
      if (typeof draft.tags === "string") setTags(draft.tags);
    } catch (e) {
      console.error("failed to load episode draft", e);
    }
  }, [draftKey]);

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
  }, [draftKey, episodeNumber, title, body, tags]);
  // === auto-save episode draft end ===


  // =========================
  // ★ 表紙・押絵（NewEpisode）
  // =========================
  const handleCoverFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setCoverFile(e.target.files[0]);
    }
  };

  const handleIllustFilesChange = (e) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    if (!files.length) return;
    // 追加形式（既存に追記）
    setIllustItems((prev) => {
      const usedTags = new Set(
        prev
          .map((it) => (it.illustTag || "").trim())
          .filter((tag) => tag.length > 0)
      );
      const next = files.map((f) => {
        const illustTag = generateIllustTag(usedTags);
        usedTags.add(illustTag);
        return { file: f, caption: "", illustTag, metaTags: "" };
      });
      return [...prev, ...next];
    });
    // 同じファイルをもう一度選べるよう input をリセット
    e.target.value = "";
  };

  const updateIllustCaption = (index, caption) => {
    setIllustItems((prev) =>
      prev.map((it, i) => (i === index ? { ...it, caption } : it))
    );
  };

  const updateIllustTag = (index, illustTag) => {
    setIllustItems((prev) =>
      prev.map((it, i) => (i === index ? { ...it, illustTag } : it))
    );
  };

  const updateIllustMetaTags = (index, metaTags) => {
    setIllustItems((prev) =>
      prev.map((it, i) => (i === index ? { ...it, metaTags } : it))
    );
  };

  const removeIllustItem = (index) => {
    setIllustItems((prev) => prev.filter((_, i) => i !== index));
  };

  const uploadCover = async (episodeId, token) => {
    if (!coverFile) return;
    const formData = new FormData();
    formData.append("file", coverFile);

    setIsUploadingCover(true);
    try {
      const res = await fetch(`${API_BASE}/api/episodes/${episodeId}/cover-image`, {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
        body: formData,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "表紙のアップロードに失敗しました");
      }
    } finally {
      setIsUploadingCover(false);
    }
  };

  const uploadIllusts = async (episodeId, token) => {
    if (!illustItems.length) return;

    setIsUploadingIllust(true);
    try {
      for (const item of illustItems) {
        const normalizedTag = normalizeIllustTag(item.illustTag);
        if (!normalizedTag) {
          throw new Error("illustタグは [[illust:12345678]] の形式で指定してください");
        }
        const formData = new FormData();
        formData.append("file", item.file);
        formData.append("caption", item.caption || "");
        formData.append("illust_tag", normalizedTag);
        formData.append("meta_tags", item.metaTags || "");

        const res = await fetch(`${API_BASE}/api/episodes/${episodeId}/illusts`, {
          method: "POST",
          headers: { Authorization: "Bearer " + token },
          body: formData,
        });

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || "押絵のアップロードに失敗しました");
        }
      }
    } finally {
      setIsUploadingIllust(false);
    }
  };

  
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

    const token = localStorage.getItem("token");
    if (!token) {
      setError("ログインが必要です。");
      return;
    }

    const payload = {
      episode_number: Number(episodeNumber),
      title,
      body,
      tag_names: tags
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s.length > 0),
    };

    console.log("📥 POST /api/novels/:id/episodes payload:", payload);

    setLoading(true);
    try {
      // 1) エピソード作成
      const res = await fetch(`${API_BASE}/api/novels/${id}/episodes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
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

      // episode_id を取得（返却形式ゆらぎ対応）
      const createdEpisodeId =
        (data && (data.id ?? data.episode_id)) ??
        null;

      if (!createdEpisodeId) {
        // ここまで成功してるので、少なくとも小説詳細には戻す
        console.warn("episode_id がレスポンスから取得できませんでした。アップロードはスキップします。");
        localStorage.removeItem(draftKey);
        navigate(`/novels/${id}`);
        return;
      }

      // 2) 表紙アップロード（任意）
      if (coverFile) {
        await uploadCover(createdEpisodeId, token);
      }

      // 3) 押絵アップロード（任意・複数）
      if (illustItems.length) {
        await uploadIllusts(createdEpisodeId, token);
      }

      // 成功したらこの小説の下書きを消して小説詳細へ戻る
      localStorage.removeItem(draftKey);
      navigate(`/novels/${id}`);
    } catch (err) {
      console.error("❌ NewEpisode error:", err);
      setError(err.message || "投稿中にエラーが発生しました。");
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

        {/* タグ入力欄 */}


        {/* =========================
            ★ 表紙・押絵（任意）
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
          <h3 style={{ marginTop: 0 }}>表紙画像（任意）</h3>
          <input type="file" accept="image/*" onChange={handleCoverFileChange} />
          {coverFile && (
            <div style={{ marginTop: 6, fontSize: 12, color: "#555" }}>
              選択中: {coverFile.name}
            </div>
          )}
          {isUploadingCover && (
            <div style={{ marginTop: 6, fontSize: 12, color: "#777" }}>
              表紙アップロード中...
            </div>
          )}
        </div>

        <div
          style={{
            marginTop: 16,
            marginBottom: 16,
            padding: 12,
            borderRadius: 8,
            border: "1px solid #ddd",
          }}
        >
          <h3 style={{ marginTop: 0 }}>押絵（任意・複数）</h3>

          <input
            type="file"
            accept="image/*"
            multiple
            onChange={handleIllustFilesChange}
          />

          {illustItems.length > 0 ? (
            <div style={{ marginTop: 12, display: "grid", gap: 10 }}>
              {illustItems.map((it, idx) => (
                <div
                  key={idx}
                  style={{
                    border: "1px solid #eee",
                    borderRadius: 8,
                    padding: 10,
                    display: "grid",
                    gap: 6,
                  }}
                >
                  <div style={{ fontSize: 12, color: "#555" }}>
                    {it.file?.name}
                  </div>
                  <input
                    type="text"
                    placeholder="キャプション（任意）"
                    value={it.caption || ""}
                    onChange={(e) => updateIllustCaption(idx, e.target.value)}
                    style={{ width: "100%", padding: 6 }}
                  />
                  <input
                    type="text"
                    placeholder="必須タグ（例: [[illust:12345678]]）"
                    value={it.illustTag || ""}
                    onChange={(e) => updateIllustTag(idx, e.target.value)}
                    style={{ width: "100%", padding: 6 }}
                  />
                  <input
                    type="text"
                    placeholder="補助タグ（例: type:scene, mood:soft）"
                    value={it.metaTags || ""}
                    onChange={(e) => updateIllustMetaTags(idx, e.target.value)}
                    style={{ width: "100%", padding: 6 }}
                  />
                  <button
                    type="button"
                    className="btn btn-border"
                    onClick={() => removeIllustItem(idx)}
                  >
                    この押絵を外す
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ marginTop: 10, color: "#777", fontSize: 13 }}>
              まだ押絵は選択されていません。
            </p>
          )}

          {isUploadingIllust && (
            <div style={{ marginTop: 6, fontSize: 12, color: "#777" }}>
              押絵アップロード中...
            </div>
          )}
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

        {error && <p style={{ color: "red" }}>{error}</p>}

        <button className="btn btn-border" type="submit" disabled={loading}>
          {loading ? "投稿中..." : "投稿する"}
        </button>
      </form>
    </div>
  );
}
