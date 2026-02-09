import { useState, useEffect } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { mergeTagsInput, parseTagsInput } from "../lib/tagSuggest";

const API_BASE = import.meta.env.VITE_BACKEND_ORIGIN || "https://shosetsu-toukou-site.org";
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
  const location = useLocation();
  const { t } = useI18n();

  const [episodeNumber, setEpisodeNumber] = useState(1);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [tags, setTags] = useState("");          // タグ用 state
  const [status, setStatus] = useState("public"); // "public" / "draft"

  // ★ 表紙・押絵（NewEpisode 用）
  const [coverFile, setCoverFile] = useState(null);
  const [isUploadingCover, setIsUploadingCover] = useState(false);

  // 押絵は複数選択できるようにする
  const [illustItems, setIllustItems] = useState([]); // [{file, caption, illustTag, metaTags}]
  const [isUploadingIllust, setIsUploadingIllust] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tagCandidates, setTagCandidates] = useState([]);
  const [selectedTagCandidates, setSelectedTagCandidates] = useState(() => new Set());
  const [tagSuggestError, setTagSuggestError] = useState("");
  const [aiPrefillApplied, setAiPrefillApplied] = useState(false);

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
      if (draft.status) setStatus(draft.status);
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
        status,
        saved_at: new Date().toISOString(),
      };
      try {
        localStorage.setItem(draftKey, JSON.stringify(payload));
      } catch (e) {
        console.error("failed to save episode draft", e);
      }
    }, 1000);

    return () => clearTimeout(timer);
  }, [draftKey, episodeNumber, title, body, tags, status]);
  // === auto-save episode draft end ===

  useEffect(() => {
    if (aiPrefillApplied) return;
    const prefill = location?.state?.aiPrefill;
    if (!prefill || typeof prefill !== "object") return;

    if (prefill.episodeNumber !== undefined && prefill.episodeNumber !== null) {
      const num = Number(prefill.episodeNumber);
      if (!Number.isNaN(num) && num > 0) {
        setEpisodeNumber(num);
      }
    }
    if (typeof prefill.title === "string") {
      setTitle(prefill.title);
    }
    if (typeof prefill.body === "string") {
      setBody(prefill.body);
    }
    if (prefill.status === "draft" || prefill.status === "public") {
      setStatus(prefill.status);
    } else {
      setStatus("draft");
    }
    setAiPrefillApplied(true);
  }, [aiPrefillApplied, location?.state]);


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
        throw new Error(
          data.detail || t({ ja: "表紙のアップロードに失敗しました", en: "Failed to upload cover image." })
        );
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
          throw new Error(
            t({
              ja: "illustタグは [[illust:12345678]] の形式で指定してください",
              en: "Illust tags must be in the form [[illust:12345678]].",
            })
          );
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
          throw new Error(
            data.detail || t({ ja: "押絵のアップロードに失敗しました", en: "Failed to upload illustration." })
          );
        }
      }
    } finally {
      setIsUploadingIllust(false);
    }
  };

  const handleSuggestTags = async () => {
    setTagSuggestError("");
    if (!body.trim()) {
      setTagSuggestError(
        t({ ja: "本文がないため候補を生成できません。", en: "No body text available to generate tags." })
      );
      return;
    }
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));
      }
      const res = await fetch(`${API_BASE}/api/ai/tag_candidates`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ text: body.slice(0, 1000) }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "タグ候補の生成に失敗しました。", en: "Failed to generate tags." }));
      }
      const existing = parseTagsInput(tags);
      const existingSet = new Set(existing.map((tag) => tag.toLowerCase()));
      const candidates = (data?.candidates || []).filter(
        (tag) => tag && !existingSet.has(tag.toLowerCase())
      );
      if (!candidates.length) {
        setTagSuggestError(
          t({ ja: "追加できるタグ候補がありません。", en: "No tag candidates to add." })
        );
        setTagCandidates([]);
        setSelectedTagCandidates(new Set());
        return;
      }
      setTagCandidates(candidates);
      setSelectedTagCandidates(new Set(candidates));
    } catch (err) {
      console.error(err);
      setTagSuggestError(
        err.message || t({ ja: "タグ候補の生成に失敗しました。", en: "Failed to generate tags." })
      );
    }
  };

  const handleToggleCandidate = (candidate) => {
    setSelectedTagCandidates((prev) => {
      const next = new Set(prev);
      if (next.has(candidate)) {
        next.delete(candidate);
      } else {
        next.add(candidate);
      }
      return next;
    });
  };

  const handleAddSuggestedTags = () => {
    if (!selectedTagCandidates.size) return;
    const selected = tagCandidates.filter((tag) => selectedTagCandidates.has(tag));
    const nextInput = mergeTagsInput(tags, selected);
    setTags(nextInput);
    const remaining = tagCandidates.filter((tag) => !selectedTagCandidates.has(tag));
    setTagCandidates(remaining);
    setSelectedTagCandidates(new Set());
  };

  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!title.trim()) {
      setError(t({ ja: "タイトルは必須です。", en: "Title is required." }));
      return;
    }
    if (!body.trim()) {
      setError(t({ ja: "本文は必須です。", en: "Body is required." }));
      return;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      setError(t({ ja: "ログインが必要です。", en: "Login required." }));
      return;
    }

    const payload = {
      episode_number: Number(episodeNumber),
      title,
      body,
      status,
      is_public: status === "public",
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
            t(
              { ja: "エピソードの投稿に失敗しました (status={{status}})", en: "Failed to post episode (status={{status}})" },
              { status: res.status }
            )
        );
      }

      // episode_id を取得（返却形式ゆらぎ対応）
      const createdEpisodeId =
        (data && (data.id ?? data.episode_id)) ??
        null;

      if (!createdEpisodeId) {
        // ここまで成功してるので、少なくとも小説詳細には戻す
        console.warn(
          t({
            ja: "episode_id がレスポンスから取得できませんでした。アップロードはスキップします。",
            en: "episode_id was missing from the response. Skipping uploads.",
          })
        );
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
      setError(
        err.message || t({ ja: "投稿中にエラーが発生しました。", en: "An error occurred while posting." })
      );
    } finally {
      setLoading(false);
    }
  };




  return (
    <div>
      <h2>{t({ ja: "新しいエピソードを投稿", en: "Post New Episode" })}</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "話数", en: "Episode number" })}
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
          <h3 style={{ marginTop: 0 }}>{t({ ja: "表紙画像（任意）", en: "Cover image (optional)" })}</h3>
          <input type="file" accept="image/*" onChange={handleCoverFileChange} />
          {coverFile && (
            <div style={{ marginTop: 6, fontSize: 12, color: "#555" }}>
              {t({ ja: "選択中: {{name}}", en: "Selected: {{name}}" }, { name: coverFile.name })}
            </div>
          )}
          {isUploadingCover && (
            <div style={{ marginTop: 6, fontSize: 12, color: "#777" }}>
              {t({ ja: "表紙アップロード中...", en: "Uploading cover..." })}
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
          <h3 style={{ marginTop: 0 }}>
            {t({ ja: "押絵（任意・複数）", en: "Illustrations (optional, multiple)" })}
          </h3>

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
                    placeholder={t({ ja: "キャプション（任意）", en: "Caption (optional)" })}
                    value={it.caption || ""}
                    onChange={(e) => updateIllustCaption(idx, e.target.value)}
                    style={{ width: "100%", padding: 6 }}
                  />
                  <input
                    type="text"
                    placeholder={t({
                      ja: "必須タグ（例: [[illust:12345678]]）",
                      en: "Required tag (e.g., [[illust:12345678]])",
                    })}
                    value={it.illustTag || ""}
                    onChange={(e) => updateIllustTag(idx, e.target.value)}
                    style={{ width: "100%", padding: 6 }}
                  />
                  <input
                    type="text"
                    placeholder={t({
                      ja: "補助タグ（例: type:scene, mood:soft）",
                      en: "Optional tags (e.g., type:scene, mood:soft)",
                    })}
                    value={it.metaTags || ""}
                    onChange={(e) => updateIllustMetaTags(idx, e.target.value)}
                    style={{ width: "100%", padding: 6 }}
                  />
                  <button
                    type="button"
                    className="btn btn-border"
                    onClick={() => removeIllustItem(idx)}
                  >
                    {t({ ja: "この押絵を外す", en: "Remove illustration" })}
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ marginTop: 10, color: "#777", fontSize: 13 }}>
              {t({ ja: "まだ押絵は選択されていません。", en: "No illustrations selected yet." })}
            </p>
          )}

          {isUploadingIllust && (
            <div style={{ marginTop: 6, fontSize: 12, color: "#777" }}>
              {t({ ja: "押絵アップロード中...", en: "Uploading illustrations..." })}
            </div>
          )}
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
          <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
            <button
              type="button"
              className="btn btn-border"
              onClick={handleSuggestTags}
            >
              {t({ ja: "本文からタグ候補を抽出", en: "Suggest tags from text" })}
            </button>
            <span style={{ fontSize: "0.85rem", color: "#666" }}>
              {t({ ja: "候補を選んで追加できます", en: "Pick candidates to add" })}
            </span>
          </div>
          {tagSuggestError && (
            <div style={{ marginTop: 6, color: "red" }}>{tagSuggestError}</div>
          )}
          {tagCandidates.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {tagCandidates.map((candidate) => (
                  <label
                    key={candidate}
                    style={{
                      border: "1px solid var(--border)",
                      borderRadius: 999,
                      padding: "4px 10px",
                      background: "var(--surface-2)",
                      fontSize: "0.85rem",
                      display: "inline-flex",
                      gap: 6,
                      alignItems: "center",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedTagCandidates.has(candidate)}
                      onChange={() => handleToggleCandidate(candidate)}
                    />
                    {candidate}
                  </label>
                ))}
              </div>
              <div style={{ marginTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={handleAddSuggestedTags}
                  disabled={!selectedTagCandidates.size}
                >
                  {t({ ja: "選択したタグを追加", en: "Add selected tags" })}
                </button>
              </div>
            </div>
          )}
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

        {error && <p style={{ color: "red" }}>{error}</p>}

        <button className="btn btn-border" type="submit" disabled={loading}>
          {loading ? t({ ja: "投稿中...", en: "Posting..." }) : t({ ja: "投稿する", en: "Post" })}
        </button>
      </form>
    </div>
  );
}
