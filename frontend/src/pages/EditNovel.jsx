import { useEffect, useState } from "react";
import { useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

const API_BASE = "";
const NOVEL_DRAFT_KEY_PREFIX = "draft_edit_novel"; // 作品ごとの編集下書き用プレフィックス

export default function EditNovel() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [ageLimit, setAgeLimit] = useState("all");           // 全年齢 / R15 / R18
  const [isAIGenerated, setIsAIGenerated] = useState(false); // AI創作フラグ
  const [creativeType, setCreativeType] = useState("original"); // オリジナル / 二次創作
  const [status, setStatus] = useState("public");            // "public" / "draft"

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
          throw new Error(`小説情報の取得に失敗しました (${res.status})`);
        }

        const data = await res.json();
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
        setError(err.message || "小説情報の取得中にエラーが発生しました");
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

    if (!title.trim()) {
      setError("タイトルは必須です。");
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem("token");
      if (!token) throw new Error("ログインが必要です。");

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
        body: JSON.stringify({
          title,
          description,
          age_limit: ageLimit,
          is_ai_generated: isAIGenerated,
          creative_type: creativeType,
          status,
          is_public: status === "public",

          // ★ ここが本命
          tag_names: tagNames,
        }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "小説の更新に失敗しました");

      // 更新に成功したら、この小説の編集下書きを削除
      try {
        localStorage.removeItem(novelDraftKey);
      } catch (e) {
        console.error("failed to clear novel edit draft", e);
      }

      navigate(`/novels/${id}`);
    } catch (err) {
      console.error(err);
      setError(err.message || "小説の更新中にエラーが発生しました");
    } finally {
      setSaving(false);
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
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            説明（あらすじ）
            <br />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>

        {/* ★ タグ編集 */}
        <div style={{ marginBottom: 8 }}>
          <label>
            タグ（カンマ区切り）
            <br />
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="例: ファンタジー, バトル, 百合"
              style={{ width: "100%", padding: 4 }}
            />
          </label>
          <div style={{ fontSize: "0.85rem", color: "#666", marginTop: 4 }}>
            ※ カンマ区切りで複数指定できます
          </div>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            作品種別
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
                オリジナル
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
                二次創作
              </label>
            </div>
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            年齢区分
            <br />
            <select
              value={ageLimit}
              onChange={(e) => setAgeLimit(e.target.value)}
              style={{ width: "100%", padding: 4 }}
            >
              <option value="all">全年齢</option>
              <option value="r15">R15</option>
              <option value="r18">R18</option>
            </select>
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            公開ステータス
            <br />
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              style={{ width: "100%", padding: 4 }}
            >
              <option value="public">公開</option>
              <option value="draft">下書き</option>
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
            AI創作
          </label>
        </div>

        {error && <p style={{ color: "red", marginTop: 4, marginBottom: 8 }}>{error}</p>}

        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-border" type="submit" disabled={saving}>
            {saving ? "更新中..." : "更新する"}
          </button>
          <button
            className="btn btn-border"
            type="button"
            onClick={() => navigate(`/novels/${id}`)}
          >
            キャンセル
          </button>
        </div>
      </form>
    </div>
  );
}
