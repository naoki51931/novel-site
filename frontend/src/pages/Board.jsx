import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch, authTokenExists } from "../lib/api";
import { useI18n } from "../lib/i18n";

const BOARD_DRAFT_STORAGE_KEY = "board_post_draft_v1";
const RECAPTCHA_SITE_KEY = (import.meta.env.VITE_RECAPTCHA_SITE_KEY || "").toString().trim();

export default function Board() {
  const { t, lang } = useI18n();
  const isLoggedIn = authTokenExists();
  const shouldUseRecaptcha = !isLoggedIn && !!RECAPTCHA_SITE_KEY;
  const recaptchaRef = useRef(null);
  const recaptchaWidgetIdRef = useRef(null);
  const [posts, setPosts] = useState([]);
  const [guestName, setGuestName] = useState(() => {
    if (typeof window === "undefined") return "";
    try {
      const raw = localStorage.getItem(BOARD_DRAFT_STORAGE_KEY);
      if (!raw) return "";
      const parsed = JSON.parse(raw);
      return typeof parsed?.guest_name === "string" ? parsed.guest_name : "";
    } catch {
      return "";
    }
  });
  const [title, setTitle] = useState(() => {
    if (typeof window === "undefined") return "";
    try {
      const raw = localStorage.getItem(BOARD_DRAFT_STORAGE_KEY);
      if (!raw) return "";
      const parsed = JSON.parse(raw);
      return typeof parsed?.title === "string" ? parsed.title : "";
    } catch {
      return "";
    }
  });
  const [body, setBody] = useState(() => {
    if (typeof window === "undefined") return "";
    try {
      const raw = localStorage.getItem(BOARD_DRAFT_STORAGE_KEY);
      if (!raw) return "";
      const parsed = JSON.parse(raw);
      return typeof parsed?.body === "string" ? parsed.body : "";
    } catch {
      return "";
    }
  });
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [error, setError] = useState("");
  const [recaptchaToken, setRecaptchaToken] = useState("");

  const loadPosts = async () => {
    try {
      setError("");
      const data = await apiFetch("/api/board/posts");
      setPosts(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message || t({ ja: "掲示板の取得に失敗しました", en: "Failed to load board posts." }));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPosts();
  }, []);

  useEffect(() => {
    const checkAdmin = async () => {
      try {
        await apiFetch("/api/admin/auth/me", { credentials: "include" });
        setIsAdmin(true);
      } catch {
        setIsAdmin(false);
      }
    };
    checkAdmin();
  }, []);

  useEffect(() => {
    if (!shouldUseRecaptcha) return;
    if (!recaptchaRef.current) return;
    if (typeof window === "undefined") return;

    const renderCaptcha = () => {
      if (!window.grecaptcha || !recaptchaRef.current) return;
      if (recaptchaWidgetIdRef.current !== null) return;
      recaptchaWidgetIdRef.current = window.grecaptcha.render(recaptchaRef.current, {
        sitekey: RECAPTCHA_SITE_KEY,
        callback: (token) => setRecaptchaToken(token || ""),
        "expired-callback": () => setRecaptchaToken(""),
        "error-callback": () => setRecaptchaToken(""),
      });
    };

    if (window.grecaptcha) {
      renderCaptcha();
      return;
    }

    const scriptId = "google-recaptcha-api-js";
    let script = document.getElementById(scriptId);
    if (!script) {
      script = document.createElement("script");
      script.id = scriptId;
      script.src = "https://www.google.com/recaptcha/api.js?render=explicit";
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
    script.addEventListener("load", renderCaptcha);
    return () => {
      script.removeEventListener("load", renderCaptcha);
    };
  }, [shouldUseRecaptcha]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem(
        BOARD_DRAFT_STORAGE_KEY,
        JSON.stringify({
          guest_name: guestName,
          title,
          body,
        })
      );
    } catch {
      // ignore
    }
  }, [guestName, title, body]);

  const handleSubmit = async (event) => {
    event.preventDefault();

    const trimmedGuestName = guestName.trim();
    const trimmedTitle = title.trim();
    const trimmedBody = body.trim();
    if (!trimmedTitle || !trimmedBody) {
      setError(t({ ja: "タイトルと本文を入力してください", en: "Please enter title and message." }));
      return;
    }
    if (shouldUseRecaptcha && !recaptchaToken) {
      setError(t({ ja: "reCAPTCHA認証を完了してください", en: "Please complete reCAPTCHA." }));
      return;
    }

    try {
      setPosting(true);
      setError("");
      await apiFetch("/api/board/posts", {
        method: "POST",
        auth: isLoggedIn,
        body: {
          guest_name: trimmedGuestName,
          title: trimmedTitle,
          body: trimmedBody,
          recaptcha_token: recaptchaToken,
        },
      });
      setGuestName("");
      setTitle("");
      setBody("");
      try {
        localStorage.removeItem(BOARD_DRAFT_STORAGE_KEY);
      } catch {
        // ignore
      }
      await loadPosts();
    } catch (e) {
      setError(e.message || t({ ja: "投稿に失敗しました", en: "Failed to post." }));
    } finally {
      if (shouldUseRecaptcha && window.grecaptcha && recaptchaWidgetIdRef.current !== null) {
        window.grecaptcha.reset(recaptchaWidgetIdRef.current);
      }
      setRecaptchaToken("");
      setPosting(false);
    }
  };

  const handleDeletePost = async (postId) => {
    try {
      setDeletingId(postId);
      setError("");
      await apiFetch(`/api/admin/board/posts/${postId}`, {
        method: "DELETE",
        credentials: "include",
      });
      setPosts((prev) => prev.filter((post) => post.id !== postId));
    } catch (e) {
      setError(e.message || t({ ja: "削除に失敗しました", en: "Failed to delete." }));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div style={{ maxWidth: 820, margin: "0 auto" }}>
      <h2>{t({ ja: "掲示板", en: "Board" })}</h2>
      <p style={{ color: "var(--muted-text)", marginTop: 0 }}>
        {t({ ja: "自由に投稿して交流できます。", en: "Post freely and chat with others." })}
      </p>

      <section style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t({ ja: "新規投稿", en: "New post" })}</h3>
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 8 }}>
          {!isLoggedIn && (
            <input
              value={guestName}
              onChange={(event) => setGuestName(event.target.value)}
              maxLength={40}
              placeholder={t({ ja: "名前（未入力ならゲスト）", en: "Name (optional, defaults to Guest)" })}
              style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid var(--border)" }}
            />
          )}
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            maxLength={120}
            placeholder={t({ ja: "タイトル（120文字以内）", en: "Title (max 120 chars)" })}
            style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid var(--border)" }}
          />
          <textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            maxLength={5000}
            rows={5}
            placeholder={t({ ja: "本文（5000文字以内）", en: "Message (max 5000 chars)" })}
            style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid var(--border)" }}
          />
          {shouldUseRecaptcha && (
            <div>
              <div ref={recaptchaRef} />
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 12, color: "var(--muted-text)" }}>
              {isLoggedIn
                ? t({ ja: "ログイン中で投稿します", en: "Posting as logged-in user" })
                : t({ ja: "ログインなしでも投稿できます", en: "You can post without login" })}
            </div>
            <button
              type="submit"
              className="btn btn-border"
              disabled={posting || !title.trim() || !body.trim()}
            >
              {posting ? t({ ja: "投稿中...", en: "Posting..." }) : t({ ja: "投稿", en: "Post" })}
            </button>
          </div>
        </form>
      </section>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {loading ? (
        <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>
      ) : posts.length === 0 ? (
        <p>{t({ ja: "まだ投稿がありません。", en: "No posts yet." })}</p>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {posts.map((post) => (
            <article
              key={post.id}
              style={{
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: 12,
                background: "var(--surface)",
              }}
            >
              <h3 style={{ margin: 0 }}>{post.title}</h3>
              <div style={{ fontSize: 12, color: "var(--muted-text)", marginTop: 4 }}>
                {post.username ? (
                  <>
                    <Link to={`/users/${encodeURIComponent(post.username)}`}>{post.username}</Link>
                    <span> · </span>
                  </>
                ) : (
                  <>
                    <span>{post.display_name || post.guest_name || t({ ja: "ゲスト", en: "Guest" })}</span>
                    <span> · </span>
                  </>
                )}
                <span>
                  {post.created_at
                    ? new Date(post.created_at).toLocaleString(lang === "en" ? "en-US" : "ja-JP", {
                        timeZone: "Asia/Tokyo",
                      })
                    : ""}
                </span>
              </div>
              <p style={{ margin: "10px 0 0", whiteSpace: "pre-wrap" }}>{post.body}</p>
              {isAdmin && (
                <div style={{ marginTop: 10 }}>
                  <button
                    type="button"
                    className="btn btn-border"
                    onClick={() => handleDeletePost(post.id)}
                    disabled={deletingId === post.id}
                  >
                    {deletingId === post.id
                      ? t({ ja: "削除中...", en: "Deleting..." })
                      : t({ ja: "削除（管理者）", en: "Delete (Admin)" })}
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
