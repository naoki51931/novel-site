import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { getApiBase } from "../lib/apiBase";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { applySeoMeta, buildSeoDescription } from "../lib/seoMeta";

const API_BASE = getApiBase();
const RECAPTCHA_SITE_KEY = (process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY || "").toString().trim();

type BlogPost = {
  id: number | string;
  title?: string | null;
  body?: string | null;
  image_url?: string | null;
  author_username?: string | null;
  view_count?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

const resolveImageUrl = (url: string | null | undefined) => {
  const value = String(url || "").trim();
  if (!value) return "";
  if (/^https?:\/\//i.test(value)) return value;
  return `${API_BASE}${value.startsWith("/") ? value : `/${value}`}`;
};

type BlogComment = {
  id: number | string;
  user_id?: number | string | null;
  username?: string | null;
  guest_name?: string | null;
  display_name?: string | null;
  body?: string | null;
  created_at?: string | null;
};

export default function BlogPostPage() {
  const { username, postId } = useParams();
  const { t } = useI18n();
  const [post, setPost] = useState<BlogPost | null>(null);
  const [comments, setComments] = useState<BlogComment[]>([]);
  const [commentBody, setCommentBody] = useState("");
  const [guestName, setGuestName] = useState("");
  const [postingComment, setPostingComment] = useState(false);
  const [commentError, setCommentError] = useState("");
  const [commentSuccess, setCommentSuccess] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const isLoggedIn = typeof window !== "undefined" && Boolean(localStorage.getItem("token") || localStorage.getItem("access_token"));
  const shouldUseRecaptcha = !isLoggedIn && !!RECAPTCHA_SITE_KEY;
  const [recaptchaReady, setRecaptchaReady] = useState(!shouldUseRecaptcha);

  const loadComments = async () => {
    if (!postId) return;
    try {
      setCommentError("");
      const res = await fetch(`${API_BASE}/api/blog-posts/${encodeURIComponent(postId)}/comments`);
      const data = await res.json().catch(() => []);
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "コメントの取得に失敗しました", en: "Failed to load comments." }));
      }
      setComments(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
      setCommentError(getErrorMessage(err, t({ ja: "コメントの取得中にエラーが発生しました", en: "Failed to load comments." })));
    }
  };

  useEffect(() => {
    const loadPost = async () => {
      try {
        setLoading(true);
        setError("");
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const res = await fetch(`${API_BASE}/api/blog-posts/${encodeURIComponent(postId || "")}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data.detail || t({ ja: "ブログ記事の取得に失敗しました", en: "Failed to load blog post." }));
        }
        setPost(data);
        await loadComments();
      } catch (err) {
        console.error(err);
        setError(getErrorMessage(err, t({ ja: "ブログ記事の取得中にエラーが発生しました", en: "Failed to load blog post." })));
      } finally {
        setLoading(false);
      }
    };
    if (!postId) {
      setError(t({ ja: "記事が指定されていません", en: "No post specified." }));
      setLoading(false);
      return;
    }
    loadPost();
  }, [postId, t]);

  useEffect(() => {
    if (!shouldUseRecaptcha) return;
    if (typeof window === "undefined") return;
    setRecaptchaReady(false);

    const scriptId = "google-recaptcha-enterprise-js";
    let script = document.getElementById(scriptId) as HTMLScriptElement | null;
    if (!script) {
      script = document.createElement("script");
      script.id = scriptId;
      script.src = `https://www.google.com/recaptcha/enterprise.js?render=${encodeURIComponent(RECAPTCHA_SITE_KEY)}`;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }

    const onLoad = () => setRecaptchaReady(true);
    const onError = () => setRecaptchaReady(false);
    script.addEventListener("load", onLoad);
    script.addEventListener("error", onError);
    if (window.grecaptcha?.enterprise) {
      setRecaptchaReady(true);
    }

    return () => {
      script.removeEventListener("load", onLoad);
      script.removeEventListener("error", onError);
    };
  }, [shouldUseRecaptcha]);

  const requestRecaptchaToken = async (action: string): Promise<string> => {
    if (!shouldUseRecaptcha) return "";
    const grecaptchaEnterprise = window.grecaptcha?.enterprise;
    if (!grecaptchaEnterprise) {
      throw new Error(t({ ja: "reCAPTCHAの初期化に失敗しました", en: "Failed to initialize reCAPTCHA." }));
    }
    return await new Promise<string>((resolve, reject) => {
      grecaptchaEnterprise.ready(async () => {
        try {
          const token = await grecaptchaEnterprise.execute(RECAPTCHA_SITE_KEY, { action });
          if (!token) {
            reject(new Error(t({ ja: "reCAPTCHAトークン取得に失敗しました", en: "Failed to get reCAPTCHA token." })));
            return;
          }
          resolve(token);
        } catch (err) {
          reject(err);
        }
      });
    });
  };

  const submitComment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!postId) return;
    const body = commentBody.trim();
    if (!body) {
      setCommentError(t({ ja: "コメントを入力してください。", en: "Please enter a comment." }));
      return;
    }

    try {
      setPostingComment(true);
      setCommentError("");
      setCommentSuccess("");
      const token = typeof window !== "undefined" ? localStorage.getItem("token") || localStorage.getItem("access_token") : null;
      const recaptchaAction = "BLOG_COMMENT";
      const recaptchaToken = shouldUseRecaptcha ? await requestRecaptchaToken(recaptchaAction) : "";
      const res = await fetch(`${API_BASE}/api/blog-posts/${encodeURIComponent(postId)}/comments`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          body,
          guest_name: guestName.trim() || null,
          recaptcha_token: recaptchaToken,
          recaptcha_action: recaptchaAction,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "コメント投稿に失敗しました", en: "Failed to post comment." }));
      }
      setCommentBody("");
      setCommentSuccess(t({ ja: "コメントを投稿しました。", en: "Comment posted." }));
      await loadComments();
    } catch (err) {
      console.error(err);
      setCommentError(getErrorMessage(err, t({ ja: "コメント投稿中にエラーが発生しました", en: "Failed to post comment." })));
    } finally {
      setPostingComment(false);
    }
  };

  useEffect(() => {
    if (loading || error || !post) return undefined;
    const authorName = post.author_username || username || "";
    const title = t({ ja: `${post.title || "ブログ"}｜${authorName} のブログ`, en: `${post.title || "Blog"} | ${authorName}'s Blog` });
    const description = buildSeoDescription(post.body, t({ ja: `${authorName} のブログ記事です。`, en: `Blog post by ${authorName}.` }));
    return applySeoMeta({
      title,
      description,
      canonicalPath: `/users/${encodeURIComponent(authorName)}/blog/${post.id}`,
      ogType: "article",
      robots: "index,follow",
      imageUrl: resolveImageUrl(post.image_url) || undefined,
    });
  }, [loading, error, post, username, t]);

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  const authorName = post?.author_username || username || "";

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to={`/users/${encodeURIComponent(authorName)}`}>{t({ ja: "← 作者ページに戻る", en: "← Back to author page" })}</Link>
      </div>
      {error ? (
        <p style={{ color: "red" }}>{error}</p>
      ) : post ? (
        <>
          <article>
            <h2 style={{ marginBottom: 8 }}>{post.title}</h2>
            <div style={{ color: "var(--muted-text)", fontSize: 13, marginBottom: 18, display: "flex", gap: 12, flexWrap: "wrap" }}>
              <Link to={`/users/${encodeURIComponent(authorName)}`}>{authorName}</Link>
              <span>{t({ ja: "閲覧", en: "Views" })}: {post.view_count ?? 0}</span>
            </div>
            {post.image_url && (
              <img
                src={resolveImageUrl(post.image_url)}
                alt=""
                style={{ width: "100%", maxHeight: 420, objectFit: "cover", borderRadius: 8, border: "1px solid var(--border)", marginBottom: 20 }}
              />
            )}
            <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.9 }}>{post.body}</div>
          </article>

          <section style={{ marginTop: 36, borderTop: "1px solid var(--border)", paddingTop: 20 }}>
            <h3 style={{ marginTop: 0 }}>{t({ ja: "コメント", en: "Comments" })}</h3>
            {commentError && <p style={{ color: "red" }}>{commentError}</p>}
            {commentSuccess && <p style={{ color: "green" }}>{commentSuccess}</p>}
            <div style={{ display: "grid", gap: 12, marginBottom: 20 }}>
              {comments.length === 0 ? (
                <p style={{ color: "var(--muted-text)", margin: 0 }}>
                  {t({ ja: "まだコメントがありません。", en: "No comments yet." })}
                </p>
              ) : (
                comments.map((comment) => (
                  <article
                    key={comment.id}
                    id={`comment-${comment.id}`}
                    style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, background: "var(--surface)" }}
                  >
                    <div style={{ color: "var(--muted-text)", fontSize: 13, marginBottom: 8 }}>
                      {comment.display_name || comment.username || comment.guest_name || t({ ja: "ゲスト", en: "Guest" })}
                    </div>
                    <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{comment.body}</div>
                  </article>
                ))
              )}
            </div>

            {shouldUseRecaptcha && (
              <p style={{ fontSize: 13, color: recaptchaReady ? "var(--muted-text)" : "#b45309" }}>
                {recaptchaReady
                  ? t({ ja: "未ログイン時は bot 対策のため reCAPTCHA が適用されます。", en: "reCAPTCHA is applied for guest comments." })
                  : t({ ja: "reCAPTCHA を読み込み中です。しばらく待ってから投稿してください。", en: "Loading reCAPTCHA. Please wait before posting." })}
              </p>
            )}
            <form onSubmit={submitComment} style={{ display: "grid", gap: 10 }}>
              {!isLoggedIn && (
                <input
                  className="input"
                  value={guestName}
                  maxLength={40}
                  onChange={(event) => setGuestName(event.target.value)}
                  placeholder={t({ ja: "お名前 (任意)", en: "Name (optional)" })}
                />
              )}
              <textarea
                className="input"
                value={commentBody}
                rows={5}
                maxLength={5000}
                required
                onChange={(event) => setCommentBody(event.target.value)}
                placeholder={t({ ja: "コメントを書く", en: "Write a comment" })}
              />
              <button
                type="submit"
                className="btn btn-border"
                disabled={postingComment || !commentBody.trim() || (shouldUseRecaptcha && !recaptchaReady)}
              >
                {postingComment ? t({ ja: "投稿中...", en: "Posting..." }) : t({ ja: "コメント投稿", en: "Post comment" })}
              </button>
            </form>
          </section>
        </>
      ) : null}
    </div>
  );
}
