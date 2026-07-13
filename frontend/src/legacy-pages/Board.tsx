import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { apiFetch, authTokenExists } from "../lib/api";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { formatDateTimeInUserTimeZone } from "../lib/timezone";

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
  like_count?: number | null;
  is_liked?: boolean | null;
};

type ReplyDraftMap = Record<number, string>;

type BoardMarkdownAction = "bold" | "large" | "link";

const isSafeBoardUrl = (value: string) => /^https?:\/\//i.test(value.trim());

const normalizeBoardMarkdownBlocks = (value: string) =>
  value
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

const clipboardHtmlToBoardMarkdown = (html: string) => {
  if (!html || typeof DOMParser === "undefined") return "";
  const doc = new DOMParser().parseFromString(html, "text/html");

  const inlineToMarkdown = (node: Node): string => {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent || "";
    if (node.nodeType !== Node.ELEMENT_NODE) return "";
    const element = node as HTMLElement;
    const tag = element.tagName.toLowerCase();
    const content = Array.from(element.childNodes).map(inlineToMarkdown).join("");

    if (tag === "br") return "\n";
    if (tag === "strong" || tag === "b") return content ? `**${content}**` : "";
    if (tag === "a") {
      const href = element.getAttribute("href") || "";
      return content && isSafeBoardUrl(href) ? `[${content}](${href})` : content;
    }
    return content;
  };

  const blockToMarkdown = (node: Node): string => {
    if (node.nodeType === Node.TEXT_NODE) return (node.textContent || "").trim();
    if (node.nodeType !== Node.ELEMENT_NODE) return "";
    const element = node as HTMLElement;
    const tag = element.tagName.toLowerCase();
    const content = Array.from(element.childNodes).map(inlineToMarkdown).join("").trim();

    if (!content && tag !== "br") return "";
    if (tag === "h1") return `# ${content}`;
    if (tag === "h2") return `## ${content}`;
    if (tag === "h3") return `### ${content}`;
    if (tag === "li") return `- ${content}`;
    if (tag === "br") return "";
    return content;
  };

  const blocks: string[] = [];
  const walkBlocks = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = (node.textContent || "").trim();
      if (text) blocks.push(text);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const element = node as HTMLElement;
    const tag = element.tagName.toLowerCase();
    if (["h1", "h2", "h3", "p", "div", "li"].includes(tag)) {
      const block = blockToMarkdown(element);
      if (block) blocks.push(block);
      return;
    }
    if (tag === "ul" || tag === "ol" || tag === "body") {
      Array.from(element.childNodes).forEach(walkBlocks);
      return;
    }
    const inline = inlineToMarkdown(element).trim();
    if (inline) blocks.push(inline);
  };

  Array.from(doc.body.childNodes).forEach(walkBlocks);
  return normalizeBoardMarkdownBlocks(blocks.join("\n\n"));
};

const clipboardToBoardMarkdown = (clipboardData: DataTransfer) => {
  const htmlMarkdown = clipboardHtmlToBoardMarkdown(clipboardData.getData("text/html"));
  if (htmlMarkdown) return htmlMarkdown;
  return normalizeBoardMarkdownBlocks(clipboardData.getData("text/plain"));
};

const renderBoldMarkdown = (text: string, keyPrefix: string): ReactNode[] => {
  const parts: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*)/g;
  let lastIndex = 0;
  let index = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index || 0;
    if (start > lastIndex) parts.push(text.slice(lastIndex, start));
    parts.push(<strong key={`${keyPrefix}-bold-${index}`}>{match[0].slice(2, -2)}</strong>);
    lastIndex = start + match[0].length;
    index += 1;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts.length > 0 ? parts : [text];
};

const renderInlineBoardMarkdown = (text: string, keyPrefix: string): ReactNode[] => {
  const parts: ReactNode[] = [];
  const pattern = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
  let lastIndex = 0;
  let index = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index || 0;
    if (start > lastIndex) {
      parts.push(...renderBoldMarkdown(text.slice(lastIndex, start), `${keyPrefix}-text-${index}`));
    }
    const label = match[1];
    const url = match[2];
    parts.push(
      <a key={`${keyPrefix}-link-${index}`} href={url} target="_blank" rel="noopener noreferrer">
        {renderBoldMarkdown(label, `${keyPrefix}-link-label-${index}`)}
      </a>
    );
    lastIndex = start + match[0].length;
    index += 1;
  }
  if (lastIndex < text.length) {
    parts.push(...renderBoldMarkdown(text.slice(lastIndex), `${keyPrefix}-tail`));
  }
  return parts.length > 0 ? parts : [text];
};

const renderBoardMarkdown = (value: string | null | undefined) => {
  const text = String(value || "");
  const lines = text.split(/\r?\n/);
  const nodes: ReactNode[] = [];
  let listItems: ReactNode[] = [];

  const flushList = () => {
    if (listItems.length === 0) return;
    nodes.push(
      <ul key={`list-${nodes.length}`} style={{ margin: "8px 0 0", paddingLeft: 22 }}>
        {listItems}
      </ul>
    );
    listItems = [];
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    const heading = /^(#{1,3})\s+(.+)$/.exec(trimmed);
    const listItem = /^[-*]\s+(.+)$/.exec(trimmed);

    if (!trimmed) {
      flushList();
      nodes.push(<div key={`blank-${index}`} style={{ height: 8 }} />);
      return;
    }

    if (heading) {
      flushList();
      const level = heading[1].length;
      const fontSize = level === 1 ? 28 : level === 2 ? 22 : 18;
      nodes.push(
        <div
          key={`heading-${index}`}
          style={{
            fontSize,
            fontWeight: 800,
            lineHeight: 1.35,
            marginTop: nodes.length ? 10 : 0,
            overflowWrap: "anywhere",
          }}
        >
          {renderInlineBoardMarkdown(heading[2], `heading-${index}`)}
        </div>
      );
      return;
    }

    if (listItem) {
      listItems.push(
        <li key={`li-${index}`} style={{ marginTop: 4, overflowWrap: "anywhere" }}>
          {renderInlineBoardMarkdown(listItem[1], `li-${index}`)}
        </li>
      );
      return;
    }

    flushList();
    nodes.push(
      <p key={`p-${index}`} style={{ margin: nodes.length ? "8px 0 0" : 0, overflowWrap: "anywhere" }}>
        {renderInlineBoardMarkdown(line, `p-${index}`)}
      </p>
    );
  });

  flushList();
  return <div>{nodes}</div>;
};

const renderBoardBody = (value: string | null | undefined) => renderBoardMarkdown(value);

const parseBoardDate = (value: string | null | undefined) => {
  const ts = value ? Date.parse(value) : NaN;
  return Number.isFinite(ts) ? ts : 0;
};

export default function Board() {
  const { t, lang } = useI18n();
  const isLoggedIn = authTokenExists();
  const shouldUseRecaptcha = !isLoggedIn && !!RECAPTCHA_SITE_KEY;
  const formSectionRef = useRef<HTMLElement | null>(null);
  const bodyTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const replyTextareaRefs = useRef<Record<number, HTMLTextAreaElement | null>>({});
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
  const [markdownMode, setMarkdownMode] = useState(() => {
    if (typeof window === "undefined") return false;
    try {
      const raw = localStorage.getItem(BOARD_DRAFT_STORAGE_KEY);
      if (!raw) return false;
      const parsed = JSON.parse(raw);
      return !!parsed?.markdown_mode;
    } catch {
      return false;
    }
  });
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const [replyPostingThreadId, setReplyPostingThreadId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [likingPostIds, setLikingPostIds] = useState<Set<number>>(() => new Set());
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
          markdown_mode: markdownMode,
        })
      );
    } catch {
      // ignore
    }
  }, [guestName, selectedMainThreadId, title, body, markdownMode]);

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

  const handleToggleLike = async (post: BoardPost) => {
    const postId = Number(post?.id || 0);
    if (!postId) return;
    if (!isLoggedIn) {
      setError(t({ ja: "いいねするにはログインが必要です", en: "Login is required to like." }));
      return;
    }
    const currentlyLiked = !!post.is_liked;
    try {
      setLikingPostIds((prev) => {
        const next = new Set(prev);
        next.add(postId);
        return next;
      });
      setError("");
      const data = await apiFetch("/api/board/posts/" + postId + "/like", {
        method: currentlyLiked ? "DELETE" : "POST",
        auth: true,
      });
      setPosts((prev) =>
        prev.map((item) =>
          Number(item.id) === postId
            ? {
                ...item,
                is_liked: typeof data.liked === "boolean" ? data.liked : !currentlyLiked,
                like_count:
                  typeof data.like_count === "number"
                    ? data.like_count
                    : Math.max(0, Number(item.like_count || 0) + (currentlyLiked ? -1 : 1)),
              }
            : item
        )
      );
    } catch (error) {
      setError(getErrorMessage(error, t({ ja: "いいね操作に失敗しました", en: "Failed to update like." })));
    } finally {
      setLikingPostIds((prev) => {
        const next = new Set(prev);
        next.delete(postId);
        return next;
      });
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

  const renderLikeButton = (post: BoardPost) => {
    const postId = Number(post?.id || 0);
    const isBusy = likingPostIds.has(postId);
    const count = Number(post?.like_count || 0);
    const liked = !!post?.is_liked;
    return (
      <button
        type="button"
        className="btn btn-border"
        onClick={() => handleToggleLike(post)}
        disabled={isBusy}
        aria-pressed={liked}
        aria-label={liked ? t({ ja: "いいねを取り消す", en: "Unlike" }) : t({ ja: "いいね", en: "Like" })}
        title={liked ? t({ ja: "いいねを取り消す", en: "Unlike" }) : t({ ja: "いいね", en: "Like" })}
        style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
      >
        <span aria-hidden="true" style={{ color: liked ? "#e7497a" : "var(--muted-text)", fontSize: 16 }}>
          {liked ? "♥" : "♡"}
        </span>
        <span>{count}</span>
      </button>
    );
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


  const applyMarkdownAction = (
    textarea: HTMLTextAreaElement | null,
    value: string,
    setValue: (nextValue: string) => void,
    action: BoardMarkdownAction
  ) => {
    if (!textarea) return;
    const start = textarea.selectionStart ?? value.length;
    const end = textarea.selectionEnd ?? value.length;
    const selected = value.slice(start, end);
    let replacement = selected;
    let nextSelectionStart = start;
    let nextSelectionEnd = end;

    if (action === "bold") {
      const inner = selected || t({ ja: "太字", en: "bold text" });
      replacement = `**${inner}**`;
      nextSelectionStart = start + 2;
      nextSelectionEnd = nextSelectionStart + inner.length;
    } else if (action === "large") {
      const lineStart = value.lastIndexOf("\n", Math.max(start - 1, 0)) + 1;
      const lineEnd = end < value.length ? value.indexOf("\n", end) : -1;
      const rangeEnd = lineEnd === -1 ? value.length : lineEnd;
      const block = value.slice(lineStart, rangeEnd) || t({ ja: "大きい文字", en: "Large text" });
      replacement = block
        .split("\n")
        .map((line) => (line.startsWith("# ") ? line : `# ${line.replace(/^#{1,3}\s+/, "")}`))
        .join("\n");
      const nextValue = `${value.slice(0, lineStart)}${replacement}${value.slice(rangeEnd)}`;
      setValue(nextValue);
      requestAnimationFrame(() => {
        textarea.focus();
        textarea.setSelectionRange(lineStart, lineStart + replacement.length);
      });
      return;
    } else if (action === "link") {
      const selectedUrl = isSafeBoardUrl(selected) ? selected.trim() : "";
      const url = window.prompt(t({ ja: "URLを入力してください", en: "Enter URL" }), selectedUrl || "https://");
      if (!url) return;
      const trimmedUrl = url.trim();
      if (!isSafeBoardUrl(trimmedUrl)) {
        setError(t({ ja: "URLは https:// または http:// で始めてください", en: "URL must start with https:// or http://." }));
        return;
      }
      const label = selected && !isSafeBoardUrl(selected) ? selected : trimmedUrl;
      replacement = `[${label}](${trimmedUrl})`;
      nextSelectionStart = start + 1;
      nextSelectionEnd = nextSelectionStart + label.length;
    }

    const nextValue = `${value.slice(0, start)}${replacement}${value.slice(end)}`;
    setValue(nextValue);
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(nextSelectionStart, nextSelectionEnd);
    });
  };

  const handlePreviewPaste = (event: React.ClipboardEvent<HTMLDivElement>) => {
    const pastedText = clipboardToBoardMarkdown(event.clipboardData);
    if (!pastedText) return;
    event.preventDefault();
    setBody((current: string) => {
      const separator = current && !current.endsWith("\n") ? "\n" : "";
      return `${current}${separator}${pastedText}`.slice(0, 5000);
    });
  };

  const markdownToolButtonStyle = {
    width: 44,
    height: 34,
    padding: 0,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: 800,
    lineHeight: 1,
  } as const;

  const renderMarkdownToolbar = (
    getTextarea: () => HTMLTextAreaElement | null,
    value: string,
    setValue: (nextValue: string) => void
  ) => (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
      <button
        type="button"
        className="btn btn-border"
        onClick={() => applyMarkdownAction(getTextarea(), value, setValue, "bold")}
        title={t({ ja: "選択範囲を太字にする", en: "Make selection bold" })}
        style={markdownToolButtonStyle}
      >
        B
      </button>
      <button
        type="button"
        className="btn btn-border"
        onClick={() => applyMarkdownAction(getTextarea(), value, setValue, "large")}
        title={t({ ja: "選択行を大きい文字にする", en: "Make selected lines large" })}
        style={markdownToolButtonStyle}
      >
        大
      </button>
      <button
        type="button"
        className="btn btn-border"
        onClick={() => applyMarkdownAction(getTextarea(), value, setValue, "link")}
        title={t({ ja: "選択範囲をURLリンクにする", en: "Turn selection into a URL link" })}
        style={{ ...markdownToolButtonStyle, fontSize: 12 }}
      >
        URL
      </button>
      <span style={{ color: "var(--muted-text)", fontSize: 12 }}>
        {t({ ja: "選択してボタンを押すとMarkdown記法を挿入します", en: "Select text, then press a button to insert Markdown." })}
      </span>
    </div>
  );

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
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <button
              type="button"
              className="btn btn-border"
              aria-pressed={markdownMode}
              onClick={() => setMarkdownMode((current) => !current)}
            >
              {markdownMode
                ? t({ ja: "Markdownモード: ON", en: "Markdown mode: ON" })
                : t({ ja: "Markdownモード: OFF", en: "Markdown mode: OFF" })}
            </button>
            <span style={{ color: "var(--muted-text)", fontSize: 12 }}>
              {t({ ja: "# 大きい文字 / **太字** / [表示名](URL) に対応", en: "Supports # large text / **bold** / [label](URL)." })}
            </span>
          </div>
          {markdownMode && renderMarkdownToolbar(() => bodyTextareaRef.current, body, setBody)}
          <textarea
            ref={bodyTextareaRef}
            value={body}
            onChange={(event) => setBody(event.target.value)}
            maxLength={5000}
            rows={5}
            placeholder={t({ ja: "本文（5000文字以内）", en: "Message (max 5000 chars)" })}
            style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid var(--border)" }}
          />
          {markdownMode ? (
            <div
              tabIndex={0}
              onPaste={handlePreviewPaste}
              style={{
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: 10,
                background: "var(--bg)",
                minHeight: 72,
                outlineOffset: 2,
              }}
              title={t({ ja: "ここにMarkdownテキストを貼り付けできます", en: "Paste Markdown text here." })}
            >
              <div style={{ color: "var(--muted-text)", fontSize: 12, marginBottom: 6 }}>
                {t({ ja: "プレビュー（ここに貼り付け可）", en: "Preview (paste here)" })}
              </div>
              {body.trim() ? (
                renderBoardBody(body)
              ) : (
                <div style={{ color: "var(--muted-text)", fontSize: 13 }}>
                  {t({ ja: "Markdownテキストをここに貼り付けると本文に入ります", en: "Paste Markdown text here to add it to the message." })}
                </div>
              )}
            </div>
          ) : null}
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
                        ? formatDateTimeInUserTimeZone(post.created_at, lang === "en" ? "en-US" : "ja-JP")
                        : ""}
                    </span>
                  </div>
                  <div style={{ margin: "10px 0 0" }}>{renderBoardBody(post.body)}</div>
                  <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {renderLikeButton(post)}
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
                      {renderMarkdownToolbar(
                        () => replyTextareaRefs.current[Number(post.id)] || null,
                        String(replyBodyByThread[post.id] || ""),
                        (nextValue) =>
                          setReplyBodyByThread((prev) => ({
                            ...prev,
                            [post.id]: nextValue,
                          }))
                      )}
                      <textarea
                        ref={(element) => {
                          replyTextareaRefs.current[Number(post.id)] = element;
                        }}
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
                              ? formatDateTimeInUserTimeZone(reply.created_at, lang === "en" ? "en-US" : "ja-JP")
                              : ""}
                          </span>
                        </div>
                        <div style={{ margin: "8px 0 0" }}>{renderBoardBody(reply.body)}</div>
                        <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
                          {renderLikeButton(reply)}
                        </div>
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
