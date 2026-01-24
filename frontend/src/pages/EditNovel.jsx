import { useEffect, useState } from "react";
import { useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";

const API_BASE = import.meta.env.VITE_BACKEND_ORIGIN || "https://shosetsu-toukou-site.org";
const NOVEL_DRAFT_KEY_PREFIX = "draft_edit_novel"; // 作品ごとの編集下書き用プレフィックス

export default function EditNovel() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t } = useI18n();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [ageLimit, setAgeLimit] = useState("all");           // 全年齢 / R15 / R18
  const [isAIGenerated, setIsAIGenerated] = useState(false); // AI創作フラグ
  const [creativeType, setCreativeType] = useState("original"); // オリジナル / 二次創作
  const [status, setStatus] = useState("public");            // "public" / "draft"
  const [canEditFull, setCanEditFull] = useState(true);

  // ★ タグ（カンマ区切り入力）
  const [tagsInput, setTagsInput] = useState("");

  
  // draft を読んだかどうか
  const hasDraftRef = useRef(false);
const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // この作品の編集用ローカルストレージキー
  const novelDraftKey = `${NOVEL_DRAFT_KEY_PREFIX}_${id ?? "unknown"}`;

  // サーバから小説情報を取得
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      navigate("/login");
      return;
    }

    const fetchNovel = async () => {
      try {
        setLoading(true);
        setError("");

        const res = await fetch(`${API_BASE}/api/novels/${id}`, {
          headers: { Authorization: "Bearer " + token },
        });
        if (!res.ok) {
          throw new Error(
            t(
              { ja: "小説情報の取得に失敗しました ({{status}})", en: "Failed to load novel info ({{status}})" },
              { status: res.status }
            )
          );
        }

        const data = await res.json();
        const canEdit = data?.can_edit_full !== false;
        setCanEditFull(canEdit);
        setTitle(data.title || "");
        setDescription(data.description || "");
        setAgeLimit(data.age_limit || "all");
        setIsAIGenerated(!!data.is_ai_generated);
        setCreativeType(data.creative_type || "original");

        // ★ tags（配列）→ "A, B" にしてセット
        if (Array.isArray(data.tags)) {
          setTagsInput(data.tags.map((t) => t.name).join(", "));
        } else {
          setTagsInput("");
        }

        // status が "draft" なら下書き。
        // それ以外でも is_public === false なら下書き扱いにする（データ不整合の保険）
        if (data.status === "draft" || data.is_public === false) {
          setStatus("draft");
        } else {
          setStatus("public");
        }
      } catch (err) {
        console.error(err);
        setError(
          err.message || t({ ja: "小説情報の取得中にエラーが発生しました", en: "An error occurred while loading novel info." })
        );
      } finally {
        setLoading(false);
      }
    };

    fetchNovel();
  }, [id, navigate]);

  // マウント時に編集下書きを読み込む（あればサーバ値の上から上書き）
  useEffect(() => {
    try {
      const raw = localStorage.getItem(novelDraftKey);
      if (!raw) return;
      const draft = JSON.parse(raw);

      
      hasDraftRef.current = true;
if (draft.title) setTitle(draft.title);
      if (draft.description) setDescription(draft.description);
      if (draft.ageLimit) setAgeLimit(draft.ageLimit);
      if (typeof draft.isAIGenerated === "boolean") setIsAIGenerated(draft.isAIGenerated);
      if (draft.status) setStatus(draft.status);
      if (draft.creativeType) setCreativeType(draft.creativeType);

      // ★ draft の tagsInput
      if (typeof draft.tagsInput === "string") setTagsInput(draft.tagsInput);
    } catch (e) {
      console.error("failed to load novel edit draft", e);
    }
  }, [novelDraftKey]);

  // 入力が変わるたび 1 秒後に自動保存
  useEffect(() => {
    const timer = setTimeout(() => {
      const payload = {
        title,
        description,
        ageLimit,
        status,
        isAIGenerated,
        creativeType,
        tagsInput, // ★ 追加
        saved_at: new Date().toISOString(),
      };
      try {
        localStorage.setItem(novelDraftKey, JSON.stringify(payload));
      } catch (e) {
        console.error("failed to save novel edit draft", e);
      }
    }, 1000);

    return () => clearTimeout(timer);
  }, [novelDraftKey, title, description, ageLimit, status, isAIGenerated, tagsInput]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (canEditFull) {
      if (!title.trim()) {
        setError(t({ ja: "タイトルは必須です。", en: "Title is required." }));
        return;
      }
    }

    setSaving(true);
    try {
      const token = localStorage.getItem("token");
      if (!token) throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));

      // ★ "A, B" → ["A","B"]
      const tagNames = (tagsInput || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      const res = await fetch(`${API_BASE}/api/novels/${id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        body: JSON.stringify(
          canEditFull
            ? {
                title,
                description,
                age_limit: ageLimit,
                is_ai_generated: isAIGenerated,
                creative_type: creativeType,
                status,
                is_public: status === "public",

                // ★ ここが本命
                tag_names: tagNames,
              }
            : {
                tag_names: tagNames,
              }
        ),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data.detail || t({ ja: "小説の更新に失敗しました", en: "Failed to update novel." })
        );
      }

      // 更新に成功したら、この小説の編集下書きを削除
      try {
        localStorage.removeItem(novelDraftKey);
      } catch (e) {
        console.error("failed to clear novel edit draft", e);
      }

      navigate(`/novels/${id}`);
    } catch (err) {
      console.error(err);
      setError(
        err.message || t({ ja: "小説の更新中にエラーが発生しました", en: "An error occurred while updating the novel." })
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to={`/novels/${id}`}>
          {t({ ja: "← 小説詳細に戻る", en: "← Back to Novel" })}
        </Link>
      </div>

      <h2>{t({ ja: "小説を編集", en: "Edit Novel" })}</h2>

      <form onSubmit={handleSubmit}>
        {!canEditFull && (
          <p style={{ marginTop: 0, marginBottom: 8, color: "#666" }}>
            {t({ ja: "この作品はタグのみ編集できます。", en: "Only tags can be edited for this novel." })}
          </p>
        )}

        {/* ★ タグ編集 */}
        <div style={{ marginBottom: 8 }}>
          <label>
            {t({ ja: "タグ（カンマ区切り）", en: "Tags (comma-separated)" })}
            <br />
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder={t({ ja: "例: ファンタジー, バトル, 百合", en: "e.g., Fantasy, Battle, Yuri" })}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
          <div style={{ fontSize: "0.85rem", color: "#666", marginTop: 4 }}>
            {t({ ja: "※ カンマ区切りで複数指定できます", en: "Tip: separate multiple tags with commas." })}
          </div>
        </div>

        {canEditFull && (
          <>
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
                {t({ ja: "説明（あらすじ）", en: "Description (summary)" })}
                <br />
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={6}
                  style={{ width: "100%", padding: 4 }}
                />
              </label>
            </div>

            <div style={{ marginBottom: 8 }}>
              <label>
                {t({ ja: "作品種別", en: "Work type" })}
                <br />
                <div style={{ display: "flex", gap: 12, marginTop: 4 }}>
                  <label>
                    <input
                      type="radio"
                      name="creative_type"
                      value="original"
                      checked={creativeType === "original"}
                      onChange={(e) => setCreativeType(e.target.value)}
                      style={{ marginRight: 4 }}
                    />
                    {t({ ja: "オリジナル", en: "Original" })}
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="creative_type"
                      value="fanfic"
                      checked={creativeType === "fanfic"}
                      onChange={(e) => setCreativeType(e.target.value)}
                      style={{ marginRight: 4 }}
                    />
                    {t({ ja: "二次創作", en: "Fanfiction" })}
                  </label>
                </div>
              </label>
            </div>

            <div style={{ marginBottom: 8 }}>
              <label>
                {t({ ja: "年齢区分", en: "Age rating" })}
                <br />
                <select
                  value={ageLimit}
                  onChange={(e) => setAgeLimit(e.target.value)}
                  style={{ width: "100%", padding: 4 }}
                >
                  <option value="all">{t({ ja: "全年齢", en: "All ages" })}</option>
                  <option value="r15">R15</option>
                  <option value="r18">R18</option>
                </select>
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
                <input
                  type="checkbox"
                  checked={isAIGenerated}
                  onChange={(e) => setIsAIGenerated(e.target.checked)}
                  style={{ marginRight: 4 }}
                />
                {t({ ja: "AI創作", en: "AI-generated" })}
              </label>
            </div>
          </>
        )}

        {error && <p style={{ color: "red", marginTop: 4, marginBottom: 8 }}>{error}</p>}

        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-border" type="submit" disabled={saving}>
            {saving ? t({ ja: "更新中...", en: "Updating..." }) : t({ ja: "更新する", en: "Update" })}
          </button>
          <button
            className="btn btn-border"
            type="button"
            onClick={() => navigate(`/novels/${id}`)}
          >
            {t({ ja: "キャンセル", en: "Cancel" })}
          </button>
        </div>
      </form>
    </div>
  );
}
