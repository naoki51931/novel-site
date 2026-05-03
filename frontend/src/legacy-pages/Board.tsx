import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch, authTokenExists } from "../lib/api";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";

const BOARD_DRAFT_STORAGE_KEY = "board_post_draft_v1";
const RECAPTCHA_SITE_KEY = (process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY || "").toString().trim();

type BoardPost = {
  id: number;
  parent_post_id?: number | null;
  title?: string | null;
  body?: string | null;
  created_at?: string | null;
  username?: string | null;
  display_name?: string | null;
  guest_name?: string | null;
};

type ReplyDraftMap = Record<number, string>;

const parseBoardDate = (value: string | null | undefined) => {
  const ts = value ? Date.parse(value) : NaN;
  return Number.isFinite(ts) ? ts : 0;
};

export default function Board() {
  const { t, lang } = useI18n();
  const isLoggedIn = authTokenExists();
  const shouldUseRecaptcha = !isLoggedIn && !!RECAPTCHA_SITE_KEY;
  const formSectionRef = useRef<HTMLElement | null>(null);
  const [recaptchaReady, setRecaptchaReady] = useState(!shouldUseRecaptcha);
  const [posts, setPosts] = useState<BoardPost[]>([]);
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
  const [selectedMainThreadId, setSelectedMainThreadId] = useState(() => {
    if (typeof window === "undefined") return "";
    try {
      const raw = localStorage.getItem(BOARD_DRAFT_STORAGE_KEY);
      if (!raw) return "";
      const parsed = JSON.parse(raw);
      return typeof parsed?.selected_main_thread_id === "string"
        ? parsed.selected_main_thread_id
        : "";
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
  const [replyPostingThreadId, setReplyPostingThreadId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [error, setError] = useState("");
  const [replyTitleByThread, setReplyTitleByThread] = useState<ReplyDraftMap>({});
  const [replyBodyByThread, setReplyBodyByThread] = useState<ReplyDraftMap>({});

  const loadPosts = async () => {
    try {
      setError("");
      const data = await apiFetch("/api/board/posts?limit=1000");
      setPosts(Array.isArray(data) ? data : []);
    } catch (error) {
      setError(
        getErrorMessage(error, t({ ja: "掲示板の取得に失敗しました", en: "Failed to load board posts." }))
      );
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
  }, [shouldUseRecaptcha, RECAPTCHA_SITE_KEY]);

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
        } catch (e) {
          reject(e);
        }
      });
    });
  };

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem(
        BOARD_DRAFT_STORAGE_KEY,
        JSON.stringify({
          guest_name: guestName,
          selected_main_thread_id: selectedMainThreadId,
          title,
          body,
        })
      );
    } catch {
      // ignore
    }
  }, [guestName, selectedMainThreadId, title, body]);

  const postsById = useMemo(() => {
    const map = new Map<number, BoardPost>();
    for (const post of posts) {
      map.set(Number(post?.id || 0), post);
    }
    return map;
  }, [posts]);

  const mainThreads = useMemo(() => {
    const mains = (Array.isArray(posts) ? posts : []).filter((post) => {
      const parentId = Number(post?.parent_post_id || 0);
      return !parentId || !postsById.has(parentId);
    });
    return mains.sort((a: BoardPost, b: BoardPost) => {
      const dt = parseBoardDate(b?.created_at) - parseBoardDate(a?.created_at);
      if (dt !== 0) return dt;
      return Number(b?.id || 0) - Number(a?.id || 0);
    });
  }, [posts, postsById]);

  const repliesByMainId = useMemo(() => {
    const grouped = new Map<number, BoardPost[]>();
    for (const post of posts) {
      const parentId = Number(post?.parent_post_id || 0);
      if (!parentId || !postsById.has(parentId)) continue;
      if (!grouped.has(parentId)) grouped.set(parentId, []);
      const replies = grouped.get(parentId);
      if (replies) replies.push(post);
    }
    for (const list of grouped.values()) {
      list.sort((a: BoardPost, b: BoardPost) => {
        const dt = parseBoardDate(a?.created_at) - parseBoardDate(b?.created_at);
        if (dt !== 0) return dt;
        return Number(a?.id || 0) - Number(b?.id || 0);
      });
    }
    return grouped;
  }, [posts, postsById]);

  const selectedMainThread = useMemo(() => {
    if (!selectedMainThreadId) return null;
    return postsById.get(Number(selectedMainThreadId)) || null;
  }, [selectedMainThreadId, postsById]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const trimmedGuestName = guestName.trim();
    const trimmedTitle = title.trim();
    const trimmedBody = body.trim();
    if (!trimmedTitle || !trimmedBody) {
      setError(t({ ja: "タイトルと本文を入力してください", en: "Please enter title and message." }));
      return;
    }
    try {
      setPosting(true);
      setError("");
      const recaptchaToken = shouldUseRecaptcha ? await requestRecaptchaToken("BOARD_POST") : "";
      await apiFetch("/api/board/posts", {
        method: "POST",
        auth: isLoggedIn,
        body: {
          guest_name: trimmedGuestName,
          parent_post_id: selectedMainThreadId ? Number(selectedMainThreadId) : null,
          title: trimmedTitle,
          body: trimmedBody,
          recaptcha_token: recaptchaToken,
          recaptcha_action: "BOARD_POST",
        },
      });
      setGuestName("");
      setSelectedMainThreadId("");
      setTitle("");
      setBody("");
      try {
        localStorage.removeItem(BOARD_DRAFT_STORAGE_KEY);
      } catch {
        // ignore
      }
      await loadPosts();
    } catch (error) {
      setError(getErrorMessage(error, t({ ja: "投稿に失敗しました", en: "Failed to post." })));
    } finally {
      setPosting(false);
    }
  };

  const handleDeletePost = async (postId: number) => {
    try {
      setDeletingId(postId);
      setError("");
      await apiFetch(`/api/admin/board/posts/${postId}`, {
        method: "DELETE",
        credentials: "include",
      });
      setPosts((prev) => prev.filter((post) => post.id !== postId && post.parent_post_id !== postId));
    } catch (error) {
      setError(getErrorMessage(error, t({ ja: "削除に失敗しました", en: "Failed to delete." })));
    } finally {
      setDeletingId(null);
    }
  };

  const handleReplySubmit = async (mainPost: BoardPost) => {
    const mainId = Number(mainPost?.id || 0);
    if (!mainId) return;
    if (!isLoggedIn) {
      setError(t({ ja: "返信にはログインが必要です", en: "Login is required to reply." }));
      return;
    }
    const replyBody = String(replyBodyByThread[mainId] || "").trim();
    const replyTitleInput = String(replyTitleByThread[mainId] || "").trim();
    if (!replyBody) {
      setError(t({ ja: "返信本文を入力してください", en: "Please enter a reply message." }));
      return;
    }
    const fallbackTitle = `Re: ${String(mainPost?.title || "").trim() || `#${mainId}`}`;
    const replyTitle = (replyTitleInput || fallbackTitle).slice(0, 120);

    try {
      setReplyPostingThreadId(mainId);
      setError("");
      await apiFetch("/api/board/posts", {
        method: "POST",
        auth: true,
        body: {
          parent_post_id: mainId,
          title: replyTitle,
          body: replyBody,
        },
      });
      setReplyTitleByThread((prev) => ({ ...prev, [mainId]: "" }));
      setReplyBodyByThread((prev) => ({ ...prev, [mainId]: "" }));
      await loadPosts();
    } catch (error) {
      setError(getErrorMessage(error, t({ ja: "返信に失敗しました", en: "Failed to reply." })));
    } finally {
      setReplyPostingThreadId(null);
    }
  };

  const formatAuthor = (post: BoardPost) => {
    if (post?.username) {
      return (
        <Link to={`/users/${encodeURIComponent(post.username)}`}>{post.username}</Link>
      );
    }
    return <span>{post?.display_name || post?.guest_name || t({ ja: "ゲスト", en: "Guest" })}</span>;
  };

  const handleSelectMainThread = (post: BoardPost) => {
    const id = Number(post?.id || 0);
    if (!id) return;
    setSelectedMainThreadId(String(id));
    if (typeof window !== "undefined") {
      const top = formSectionRef.current?.offsetTop ?? 0;
      window.scrollTo({ top: Math.max(top - 90, 0), behavior: "smooth" });
    }
  };

  return (
    <div style={{ maxWidth: 940, margin: "0 auto" }}>
      <h2>{t({ ja: "掲示板", en: "Board" })}</h2>
      <p style={{ color: "var(--muted-text)", marginTop: 0 }}>
        {t({
          ja: "スレッドフロート型で表示します。既存のメインスレッドを選んで投稿できます。",
          en: "Threads are displayed in a floating style. You can post under an existing main thread.",
        })}
      </p>

      <section
        ref={formSectionRef}
        style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 16 }}
      >
        <h3 style={{ marginTop: 0 }}>{t({ ja: "スレッド投稿", en: "Post to Thread" })}</h3>
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
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 13, color: "var(--muted-text)" }}>
              {t({ ja: "メインスレッド", en: "Main Thread" })}
            </span>
            <select
              value={selectedMainThreadId}
              onChange={(event) => setSelectedMainThreadId(event.target.value)}
              className="search-input"
              style={{ width: "100%" }}
            >
              <option value="">{t({ ja: "新規メインスレッドとして作成", en: "Create as new main thread" })}</option>
              {mainThreads.map((post) => (
                <option key={`main-thread-option-${post.id}`} value={String(post.id)}>
                  #{post.id} {post.title}
                </option>
              ))}
            </select>
          </label>
          {selectedMainThread ? (
            <div style={{ fontSize: 12, color: "var(--muted-text)" }}>
              {t({ ja: "選択中", en: "Selected" })}: #{selectedMainThread.id} {selectedMainThread.title}
            </div>
          ) : null}
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
            <div style={{ fontSize: 12, color: "var(--muted-text)" }}>
              {recaptchaReady
                ? t({ ja: "reCAPTCHA保護: 送信時に自動検証します", en: "reCAPTCHA protection: verified automatically on submit." })
                : t({ ja: "reCAPTCHAを初期化中...", en: "Initializing reCAPTCHA..." })}
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
            <div style={{ fontSize: 12, color: "var(--muted-text)" }}>
              {isLoggedIn
                ? t({ ja: "ログイン中で投稿します", en: "Posting as logged-in user" })
                : t({ ja: "ログインなしでも投稿できます", en: "You can post without login" })}
            </div>
            <button
              type="submit"
              className="btn btn-border"
              disabled={posting || !title.trim() || !body.trim() || (shouldUseRecaptcha && !recaptchaReady)}
            >
              {posting ? t({ ja: "投稿中...", en: "Posting..." }) : t({ ja: "投稿", en: "Post" })}
            </button>
          </div>
        </form>
      </section>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {loading ? (
        <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>
      ) : mainThreads.length === 0 ? (
        <p>{t({ ja: "まだ投稿がありません。", en: "No posts yet." })}</p>
      ) : (
        <div style={{ display: "grid", gap: 14 }}>
          {mainThreads.map((post) => {
            const replies = repliesByMainId.get(Number(post.id)) || [];
            return (
              <section
                key={`thread-main-${post.id}`}
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  padding: 14,
                  background: "var(--surface)",
                  boxShadow: "0 10px 24px var(--shadow)",
                }}
              >
                <article id={`post-${post.id}`}>
                  <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 12, color: "var(--muted-text)", border: "1px solid var(--border)", borderRadius: 999, padding: "1px 8px" }}>
                      {t({ ja: "メイン", en: "Main" })}
                    </span>
                    {post.title}
                  </h3>
                  <div style={{ fontSize: 12, color: "var(--muted-text)", marginTop: 6 }}>
                    {formatAuthor(post)}
                    <span> · </span>
                    <span>
                      {post.created_at
                        ? new Date(post.created_at).toLocaleString(lang === "en" ? "en-US" : "ja-JP", {
                            timeZone: "Asia/Tokyo",
                          })
                        : ""}
                    </span>
                  </div>
                  <p style={{ margin: "10px 0 0", whiteSpace: "pre-wrap" }}>{post.body}</p>
                  <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="btn btn-border"
                      onClick={() => handleSelectMainThread(post)}
                    >
                      {t({ ja: "このメインに投稿", en: "Post under this main" })}
                    </button>
                    {isAdmin && (
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
                    )}
                  </div>
                </article>

                <section style={{ marginTop: 12 }}>
                  <h4 style={{ margin: "0 0 8px", fontSize: 14 }}>
                    {t({ ja: "コメント（返信）", en: "Comments (Replies)" })}
                  </h4>
                  {isLoggedIn ? (
                    <div style={{ display: "grid", gap: 8 }}>
                      <input
                        value={String(replyTitleByThread[post.id] || "")}
                        onChange={(event) =>
                          setReplyTitleByThread((prev) => ({
                            ...prev,
                            [post.id]: event.target.value,
                          }))
                        }
                        maxLength={120}
                        placeholder={t({
                          ja: "返信タイトル（未入力なら自動設定）",
                          en: "Reply title (auto if blank)",
                        })}
                        style={{ padding: "8px 10px", borderRadius: 6, border: "1px solid var(--border)" }}
                      />
                      <textarea
                        value={String(replyBodyByThread[post.id] || "")}
                        onChange={(event) =>
                          setReplyBodyByThread((prev) => ({
                            ...prev,
                            [post.id]: event.target.value,
                          }))
                        }
                        maxLength={5000}
                        rows={3}
                        placeholder={t({ ja: "返信本文", en: "Reply message" })}
                        style={{ padding: "8px 10px", borderRadius: 6, border: "1px solid var(--border)" }}
                      />
                      <div style={{ textAlign: "right" }}>
                        <button
                          type="button"
                          className="btn btn-border"
                          onClick={() => handleReplySubmit(post)}
                          disabled={
                            replyPostingThreadId === Number(post.id) ||
                            !String(replyBodyByThread[post.id] || "").trim()
                          }
                        >
                          {replyPostingThreadId === Number(post.id)
                            ? t({ ja: "返信中...", en: "Replying..." })
                            : t({ ja: "返信する", en: "Reply" })}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p style={{ margin: 0, color: "var(--muted-text)", fontSize: 13 }}>
                      {t({
                        ja: "返信するにはログインしてください（または上部フォームから投稿できます）。",
                        en: "Login to reply (or use the form at the top).",
                      })}
                    </p>
                  )}
                </section>

                {replies.length > 0 && (
                  <div
                    style={{
                      marginTop: 12,
                      marginLeft: 12,
                      paddingLeft: 12,
                      borderLeft: "2px solid var(--border)",
                      display: "grid",
                      gap: 8,
                    }}
                  >
                    {replies.map((reply) => (
                      <article
                        key={`thread-reply-${reply.id}`}
                        id={`post-${reply.id}`}
                        style={{
                          border: "1px solid var(--border)",
                          borderRadius: 10,
                          padding: 10,
                          background: "var(--bg)",
                          boxShadow: "0 6px 14px var(--shadow)",
                        }}
                      >
                        <h4 style={{ margin: 0, fontSize: 16 }}>{reply.title}</h4>
                        <div style={{ fontSize: 12, color: "var(--muted-text)", marginTop: 4 }}>
                          {formatAuthor(reply)}
                          <span> · </span>
                          <span>
                            {reply.created_at
                              ? new Date(reply.created_at).toLocaleString(lang === "en" ? "en-US" : "ja-JP", {
                                  timeZone: "Asia/Tokyo",
                                })
                              : ""}
                          </span>
                        </div>
                        <p style={{ margin: "8px 0 0", whiteSpace: "pre-wrap" }}>{reply.body}</p>
                        {isAdmin && (
                          <div style={{ marginTop: 8 }}>
                            <button
                              type="button"
                              className="btn btn-border"
                              onClick={() => handleDeletePost(reply.id)}
                              disabled={deletingId === reply.id}
                            >
                              {deletingId === reply.id
                                ? t({ ja: "削除中...", en: "Deleting..." })
                                : t({ ja: "削除（管理者）", en: "Delete (Admin)" })}
                            </button>
                          </div>
                        )}
                      </article>
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
