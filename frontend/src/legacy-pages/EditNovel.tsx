import { useEffect, useState, useRef, type ChangeEvent, type FormEvent } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { mergeTagsInput, parseTagsInput } from "../lib/tagSuggest";
import { getApiBase } from "../lib/apiBase";
import { formatDateTimeInUserTimeZone } from "../lib/timezone";

const API_BASE = getApiBase();
const NOVEL_DRAFT_KEY_PREFIX = "draft_edit_novel"; // 作品ごとの編集下書き用プレフィックス

type NovelStatus = "public" | "draft";

type CoverForm = {
  genre: string;
  mood: string;
  color_theme: string;
  character_count: number;
  extra_prompt: string;
};

type NovelTag = {
  name?: string | null;
};

type NovelResponse = {
  title?: string | null;
  description?: string | null;
  age_limit?: string | null;
  is_ai_generated?: boolean | null;
  creative_type?: string | null;
  fanfic_source_title?: string | null;
  fanfic_characters?: string | null;
  fanfic_coupling?: string | null;
  fanfic_notes?: string | null;
  series_name?: string | null;
  series_order?: string | number | null;
  tags?: NovelTag[] | null;
  status?: string | null;
  is_public?: boolean | null;
  cover_image_url?: string | null;
  can_edit_full?: boolean | null;
};

type EditNovelDraft = {
  title?: string;
  description?: string;
  ageLimit?: string;
  status?: NovelStatus;
  isAIGenerated?: boolean;
  creativeType?: string;
  fanficSourceTitle?: string;
  fanficCharacters?: string;
  characterNamesInput?: string;
  fanficCoupling?: string;
  fanficNotes?: string;
  seriesName?: string;
  seriesOrder?: string;
  tagsInput?: string;
};

type CoverHistoryItem = {
  id?: number | string | null;
  image_url?: string | null;
  image_path?: string | null;
  created_at?: string | null;
  status?: string | null;
  cover_image_path?: string | null;
};

export default function EditNovel() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t, lang } = useI18n();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [characterNamesInput, setCharacterNamesInput] = useState("");
  const [ageLimit, setAgeLimit] = useState("all");           // 全年齢 / R15 / R18
  const [isAIGenerated, setIsAIGenerated] = useState(false); // AI創作フラグ
  const [creativeType, setCreativeType] = useState("original"); // オリジナル / 二次創作
  const [fanficSourceTitle, setFanficSourceTitle] = useState("");
  const [fanficCharacters, setFanficCharacters] = useState("");
  const [fanficCoupling, setFanficCoupling] = useState("");
  const [fanficNotes, setFanficNotes] = useState("");
  const [seriesName, setSeriesName] = useState("");
  const [seriesOrder, setSeriesOrder] = useState("");
  const [status, setStatus] = useState<NovelStatus>("public");            // "public" / "draft"
  const [novelCoverImageUrl, setNovelCoverImageUrl] = useState("");
  const [isPremium, setIsPremium] = useState(false);
  const [canEditFull, setCanEditFull] = useState(true);
  const [autoSummaryLoading, setAutoSummaryLoading] = useState(false);
  const [autoSummaryError, setAutoSummaryError] = useState("");
  const [autoSummaryCandidates, setAutoSummaryCandidates] = useState<string[]>([]);
  const [selectedAutoSummary, setSelectedAutoSummary] = useState("");
  const [titleSuggestLoading, setTitleSuggestLoading] = useState(false);
  const [titleSuggestError, setTitleSuggestError] = useState("");
  const [titleCandidates, setTitleCandidates] = useState<string[]>([]);
  const [tagSuggestLoading, setTagSuggestLoading] = useState(false);
  const [tagSuggestError, setTagSuggestError] = useState("");
  const [characterSuggestLoading, setCharacterSuggestLoading] = useState(false);
  const [characterSuggestError, setCharacterSuggestError] = useState("");
  const [tagCandidates, setTagCandidates] = useState<string[]>([]);
  const [selectedTagCandidates, setSelectedTagCandidates] = useState<Set<string>>(() => new Set());
  const [showCoverModal, setShowCoverModal] = useState(false);
  const [coverGenerating, setCoverGenerating] = useState(false);
  const [coverSaving, setCoverSaving] = useState(false);
  const [coverRemoving, setCoverRemoving] = useState(false);
  const [coverError, setCoverError] = useState("");
  const [localCoverFile, setLocalCoverFile] = useState<File | null>(null);
  const [localCoverUploading, setLocalCoverUploading] = useState(false);
  const [localCoverError, setLocalCoverError] = useState("");
  const [fanficAutoFillLoading, setFanficAutoFillLoading] = useState(false);
  const [fanficAutoFillError, setFanficAutoFillError] = useState("");
  const [fanficSourceTitleCandidates, setFanficSourceTitleCandidates] = useState<string[]>([]);
  const [coverHistory, setCoverHistory] = useState<CoverHistoryItem[]>([]);
  const [coverForm, setCoverForm] = useState<CoverForm>({
    genre: "",
    mood: "",
    color_theme: "",
    character_count: 1,
    extra_prompt: "",
  });

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
        // 下書きを読み込んでいる場合は、遅延レスポンスで入力を上書きしない
        if (!hasDraftRef.current) {
          setTitle(data.title || "");
          setDescription(data.description || "");
          setAgeLimit(data.age_limit || "all");
          setIsAIGenerated(!!data.is_ai_generated);
          setCreativeType(data.creative_type || "original");
          setFanficSourceTitle(data.fanfic_source_title || "");
          setFanficCharacters(data.fanfic_characters || "");
          setCharacterNamesInput(data.fanfic_characters || "");
          setFanficCoupling(data.fanfic_coupling || "");
          setFanficNotes(data.fanfic_notes || "");
          setSeriesName(data.series_name || "");
          setSeriesOrder(
            data.series_order === null || typeof data.series_order === "undefined"
              ? ""
              : String(data.series_order)
          );

          // ★ tags（配列）→ "A, B" にしてセット
          if (Array.isArray(data.tags)) {
            setTagsInput(data.tags.map((t: NovelTag) => t.name).join(", "));
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
          setNovelCoverImageUrl(data.cover_image_url || "");
        }
      } catch (err) {
        console.error(err);
        setError(
          getErrorMessage(
            err,
            t({ ja: "小説情報の取得中にエラーが発生しました", en: "An error occurred while loading novel info." })
          )
        );
      } finally {
        setLoading(false);
      }
    };

    fetchNovel();
  }, [id, navigate]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    fetch(`${API_BASE}/api/users/me`, {
      headers: { Authorization: "Bearer " + token },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setIsPremium(!!data?.is_premium))
      .catch(() => {});
  }, []);

  // マウント時に編集下書きを読み込む（あればサーバ値の上から上書き）
  useEffect(() => {
    try {
      const raw = localStorage.getItem(novelDraftKey);
      if (!raw) return;
      const draft = JSON.parse(raw) as EditNovelDraft;

      hasDraftRef.current = true;
      if (draft.title) setTitle(draft.title);
      if (draft.description) setDescription(draft.description);
      if (draft.ageLimit) setAgeLimit(draft.ageLimit);
      if (typeof draft.isAIGenerated === "boolean") setIsAIGenerated(draft.isAIGenerated);
      if (draft.status) setStatus(draft.status);
      if (draft.creativeType) setCreativeType(draft.creativeType);
      if (typeof draft.fanficSourceTitle === "string") setFanficSourceTitle(draft.fanficSourceTitle);
      if (typeof draft.fanficCharacters === "string") setFanficCharacters(draft.fanficCharacters);
      if (typeof draft.characterNamesInput === "string") setCharacterNamesInput(draft.characterNamesInput);
      if (typeof draft.fanficCoupling === "string") setFanficCoupling(draft.fanficCoupling);
      if (typeof draft.fanficNotes === "string") setFanficNotes(draft.fanficNotes);
      if (typeof draft.seriesName === "string") setSeriesName(draft.seriesName);
      if (typeof draft.seriesOrder === "string") setSeriesOrder(draft.seriesOrder);

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
        fanficSourceTitle,
        fanficCharacters,
        characterNamesInput,
        fanficCoupling,
        fanficNotes,
        seriesName,
        seriesOrder,
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
  }, [
    novelDraftKey,
    title,
    description,
    ageLimit,
    status,
    isAIGenerated,
    creativeType,
    fanficSourceTitle,
    fanficCharacters,
    characterNamesInput,
    fanficCoupling,
    fanficNotes,
    seriesName,
    seriesOrder,
    tagsInput,
  ]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
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
                fanfic_source_title: creativeType === "fanfic" ? fanficSourceTitle : "",
                fanfic_characters:
                  creativeType === "fanfic"
                    ? (fanficCharacters || "").trim() || (characterNamesInput || "").trim()
                    : "",
                fanfic_coupling: creativeType === "fanfic" ? fanficCoupling : "",
                fanfic_notes: creativeType === "fanfic" ? fanficNotes : "",
                series_name: seriesName,
                series_order: seriesOrder === "" ? null : Number(seriesOrder),
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
        getErrorMessage(
          err,
          t({ ja: "小説の更新中にエラーが発生しました", en: "An error occurred while updating the novel." })
        )
      );
    } finally {
      setSaving(false);
    }
  };

  const loadCoverHistory = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    const res = await fetch(`${API_BASE}/api/covers/history?novel_id=${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json().catch(() => []);
    if (!res.ok) {
      throw new Error(data.detail || t({ ja: "表紙履歴の取得に失敗しました", en: "Failed to load cover history." }));
    }
    setCoverHistory(Array.isArray(data) ? data : []);
  };

  const openCoverModal = async () => {
    if (!isPremium) {
      setCoverError(t({ ja: "AI表紙生成はプレミアム会員限定です。", en: "AI cover generation is premium-only." }));
      return;
    }
    setCoverError("");
    setShowCoverModal(true);
    try {
      await loadCoverHistory();
    } catch (e) {
      setCoverError(getErrorMessage(e, t({ ja: "表紙履歴の取得に失敗しました", en: "Failed to load cover history." })));
    }
  };

  const handleGenerateCover = async () => {
    if (!isPremium) {
      setCoverError(t({ ja: "AI表紙生成はプレミアム会員限定です。", en: "AI cover generation is premium-only." }));
      return;
    }
    const token = localStorage.getItem("token");
    if (!token) {
      navigate("/login");
      return;
    }
    try {
      setCoverError("");
      setCoverGenerating(true);
      const payload = {
        novel_id: Number(id),
        title: title || "",
        catch_copy: (description || "").slice(0, 200),
        genre: coverForm.genre,
        mood: coverForm.mood,
        color_theme: coverForm.color_theme,
        character_count: Number(coverForm.character_count || 0),
        extra_prompt: coverForm.extra_prompt,
      };
      const res = await fetch(`${API_BASE}/api/covers/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "表紙生成に失敗しました", en: "Failed to generate cover." }));
      }
      await loadCoverHistory();
    } catch (e) {
      setCoverError(getErrorMessage(e, t({ ja: "表紙生成に失敗しました", en: "Failed to generate cover." })));
    } finally {
      setCoverGenerating(false);
    }
  };

  const handleAdoptCover = async (imagePath: string) => {
    if (!isPremium) {
      setCoverError(t({ ja: "AI表紙生成はプレミアム会員限定です。", en: "AI cover generation is premium-only." }));
      return;
    }
    const token = localStorage.getItem("token");
    if (!token) {
      navigate("/login");
      return;
    }
    try {
      setCoverSaving(true);
      setCoverError("");
      const res = await fetch(`${API_BASE}/api/novels/${id}/cover`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ image_path: imagePath }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "表紙設定に失敗しました", en: "Failed to set novel cover." }));
      }
      setNovelCoverImageUrl(data.cover_image_path || imagePath);
      setShowCoverModal(false);
    } catch (e) {
      setCoverError(getErrorMessage(e, t({ ja: "表紙設定に失敗しました", en: "Failed to set novel cover." })));
    } finally {
      setCoverSaving(false);
    }
  };

  const handleRemoveNovelCover = async () => {
    const confirmed = window.confirm(t({ ja: "現在の表紙を削除しますか？", en: "Remove current cover?" }));
    if (!confirmed) return;
    const token = localStorage.getItem("token");
    if (!token) {
      navigate("/login");
      return;
    }
    try {
      setCoverError("");
      setCoverRemoving(true);
      const res = await fetch(`${API_BASE}/api/novels/${id}/cover`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "表紙削除に失敗しました", en: "Failed to remove cover." }));
      }
      setNovelCoverImageUrl("");
    } catch (e) {
      setCoverError(getErrorMessage(e, t({ ja: "表紙削除に失敗しました", en: "Failed to remove cover." })));
    } finally {
      setCoverRemoving(false);
    }
  };

  const resolveCoverUrl = (raw: string | null | undefined) => {
    const path = String(raw || "").trim();
    if (!path) return "";
    if (path.startsWith("http://") || path.startsWith("https://")) return path;
    return `${API_BASE}${path}`;
  };

  const handleLocalCoverFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setLocalCoverFile(file);
    setLocalCoverError("");
  };

  const handleUploadLocalCover = async () => {
    if (!localCoverFile) {
      setLocalCoverError(
        t({ ja: "表紙画像ファイルを選択してください。", en: "Please select a cover image file." })
      );
      return;
    }
    const token = localStorage.getItem("token");
    if (!token) {
      navigate("/login");
      return;
    }
    try {
      setLocalCoverUploading(true);
      setLocalCoverError("");
      const formData = new FormData();
      formData.append("file", localCoverFile);
      const res = await fetch(`${API_BASE}/api/novels/${id}/cover-image`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data.detail ||
            t({ ja: "表紙画像のアップロードに失敗しました。", en: "Failed to upload cover image." })
        );
      }
      setNovelCoverImageUrl(data.cover_image_path || "");
      setLocalCoverFile(null);
    } catch (e) {
      setLocalCoverError(
        getErrorMessage(
          e,
          t({ ja: "表紙画像のアップロード中にエラーが発生しました。", en: "Failed while uploading cover image." })
        )
      );
    } finally {
      setLocalCoverUploading(false);
    }
  };

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  const handleAutoSummary = async () => {
    if (!id) return;
    try {
      setAutoSummaryLoading(true);
      setAutoSummaryError("");
      setAutoSummaryCandidates([]);
      setSelectedAutoSummary("");
      const token = localStorage.getItem("token");
      if (!token) throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));
      const res = await fetch(`${API_BASE}/api/novels/${id}/summary_candidates`, {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
      });
      if (!res.ok) {
        throw new Error(
          t({ ja: "説明文候補の生成に失敗しました", en: "Failed to generate summary candidates." })
        );
      }
      const data = await res.json().catch(() => ({}));
      const candidates = Array.isArray(data?.candidates) ? data.candidates : [];
      if (!candidates.length) {
        setAutoSummaryError(
          t({ ja: "本文が見つかりませんでした。", en: "No episode text found." })
        );
        return;
      }
      setAutoSummaryCandidates(candidates);
      setSelectedAutoSummary(candidates[0] || "");
    } catch (err) {
      console.error(err);
      setAutoSummaryError(
        getErrorMessage(err, t({ ja: "説明文の生成に失敗しました。", en: "Failed to generate summary." }))
      );
    } finally {
      setAutoSummaryLoading(false);
    }
  };

  const handleApplyAutoSummary = () => {
    if (!selectedAutoSummary) return;
    if (description.trim()) {
      const confirmed = window.confirm(
        t({
          ja: "現在の説明文を選択した候補で上書きしますか？",
          en: "Replace the current description with the selected candidate?",
        })
      );
      if (!confirmed) return;
    }
    setDescription(selectedAutoSummary);
  };

  const handleSuggestTags = async () => {
    if (!id) return;
    try {
      setTagSuggestLoading(true);
      setTagSuggestError("");
      const token = localStorage.getItem("token");
      if (!token) throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));
      const res = await fetch(`${API_BASE}/api/novels/${id}/tag_candidates`, {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
      });
      if (!res.ok) {
        throw new Error(
          t({ ja: "タグ候補の生成に失敗しました。", en: "Failed to generate tag candidates." })
        );
      }
      const data = await res.json().catch(() => ({}));
      const existing = parseTagsInput(tagsInput);
      const existingSet = new Set(existing.map((tag: string) => tag.toLowerCase()));
      const candidates = (data?.candidates || []).filter(
        (tag: string) => !existingSet.has(tag.toLowerCase())
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
        getErrorMessage(err, t({ ja: "タグ候補の生成に失敗しました。", en: "Failed to generate tag candidates." }))
      );
    } finally {
      setTagSuggestLoading(false);
    }
  };

  const handleSuggestTitleCandidates = async () => {
    if (!id) return;
    try {
      setTitleSuggestLoading(true);
      setTitleSuggestError("");
      setTitleCandidates([]);
      const token = localStorage.getItem("token");
      if (!token) throw new Error(t({ ja: "ログインが必要です。", en: "Login required." }));
      const res = await fetch(`${API_BASE}/api/novels/${id}/title_candidates`, {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data.detail || t({ ja: "タイトル候補の生成に失敗しました。", en: "Failed to generate title candidates." })
        );
      }
      const nextCandidates = Array.isArray(data?.candidates)
        ? data.candidates.map((v: unknown) => String(v || "").trim()).filter(Boolean)
        : [];
      if (!nextCandidates.length) {
        throw new Error(
          t({ ja: "タイトル候補を取得できませんでした。", en: "Failed to get title candidates." })
        );
      }
      setTitleCandidates(nextCandidates);
      setTitle(nextCandidates[0]);
    } catch (err) {
      console.error(err);
      setTitleSuggestError(
        getErrorMessage(
          err,
          t({ ja: "タイトル候補の生成に失敗しました。", en: "Failed to generate title candidates." })
        )
      );
    } finally {
      setTitleSuggestLoading(false);
    }
  };

  const handleToggleCandidate = (candidate: string) => {
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
    const nextInput = mergeTagsInput(tagsInput, selected);
    setTagsInput(nextInput);
    const remaining = tagCandidates.filter((tag) => !selectedTagCandidates.has(tag));
    setTagCandidates(remaining);
    setSelectedTagCandidates(new Set());
  };

  const handleSuggestCharacterNames = async () => {
    setCharacterSuggestError("");
    const sourceText = [title, description, tagsInput].filter(Boolean).join("\n");
    if (!sourceText.trim()) {
      setCharacterSuggestError(
        t({
          ja: "タイトル/説明/タグが空のためキャラ名を抽出できません。",
          en: "No title/description/tags to extract character names.",
        })
      );
      return;
    }
    try {
      setCharacterSuggestLoading(true);
      const res = await fetch(`${API_BASE}/api/ai/character_terms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          description,
          tags: tagsInput,
          limit: 8,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "キャラ名の抽出に失敗しました。", en: "Failed to extract character names." })
        );
      }
      const terms = Array.isArray(data?.terms)
        ? data.terms.map((v: unknown) => String(v || "").trim()).filter(Boolean)
        : [];
      if (!terms.length) {
        throw new Error(
          t({ ja: "キャラ名候補を抽出できませんでした。", en: "No character name candidates found." })
        );
      }
      setCharacterNamesInput(terms.slice(0, 5).join(", "));
    } catch (e) {
      console.error(e);
      setCharacterSuggestError(
        getErrorMessage(
          e,
          t({ ja: "キャラ名の抽出中にエラーが発生しました。", en: "Failed while extracting character names." })
        )
      );
    } finally {
      setCharacterSuggestLoading(false);
    }
  };

  const handleAutoFillFanficFields = async () => {
    setCreativeType("fanfic");
    setFanficAutoFillError("");
    setFanficSourceTitleCandidates([]);
    const source = (fanficSourceTitle || "").trim() || (title || "").trim();
    const rawTags = (tagsInput || "")
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean);
    const fallbackChars = rawTags.slice(0, 3).join(", ");
    const nextCharacters = (fanficCharacters || "").trim() || fallbackChars || "主人公, 相手役";
    const charTokens = nextCharacters
      .split(/[,\u3001]/)
      .map((v) => v.trim())
      .filter(Boolean);
    const nextPairing =
      (fanficCoupling || "").trim() ||
      (charTokens.length >= 2 ? `${charTokens[0]}×${charTokens[1]}` : "");
    const nextNotes =
      (fanficNotes || "").trim() ||
      "二次創作です。原作・公式とは関係ありません。解釈違いを含む可能性があります。";

    const charQuery =
      (fanficCharacters || "").trim() ||
      (characterNamesInput || "").trim() ||
      fallbackChars;
    let inferredSourceTitle = source;
    if (charQuery) {
      try {
        setFanficAutoFillLoading(true);
        const res = await fetch(`${API_BASE}/api/ai/novels/auto-fill`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: (title || "").trim() || undefined,
            characters: charQuery,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(
            data?.detail ||
              t({ ja: "タイトル推測に失敗しました。", en: "Failed to infer source title." })
          );
        }
        const candidates = Array.isArray(data?.source_title_candidates)
          ? data.source_title_candidates.map((v: unknown) => String(v || "").trim()).filter(Boolean)
          : [];
        const topCandidates = candidates.slice(0, 5);
        setFanficSourceTitleCandidates(topCandidates);
        inferredSourceTitle =
          String(data?.inferred_source_title || "").trim() || topCandidates[0] || inferredSourceTitle;
      } catch (e) {
        console.error(e);
        setFanficAutoFillError(
          getErrorMessage(
            e,
            t({
              ja: "Google検索でのタイトル推測に失敗したため、ローカル補完のみ行いました。",
              en: "Google title inference failed. Applied local autofill only.",
            })
          )
        );
      } finally {
        setFanficAutoFillLoading(false);
      }
    }

    if (!fanficSourceTitle.trim()) setFanficSourceTitle(inferredSourceTitle);
    if (!fanficCharacters.trim()) {
      setFanficCharacters((characterNamesInput || "").trim() || nextCharacters);
    }
    if (!fanficCoupling.trim()) setFanficCoupling(nextPairing);
    if (!fanficNotes.trim()) setFanficNotes(nextNotes);
  };

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
          <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
            <button
              type="button"
              className="btn btn-border"
              onClick={handleSuggestTags}
              disabled={tagSuggestLoading}
            >
              {tagSuggestLoading
                ? t({ ja: "抽出中...", en: "Extracting..." })
                : t({ ja: "本文からタグ候補を抽出", en: "Suggest tags from text" })}
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

        {canEditFull && (
          <>
            <section
              style={{
                marginBottom: 16,
                border: "1px solid #ddd",
                borderRadius: 8,
                padding: 12,
                background: "#fff",
              }}
            >
              <h3 style={{ marginTop: 0, marginBottom: 8 }}>
                {t({ ja: "AI表紙生成", en: "AI Cover Generator" })}
              </h3>
              <p style={{ marginTop: 0, color: "#666", fontSize: 14 }}>
                {t({
                  ja: "AIが背景イラストを生成します。表紙に入る文字は後から重ねます。",
                  en: "AI generates a background illustration. Title/author text will be overlaid later.",
                })}
              </p>
              {novelCoverImageUrl && (
                <div style={{ marginBottom: 8 }}>
                  <img
                    src={resolveCoverUrl(novelCoverImageUrl)}
                    alt={t({ ja: "現在の表紙", en: "Current cover" })}
                    style={{ width: 180, borderRadius: 8, border: "1px solid #ddd" }}
                  />
                  <div style={{ marginTop: 8 }}>
                    <button
                      type="button"
                      className="btn btn-border"
                      onClick={handleRemoveNovelCover}
                      disabled={coverSaving || coverGenerating || coverRemoving}
                    >
                      {coverRemoving
                        ? t({ ja: "削除中...", en: "Removing..." })
                        : t({ ja: "表紙を削除", en: "Remove cover" })}
                    </button>
                  </div>
                </div>
              )}
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 14, marginBottom: 6 }}>
                  {t({ ja: "ローカル画像を表紙に設定", en: "Set cover from local image" })}
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                  <input type="file" accept="image/*" onChange={handleLocalCoverFileChange} />
                  <button
                    type="button"
                    className="btn btn-border"
                    onClick={handleUploadLocalCover}
                    disabled={localCoverUploading || !localCoverFile}
                  >
                    {localCoverUploading
                      ? t({ ja: "アップロード中...", en: "Uploading..." })
                      : t({ ja: "この画像を表紙に反映", en: "Apply this image as cover" })}
                  </button>
                </div>
                {localCoverFile && (
                  <div style={{ marginTop: 6, fontSize: "0.85rem", color: "#666" }}>
                    {t({ ja: "選択中: {{name}}", en: "Selected: {{name}}" }, { name: localCoverFile.name })}
                  </div>
                )}
                {localCoverError && (
                  <div style={{ marginTop: 6, color: "red" }}>{localCoverError}</div>
                )}
              </div>
              <button type="button" className="btn btn-border" onClick={openCoverModal}>
                {t({ ja: "AI表紙を生成・選択", en: "Generate / Select AI cover" })}
              </button>
              {!isPremium && (
                <p style={{ marginTop: 8, color: "#666", fontSize: 13 }}>
                  {t({
                    ja: "AI表紙生成はプレミアム会員限定です。",
                    en: "AI cover generation is available for premium members only.",
                  })}
                </p>
              )}
            </section>

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
              <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={handleSuggestTitleCandidates}
                  disabled={titleSuggestLoading}
                >
                  {titleSuggestLoading
                    ? t({ ja: "タイトル候補を生成中...", en: "Generating title candidates..." })
                    : t({ ja: "本文からタイトル候補を生成", en: "Generate title candidates from body" })}
                </button>
              </div>
              {titleSuggestError && (
                <div style={{ marginTop: 6, color: "red" }}>{titleSuggestError}</div>
              )}
              {titleCandidates.length > 0 && (
                <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
                  {titleCandidates.map((candidate, idx) => (
                    <button
                      key={`${candidate}-${idx}`}
                      type="button"
                      className="btn btn-border"
                      onClick={() => setTitle(candidate)}
                      style={{ textAlign: "left" }}
                    >
                      {candidate}
                    </button>
                  ))}
                </div>
              )}
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
              <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={handleAutoSummary}
                  disabled={autoSummaryLoading}
                >
                  {autoSummaryLoading
                    ? t({ ja: "自動生成中...", en: "Generating..." })
                    : t({ ja: "本文から候補生成", en: "Generate candidates" })}
                </button>
                <span style={{ fontSize: "0.85rem", color: "#666" }}>
                  {t({ ja: "本文から候補を作成して選択できます", en: "Create candidates and pick one" })}
                </span>
              </div>
              {autoSummaryError && (
                <div style={{ marginTop: 6, color: "red" }}>{autoSummaryError}</div>
              )}
              {autoSummaryCandidates.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ display: "grid", gap: 8 }}>
                    {autoSummaryCandidates.map((candidate) => (
                      <label
                        key={candidate}
                        style={{
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                          padding: "8px 10px",
                          background: "var(--surface-2)",
                          display: "flex",
                          gap: 8,
                          alignItems: "flex-start",
                        }}
                      >
                        <input
                          type="radio"
                          name="auto-summary-candidate"
                          checked={selectedAutoSummary === candidate}
                          onChange={() => setSelectedAutoSummary(candidate)}
                        />
                        <span style={{ fontSize: "0.9rem" }}>{candidate}</span>
                      </label>
                    ))}
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <button
                      type="button"
                      className="btn btn-border"
                      onClick={handleApplyAutoSummary}
                      disabled={!selectedAutoSummary}
                    >
                      {t({ ja: "選択した説明文を追加", en: "Apply selected summary" })}
                    </button>
                  </div>
                </div>
              )}
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
                {t({ ja: "キャラ名（検索・補助用）", en: "Character names (for search/autofill)" })}
                <br />
                <input
                  type="text"
                  value={characterNamesInput}
                  onChange={(e) => setCharacterNamesInput(e.target.value)}
                  style={{ width: "100%", padding: 4 }}
                  placeholder={t({ ja: "例: 五条 悟, 夏油 傑", en: "e.g., Gojo Satoru, Geto Suguru" })}
                />
              </label>
              <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
                <button
                  type="button"
                  className="btn btn-border"
                  onClick={handleSuggestCharacterNames}
                  disabled={characterSuggestLoading}
                >
                  {characterSuggestLoading
                    ? t({ ja: "抽出中...", en: "Extracting..." })
                    : t({ ja: "キャラ名を自動入力", en: "Auto-fill character names" })}
                </button>
              </div>
              {characterSuggestError && (
                <div style={{ marginTop: 6, color: "red" }}>{characterSuggestError}</div>
              )}
            </div>

            {creativeType === "fanfic" && (
              <section
                style={{
                  marginBottom: 10,
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  padding: 10,
                }}
              >
                <h3 style={{ marginTop: 0, marginBottom: 8 }}>
                  {t({ ja: "二次創作向け入力", en: "Fanfic fields" })}
                </h3>
                <div style={{ marginBottom: 8 }}>
                  <button
                    type="button"
                    className="btn btn-border"
                    onClick={handleAutoFillFanficFields}
                    disabled={fanficAutoFillLoading}
                  >
                    {fanficAutoFillLoading
                      ? t({ ja: "推測中...", en: "Inferring..." })
                      : t({ ja: "二次創作向け入力を自動で埋める", en: "Auto-fill fanfic fields" })}
                  </button>
                </div>
                {fanficAutoFillError && <div style={{ marginBottom: 8, color: "red" }}>{fanficAutoFillError}</div>}
                <div style={{ marginBottom: 8 }}>
                  <label>
                    {t({ ja: "原作名", en: "Source title" })}<br />
                    <input
                      type="text"
                      value={fanficSourceTitle}
                      onChange={(e) => setFanficSourceTitle(e.target.value)}
                      style={{ width: "100%", padding: 4 }}
                    />
                  </label>
                  {fanficSourceTitleCandidates.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <div style={{ fontSize: "0.85rem", color: "#666", marginBottom: 6 }}>
                        {t({ ja: "カスタム検索候補（最大5件）", en: "Custom search candidates (up to 5)" })}
                      </div>
                      <div style={{ display: "grid", gap: 6 }}>
                        {fanficSourceTitleCandidates.map((candidate, idx) => (
                          <button
                            key={`fanfic-source-${idx}-${candidate}`}
                            type="button"
                            className="btn btn-border"
                            onClick={() => setFanficSourceTitle(candidate)}
                            style={{
                              textAlign: "left",
                              borderColor: fanficSourceTitle === candidate ? "var(--primary)" : undefined,
                            }}
                          >
                            {candidate}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                <div style={{ marginBottom: 8 }}>
                  <label>
                    {t({ ja: "キャラ", en: "Characters" })}<br />
                    <input
                      type="text"
                      value={fanficCharacters}
                      onChange={(e) => setFanficCharacters(e.target.value)}
                      style={{ width: "100%", padding: 4 }}
                      placeholder={t({ ja: "例: A, B, C", en: "e.g., A, B, C" })}
                    />
                  </label>
                </div>
                <div style={{ marginBottom: 8 }}>
                  <label>
                    {t({ ja: "カップリング", en: "Pairing" })}<br />
                    <input
                      type="text"
                      value={fanficCoupling}
                      onChange={(e) => setFanficCoupling(e.target.value)}
                      style={{ width: "100%", padding: 4 }}
                      placeholder={t({ ja: "例: A×B", en: "e.g., A x B" })}
                    />
                  </label>
                </div>
                <div style={{ marginBottom: 0 }}>
                  <label>
                    {t({ ja: "注意事項", en: "Notes / warnings" })}<br />
                    <textarea
                      rows={3}
                      value={fanficNotes}
                      onChange={(e) => setFanficNotes(e.target.value)}
                      style={{ width: "100%", padding: 4 }}
                    />
                  </label>
                </div>
              </section>
            )}

            <section
              style={{
                marginBottom: 10,
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: 10,
              }}
            >
              <h3 style={{ marginTop: 0, marginBottom: 8 }}>
                {t({ ja: "シリーズ設定（任意）", en: "Series (optional)" })}
              </h3>
              <div style={{ marginBottom: 8 }}>
                <label>
                  {t({ ja: "シリーズ名", en: "Series name" })}<br />
                  <input
                    type="text"
                    value={seriesName}
                    onChange={(e) => setSeriesName(e.target.value)}
                    style={{ width: "100%", padding: 4 }}
                  />
                </label>
              </div>
              <div style={{ marginBottom: 0 }}>
                <label>
                  {t({ ja: "シリーズ順", en: "Series order" })}<br />
                  <input
                    type="number"
                    min="1"
                    value={seriesOrder}
                    onChange={(e) => setSeriesOrder(e.target.value)}
                    style={{ width: "100%", padding: 4 }}
                  />
                </label>
              </div>
            </section>

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
                  onChange={(e) => setStatus(e.target.value === "draft" ? "draft" : "public")}
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

      {showCoverModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.45)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 16,
            zIndex: 1000,
          }}
          onClick={() => setShowCoverModal(false)}
        >
          <div
            style={{
              width: "min(960px, 96vw)",
              maxHeight: "90vh",
              overflow: "auto",
              background: "#fff",
              borderRadius: 10,
              padding: 16,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ marginTop: 0 }}>{t({ ja: "AI表紙生成", en: "AI Cover Generator" })}</h3>
            <p style={{ marginTop: 0, color: "#666", fontSize: 14 }}>
              {t({
                ja: "生成には数秒かかることがあります。表紙に入る文字は後から重ねます。",
                en: "Generation may take several seconds. Text will be overlaid later.",
              })}
            </p>
            <div style={{ display: "grid", gap: 8 }}>
              <input
                type="text"
                value={coverForm.genre}
                onChange={(e) => setCoverForm((prev) => ({ ...prev, genre: e.target.value }))}
                placeholder={t({ ja: "ジャンル (例: SF百合)", en: "Genre (e.g. sci-fi yuri)" })}
              />
              <input
                type="text"
                value={coverForm.mood}
                onChange={(e) => setCoverForm((prev) => ({ ...prev, mood: e.target.value }))}
                placeholder={t({ ja: "雰囲気 (例: 切ない、近未来)", en: "Mood" })}
              />
              <input
                type="text"
                value={coverForm.color_theme}
                onChange={(e) => setCoverForm((prev) => ({ ...prev, color_theme: e.target.value }))}
                placeholder={t({ ja: "色味 (例: 青紫、銀)", en: "Color theme" })}
              />
              <input
                type="number"
                min={0}
                max={20}
                value={coverForm.character_count}
                onChange={(e) => setCoverForm((prev) => ({ ...prev, character_count: Number(e.target.value) }))}
                placeholder={t({ ja: "人数", en: "Character count" })}
              />
              <textarea
                rows={3}
                value={coverForm.extra_prompt}
                onChange={(e) => setCoverForm((prev) => ({ ...prev, extra_prompt: e.target.value }))}
                placeholder={t({ ja: "補足指示 (舞台・構図など)", en: "Additional direction" })}
              />
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button className="btn btn-border" type="button" onClick={handleGenerateCover} disabled={coverGenerating || coverSaving}>
                {coverGenerating ? t({ ja: "生成中...", en: "Generating..." }) : t({ ja: "1枚生成", en: "Generate one image" })}
              </button>
              <button className="btn btn-border" type="button" onClick={() => setShowCoverModal(false)} disabled={coverGenerating || coverSaving}>
                {t({ ja: "閉じる", en: "Close" })}
              </button>
            </div>
            {coverError && <p style={{ color: "red", marginTop: 8 }}>{coverError}</p>}

            <div style={{ marginTop: 16 }}>
              <h4 style={{ marginBottom: 8 }}>{t({ ja: "生成履歴", en: "History" })}</h4>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: 10 }}>
                {coverHistory.map((item) => (
                  <div key={item.id ?? item.image_path ?? item.image_url ?? "cover-history-item"} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 8 }}>
                    {(item.image_url || item.image_path) ? (
                      <img
                        src={item.image_url || `${API_BASE}${item.image_path}`}
                        alt={`cover-${item.id}`}
                        style={{ width: "100%", aspectRatio: "2 / 3", objectFit: "cover", borderRadius: 6 }}
                      />
                    ) : (
                      <div style={{ width: "100%", aspectRatio: "2 / 3", background: "#f3f4f6", borderRadius: 6 }} />
                    )}
                    <div style={{ marginTop: 6, fontSize: 12, color: "#666" }}>
                      {formatDateTimeInUserTimeZone(item.created_at, lang === "en" ? "en-US" : "ja-JP")}
                    </div>
                    <div style={{ marginTop: 4, fontSize: 12 }}>
                      {item.status === "failed" ? t({ ja: "失敗", en: "Failed" }) : item.status}
                    </div>
                    {item.image_path && item.status === "succeeded" && (
                      <>
                        <button
                          type="button"
                          className="btn btn-border"
                          style={{ marginTop: 8, width: "100%" }}
                          onClick={() => handleAdoptCover(item.image_path || "")}
                          disabled={coverSaving || coverGenerating || coverRemoving}
                        >
                          {t({ ja: "この画像を表紙に設定", en: "Use this image as cover" })}
                        </button>
                        <button
                          type="button"
                          className="btn btn-border"
                          style={{ marginTop: 6, width: "100%" }}
                          onClick={handleRemoveNovelCover}
                          disabled={
                            coverSaving ||
                            coverGenerating ||
                            coverRemoving ||
                            String(item.image_path || "") !== String(novelCoverImageUrl || "")
                          }
                        >
                          {coverRemoving
                            ? t({ ja: "削除中...", en: "Removing..." })
                            : t({ ja: "表紙を削除", en: "Remove cover" })}
                        </button>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
