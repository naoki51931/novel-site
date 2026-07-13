import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getApiBase } from "../lib/apiBase";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";

const API_BASE = getApiBase();

type BlogPost = {
  id: number | string;
  title?: string | null;
  body?: string | null;
  image_url?: string | null;
  status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  author_username?: string | null;
  view_count?: number | null;
};

const emptyForm = { title: "", body: "", image_url: "", status: "public" };
const BLOG_CREATE_DRAFT_KEY = "blog_post_draft_v1";
const BLOG_EDIT_DRAFT_PREFIX = "blog_post_edit_draft_v1";

type BlogPostForm = typeof emptyForm;
type BlogPostDraft = BlogPostForm & {
  saved_at?: string;
};

const getEditDraftKey = (postId: BlogPost["id"]) => `${BLOG_EDIT_DRAFT_PREFIX}:${postId}`;

const normalizeBlogPostForm = (value: Partial<BlogPostDraft> | null | undefined): BlogPostForm | null => {
  if (!value || typeof value !== "object") return null;
  return {
    title: typeof value.title === "string" ? value.title : "",
    body: typeof value.body === "string" ? value.body : "",
    image_url: typeof value.image_url === "string" ? value.image_url : "",
    status: value.status === "draft" ? "draft" : "public",
  };
};

const loadStoredBlogDraft = (key: string): BlogPostForm | null => {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    return normalizeBlogPostForm(JSON.parse(raw) as BlogPostDraft);
  } catch (err) {
    console.error("failed to load blog draft", err);
    return null;
  }
};

const hasBlogDraftContent = (form: BlogPostForm) => Boolean(form.title.trim() || form.body.trim() || form.image_url.trim());

const resolveImageUrl = (url: string | null | undefined) => {
  const value = String(url || "").trim();
  if (!value) return "";
  if (/^https?:\/\//i.test(value)) return value;
  return `${API_BASE}${value.startsWith("/") ? value : `/${value}`}`;
};

const getPostForm = (post: BlogPost): BlogPostForm => ({
  title: post.title || "",
  body: post.body || "",
  image_url: post.image_url || "",
  status: post.status === "draft" ? "draft" : "public",
});

export default function BlogManager() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const username = typeof window !== "undefined" ? localStorage.getItem("username") || "" : "";
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<BlogPost["id"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState("");
  const [imageMarkedForDeletion, setImageMarkedForDeletion] = useState(false);
  const [imageInputKey, setImageInputKey] = useState(0);

  const loadPosts = async () => {
    if (!token) return;
    try {
      setLoading(true);
      setError("");
      const res = await fetch(`${API_BASE}/api/blog-posts`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => []);
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "ブログの取得に失敗しました", en: "Failed to load blog posts." }));
      }
      setPosts(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
      setError(getErrorMessage(err, t({ ja: "ブログの取得中にエラーが発生しました", en: "Failed to load blog posts." })));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!token) {
      navigate("/login");
      return;
    }
    loadPosts();
  }, [token]);

  useEffect(() => {
    const draft = loadStoredBlogDraft(BLOG_CREATE_DRAFT_KEY);
    if (draft) setForm(draft);
  }, []);

  useEffect(() => {
    if (!imageFile) {
      setImagePreviewUrl("");
      return undefined;
    }
    const url = URL.createObjectURL(imageFile);
    setImagePreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [imageFile]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const draftKey = editingId ? getEditDraftKey(editingId) : BLOG_CREATE_DRAFT_KEY;
    const timer = window.setTimeout(() => {
      try {
        if (!hasBlogDraftContent(form)) {
          localStorage.removeItem(draftKey);
          return;
        }
        localStorage.setItem(
          draftKey,
          JSON.stringify({
            ...form,
            saved_at: new Date().toISOString(),
          })
        );
      } catch (err) {
        console.error("failed to save blog draft", err);
      }
    }, 1000);

    return () => window.clearTimeout(timer);
  }, [editingId, form]);

  const startEdit = (post: BlogPost) => {
    setEditingId(post.id);
    setForm(loadStoredBlogDraft(getEditDraftKey(post.id)) || getPostForm(post));
    setImageFile(null);
    setImageMarkedForDeletion(false);
    setImageInputKey((value) => value + 1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const resetForm = () => {
    setEditingId(null);
    setForm(loadStoredBlogDraft(BLOG_CREATE_DRAFT_KEY) || emptyForm);
    setImageFile(null);
    setImageMarkedForDeletion(false);
    setImageInputKey((value) => value + 1);
  };

  const uploadBlogImage = async (postId: BlogPost["id"], file: File) => {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch(`${API_BASE}/api/blog-posts/${postId}/image`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || t({ ja: "画像のアップロードに失敗しました", en: "Failed to upload image." }));
    }
    return data;
  };

  const deleteBlogImage = async (postId: BlogPost["id"]) => {
    const res = await fetch(`${API_BASE}/api/blog-posts/${postId}/image`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || t({ ja: "画像の削除に失敗しました", en: "Failed to delete image." }));
    }
    return data;
  };

  const savePost = async (event: FormEvent) => {
    event.preventDefault();
    if (!token) return;
    try {
      setSaving(true);
      setError("");
      const url = editingId ? `${API_BASE}/api/blog-posts/${editingId}` : `${API_BASE}/api/blog-posts`;
      const res = await fetch(url, {
        method: editingId ? "PUT" : "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(form),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "ブログの保存に失敗しました", en: "Failed to save blog post." }));
      }
      const savedPost = data as BlogPost;
      if (savedPost?.id && imageMarkedForDeletion && !imageFile) {
        await deleteBlogImage(savedPost.id);
      }
      if (savedPost?.id && imageFile) {
        await uploadBlogImage(savedPost.id, imageFile);
      }
      try {
        localStorage.removeItem(editingId ? getEditDraftKey(editingId) : BLOG_CREATE_DRAFT_KEY);
      } catch (err) {
        console.error("failed to clear blog draft", err);
      }
      setEditingId(null);
      setForm(emptyForm);
      setImageFile(null);
      setImageMarkedForDeletion(false);
      setImageInputKey((value) => value + 1);
      await loadPosts();
    } catch (err) {
      console.error(err);
      setError(getErrorMessage(err, t({ ja: "ブログの保存中にエラーが発生しました", en: "Failed to save blog post." })));
    } finally {
      setSaving(false);
    }
  };

  const deletePost = async (post: BlogPost) => {
    if (!token) return;
    const ok = window.confirm(t({ ja: "この記事を削除します。よろしいですか？", en: "Delete this blog post?" }));
    if (!ok) return;
    try {
      setError("");
      const res = await fetch(`${API_BASE}/api/blog-posts/${post.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "ブログの削除に失敗しました", en: "Failed to delete blog post." }));
      }
      try {
        localStorage.removeItem(getEditDraftKey(post.id));
      } catch (err) {
        console.error("failed to clear blog edit draft", err);
      }
      if (editingId === post.id) resetForm();
      await loadPosts();
    } catch (err) {
      console.error(err);
      setError(getErrorMessage(err, t({ ja: "ブログの削除中にエラーが発生しました", en: "Failed to delete blog post." })));
    }
  };

  return (
    <div style={{ maxWidth: 840, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/mypage">{t({ ja: "← マイページに戻る", en: "← Back to My Page" })}</Link>
      </div>
      <h2>{t({ ja: "ブログ管理", en: "Blog Manager" })}</h2>
      {username && (
        <p style={{ color: "var(--muted-text)", lineHeight: 1.6 }}>
          {t({ ja: `${username} のブログを作成・更新できます。`, en: `Create and update ${username}'s blog.` })}
        </p>
      )}
      {error && <p style={{ color: "red" }}>{error}</p>}

      <form onSubmit={savePost} style={{ display: "grid", gap: 12, marginTop: 18 }}>
        <div className="form-group">
          <label>{t({ ja: "タイトル", en: "Title" })}</label>
          <input
            className="input"
            value={form.title}
            maxLength={200}
            required
            onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label>{t({ ja: "本文", en: "Body" })}</label>
          <textarea
            className="input"
            value={form.body}
            required
            rows={14}
            onChange={(e) => setForm((prev) => ({ ...prev, body: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label>{t({ ja: "画像", en: "Image" })}</label>
          {(imagePreviewUrl || (!imageMarkedForDeletion && form.image_url)) && (
            <img
              src={imagePreviewUrl || resolveImageUrl(form.image_url)}
              alt=""
              style={{ width: "100%", maxHeight: 260, objectFit: "cover", borderRadius: 8, border: "1px solid var(--border)", marginBottom: 8 }}
            />
          )}
          <input
            key={imageInputKey}
            className="input"
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            onChange={(e) => {
              const file = e.target.files?.[0] || null;
              setImageFile(file);
              if (file) setImageMarkedForDeletion(false);
            }}
          />
          {(imageFile || form.image_url) && (
            <button
              type="button"
              className="btn btn-border"
              style={{ marginTop: 8 }}
              onClick={() => {
                setImageFile(null);
                setImageMarkedForDeletion(Boolean(form.image_url));
                setImageInputKey((value) => value + 1);
              }}
              disabled={saving}
            >
              {t({ ja: "画像を削除", en: "Remove image" })}
            </button>
          )}
        </div>
        <div className="form-group">
          <label>{t({ ja: "公開状態", en: "Status" })}</label>
          <select
            className="input"
            value={form.status}
            onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value }))}
          >
            <option value="public">{t({ ja: "公開", en: "Public" })}</option>
            <option value="draft">{t({ ja: "下書き", en: "Draft" })}</option>
          </select>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="submit" className="btn btn-border" disabled={saving}>
            {saving
              ? t({ ja: "保存中...", en: "Saving..." })
              : editingId
                ? t({ ja: "更新する", en: "Update" })
                : t({ ja: "作成する", en: "Create" })}
          </button>
          {editingId && (
            <button type="button" className="btn btn-border" onClick={resetForm} disabled={saving}>
              {t({ ja: "新規作成に戻る", en: "New post" })}
            </button>
          )}
        </div>
      </form>

      <section style={{ marginTop: 32 }}>
        <h3 style={{ borderBottom: "1px solid #ddd", paddingBottom: 6 }}>
          {t({ ja: "記事一覧", en: "Posts" })}
        </h3>
        {loading ? (
          <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>
        ) : posts.length === 0 ? (
          <p>{t({ ja: "まだブログ記事がありません。", en: "No blog posts yet." })}</p>
        ) : (
          <div style={{ display: "grid", gap: 12, marginTop: 14 }}>
            {posts.map((post) => (
              <article
                key={post.id}
                style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, background: "var(--surface)" }}
              >
                {post.image_url && (
                  <img
                    src={resolveImageUrl(post.image_url)}
                    alt=""
                    style={{ width: "100%", maxHeight: 180, objectFit: "cover", borderRadius: 8, border: "1px solid var(--border)", marginBottom: 10 }}
                  />
                )}
                <h4 style={{ margin: "0 0 6px" }}>{post.title}</h4>
                <div style={{ color: "var(--muted-text)", fontSize: 12, marginBottom: 8, display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <span>{post.status === "draft" ? t({ ja: "下書き", en: "Draft" }) : t({ ja: "公開", en: "Public" })}</span>
                  <span>{t({ ja: "閲覧", en: "Views" })}: {post.view_count ?? 0}</span>
                </div>
                <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, marginTop: 0 }}>
                  {(post.body || "").slice(0, 180)}{(post.body || "").length > 180 ? "..." : ""}
                </p>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {post.status !== "draft" && username && (
                    <Link className="btn btn-border" to={`/users/${encodeURIComponent(username)}/blog/${post.id}`}>
                      {t({ ja: "表示", en: "View" })}
                    </Link>
                  )}
                  <button type="button" className="btn btn-border" onClick={() => startEdit(post)}>
                    {t({ ja: "編集", en: "Edit" })}
                  </button>
                  <button type="button" className="btn btn-border" onClick={() => deletePost(post)}>
                    {t({ ja: "削除", en: "Delete" })}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
