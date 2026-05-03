// frontend/src/App.jsx
import AccountSettings from "./legacy-pages/AccountSettings";
import Register from "./legacy-pages/Register";
import { useEffect, useRef, useState } from "react";
import SearchBar from "./components/SearchBar";
import { Routes, Route, Link, useLocation, useNavigate } from "react-router-dom";
import Home from "./legacy-pages/Home";
import NewNovel from "./legacy-pages/NewNovel";
import NovelDetail from "./legacy-pages/NovelDetail";
import NewEpisode from "./legacy-pages/NewEpisode";
import EditNovel from "./legacy-pages/EditNovel";
import EditEpisode from "./legacy-pages/EditEpisode";
import EpisodeDetail from "./legacy-pages/EpisodeDetail";
import StripeReturn from "./legacy-pages/StripeReturn";
import Login from "./legacy-pages/Login";
import OAuthCallback from "./legacy-pages/OAuthCallback";
import Mypage from "./legacy-pages/Mypage";
import UserPage from "./legacy-pages/UserPage";
import AINovelPage from "./legacy-pages/AINovelPage";
import AiLogsPage from "./legacy-pages/AiLogsPage";
import AiChatPage from "./legacy-pages/AiChatPage";
import AiChatPublicPage from "./legacy-pages/AiChatPublicPage";
import AiChatHowToPage from "./legacy-pages/AiChatHowToPage";
import AiChatLPPage from "./legacy-pages/AiChatLPPage";
import DirectMessageThread from "./legacy-pages/DirectMessageThread";
import ResetPassword from "./legacy-pages/ResetPassword";
import CreatorDashboard from "./legacy-pages/CreatorDashboard";
import AuthorDashboard from "./legacy-pages/AuthorDashboard";
import ScheduledEpisodes from "./legacy-pages/ScheduledEpisodes";
import AdminHome from "./legacy-pages/AdminHome";
import AdminPayouts from "./legacy-pages/AdminPayouts";
import AdminLogin from "./legacy-pages/AdminLogin";
import AdminDashboard from "./legacy-pages/AdminDashboard";
import AdminUsers from "./legacy-pages/AdminUsers";
import AdminAiJobs from "./legacy-pages/AdminAiJobs";
import AdminI18nJobs from "./legacy-pages/AdminI18nJobs";
import SupportReturn from "./legacy-pages/SupportReturn";
import SupportPlans from "./legacy-pages/SupportPlans";
import StripePriceIdManual from "./legacy-pages/StripePriceIdManual";
import Notifications from "./legacy-pages/Notifications";
import AuthorLanding from "./legacy-pages/AuthorLanding";
import PremiumLP from "./legacy-pages/PremiumLP";
import Contact from "./legacy-pages/Contact";
import Board from "./legacy-pages/Board";
import TagPage from "./legacy-pages/TagPage";
import AllSites from "./legacy-pages/AllSites";
import FanficPage from "./legacy-pages/FanficPage";
import SeriesPage from "./legacy-pages/SeriesPage";
import DiscoverPage from "./legacy-pages/DiscoverPage";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faBell } from "@fortawesome/free-regular-svg-icons";
import { trackPageView } from "./lib/analytics";
import { useI18n } from "./lib/i18n";
import type { Lang } from "./lib/i18n";
import {
  dismissGuideBubble,
  getDismissedGuideBubbles,
  isOnboardingGuideEligible,
  markGoogleAdsTraffic,
} from "./lib/onboardingGuide";

const ANDROID_NOTIFIED_KEY_PREFIX = "android_notified_notification_ids_v1_";
const ANDROID_NOTIFIED_MAX_IDS = 300;
const GUIDE_REGISTER_VISITED_KEY = "onboarding_register_visited_v1";
const GUIDE_ONBOARDING_DONE_KEY = "onboarding_episode_created_v1";
const GUIDE_LOGGED_IN_USERS_KEY = "onboarding_logged_in_users_v1";
const GUIDE_NOVEL_CREATED_USERS_KEY = "onboarding_novel_created_users_v1";
type SiteKey = "romance" | "history" | "main";
type GuideStep = "none" | "post" | "login" | "register";
type SearchOptions = {
  query?: string;
  excludeQuery?: string;
  sort?: string;
  ageLimit?: string;
  creativeType?: string;
};
type NotificationItem = {
  id?: number | null;
  type?: string | null;
  title?: string | null;
  body?: string | null;
  link_url?: string | null;
};

const LANGUAGE_ORDER: Lang[] = ["ja", "en", "zh-cn", "zh-tw", "ko"];
const LANGUAGE_BUTTON_LABEL = {
  ja: "JP",
  en: "EN",
  "zh-cn": "简",
  "zh-tw": "繁",
  ko: "KO",
};
const NEXT_LANGUAGE_NAME = {
  ja: { ja: "English", en: "English" },
  en: { ja: "简体中文", en: "Simplified Chinese" },
  "zh-cn": { ja: "繁體中文", en: "Traditional Chinese" },
  "zh-tw": { ja: "한국어", en: "Korean" },
  ko: { ja: "日本語", en: "Japanese" },
};
const NEXT_LANGUAGE_NAME_LOCALIZED = {
  ja: { ja: "英語", en: "English", "zh-cn": "英语", "zh-tw": "英語", ko: "영어" },
  en: { ja: "簡体字中国語", en: "Simplified Chinese", "zh-cn": "简体中文", "zh-tw": "簡體中文", ko: "중국어(간체)" },
  "zh-cn": { ja: "繁体字中国語", en: "Traditional Chinese", "zh-cn": "繁体中文", "zh-tw": "繁體中文", ko: "중국어(번체)" },
  "zh-tw": { ja: "韓国語", en: "Korean", "zh-cn": "韩语", "zh-tw": "韓語", ko: "한국어" },
  ko: { ja: "日本語", en: "Japanese", "zh-cn": "日语", "zh-tw": "日語", ko: "일본어" },
};
const HEADER_I18N = {
  home: { ja: "トップ", en: "Home", "zh-cn": "首页", "zh-tw": "首頁", ko: "홈" },
  ranking: { ja: "ランキング", en: "Ranking", "zh-cn": "排行榜", "zh-tw": "排行榜", ko: "랭킹" },
  discover: { ja: "発見", en: "Discover", "zh-cn": "发现", "zh-tw": "發現", ko: "발견" },
  siteSwitch: {
    ja: "ジャンル切替",
    en: "Switch Genre",
    "zh-cn": "切换分类",
    "zh-tw": "切換分類",
    ko: "장르 전환",
  },
  forAuthors: { ja: "作者向け", en: "For Authors", "zh-cn": "作者入口", "zh-tw": "作者入口", ko: "작가용" },
  postNovel: {
    ja: "新規小説投稿",
    en: "Post New Novel",
    "zh-cn": "发布新小说",
    "zh-tw": "發佈新小說",
    ko: "새 소설 등록",
  },
  aiNovel: { ja: "AI小説生成", en: "AI Novel", "zh-cn": "AI小说生成", "zh-tw": "AI小說生成", ko: "AI 소설 생성" },
  aiChat: { ja: "AIチャット", en: "AI Chat", "zh-cn": "AI聊天", "zh-tw": "AI聊天", ko: "AI 채팅" },
  board: { ja: "掲示板", en: "Board", "zh-cn": "论坛", "zh-tw": "論壇", ko: "게시판" },
  premium: { ja: "プレミアム", en: "Premium", "zh-cn": "高级会员", "zh-tw": "高級會員", ko: "프리미엄" },
  fanficTop: { ja: "二次創作", en: "Fanfic", "zh-cn": "同人", "zh-tw": "同人", ko: "팬픽" },
  myPage: { ja: "マイページ", en: "My Page", "zh-cn": "我的主页", "zh-tw": "我的主頁", ko: "마이페이지" },
  login: { ja: "ログイン", en: "Login", "zh-cn": "登录", "zh-tw": "登入", ko: "로그인" },
  register: { ja: "新規登録", en: "Register", "zh-cn": "注册", "zh-tw": "註冊", ko: "회원가입" },
  switchLang: {
    ja: "言語を切り替える",
    en: "Switch language",
    "zh-cn": "切换语言",
    "zh-tw": "切換語言",
    ko: "언어 전환",
  },
  loggedIn: { ja: "ログイン中", en: "Logged in", "zh-cn": "已登录", "zh-tw": "已登入", ko: "로그인됨" },
  user: { ja: "ユーザー", en: "User", "zh-cn": "用户", "zh-tw": "使用者", ko: "사용자" },
  notLoggedIn: {
    ja: "未ログイン",
    en: "Not logged in",
    "zh-cn": "未登录",
    "zh-tw": "未登入",
    ko: "로그인 안 됨",
  },
  notifications: {
    ja: "通知センター",
    en: "Notifications",
    "zh-cn": "通知中心",
    "zh-tw": "通知中心",
    ko: "알림 센터",
  },
  openMenu: { ja: "メニューを開く", en: "Open menu", "zh-cn": "打开菜单", "zh-tw": "開啟選單", ko: "메뉴 열기" },
  support: { ja: "支援", en: "Support", "zh-cn": "赞助", "zh-tw": "贊助", ko: "후원" },
  monthlySupport: {
    ja: "月額支援",
    en: "Monthly Support",
    "zh-cn": "月度赞助",
    "zh-tw": "月度贊助",
    ko: "월간 후원",
  },
  contact: { ja: "お問い合わせ", en: "Contact", "zh-cn": "联系我们", "zh-tw": "聯絡我們", ko: "문의하기" },
  admin: { ja: "管理画面", en: "Admin", "zh-cn": "管理后台", "zh-tw": "管理後台", ko: "관리자" },
};

function normalizeSiteKey(siteKey: string): SiteKey {
  if (siteKey === "romance" || siteKey === "history") return siteKey;
  return "main";
}

function notifyAndroidSiteNotification(item: NotificationItem) {
  try {
    if (typeof window === "undefined") return;
    const bridge = window.AndroidFormBridge;
    if (!bridge || typeof bridge.notifySiteNotification !== "function") return;
    bridge.notifySiteNotification(
      JSON.stringify({
        id: item?.id ?? null,
        type: item?.type || "",
        title: item?.title || "",
        body: item?.body || "",
        link_url: item?.link_url || "",
      })
    );
  } catch {
    // ignore
  }
}

function loadNotifiedIds(storageKey: string): number[] {
  try {
    if (typeof window === "undefined") return [];
    const raw = localStorage.getItem(storageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((v) => Number(v))
      .filter((v) => Number.isFinite(v))
      .slice(0, ANDROID_NOTIFIED_MAX_IDS);
  } catch {
    return [];
  }
}

function saveNotifiedIds(storageKey: string, ids: number[]) {
  try {
    if (typeof window === "undefined") return;
    localStorage.setItem(storageKey, JSON.stringify(ids.slice(0, ANDROID_NOTIFIED_MAX_IDS)));
  } catch {
    // ignore
  }
}

export default function App() {
  const headerRef = useRef<HTMLElement | null>(null);
  const [query, setQuery] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("search_query") || "";
  });
  const [excludeQuery, setExcludeQuery] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("search_exclude_query") || "";
  });
  const [sort, setSort] = useState("new");
  const [ageLimit, setAgeLimit] = useState("");
  const [creativeType, setCreativeType] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [registerVisited, setRegisterVisited] = useState(() => {
    if (typeof window === "undefined") return false;
    try {
      return localStorage.getItem(GUIDE_REGISTER_VISITED_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [dismissedBubbles, setDismissedBubbles] = useState(() => getDismissedGuideBubbles());
  const [expandedBubble, setExpandedBubble] = useState("");
  const navigate = useNavigate();
  const location = useLocation();
  const { t, lang, setLang } = useI18n();
  const siteKey: SiteKey =
    typeof document !== "undefined"
      ? normalizeSiteKey(document.documentElement.dataset.siteKey || "main")
      : "main";
  const siteTitleJaByKey = {
    romance: "恋愛小説Lexis（レクシー/レクシス）",
    history: "歴史小説Lexis（レクシー/レクシス）",
    main: "小説投稿サイトLexis（レクシー/レクシス）",
  };
  const siteTitleEnByKey = {
    romance: "Romance Lexis",
    history: "History Lexis",
    main: "Lexis",
  };
  const siteTitleJa = siteTitleJaByKey[siteKey] || siteTitleJaByKey.main;
  const siteTitleEn = siteTitleEnByKey[siteKey] || siteTitleEnByKey.main;
  const siteTitleZhCnByKey = {
    romance: "恋爱小说Lexis",
    history: "历史小说Lexis",
    main: "Lexis小说投稿站",
  };
  const siteTitleZhTwByKey = {
    romance: "戀愛小說Lexis",
    history: "歷史小說Lexis",
    main: "Lexis小說投稿站",
  };
  const siteTitleKoByKey = {
    romance: "로맨스 소설 Lexis",
    history: "역사 소설 Lexis",
    main: "Lexis 소설 투고 사이트",
  };
  const siteTitleZhCn = siteTitleZhCnByKey[siteKey] || siteTitleZhCnByKey.main;
  const siteTitleZhTw = siteTitleZhTwByKey[siteKey] || siteTitleZhTwByKey.main;
  const siteTitleKo = siteTitleKoByKey[siteKey] || siteTitleKoByKey.main;
  const isAuthorsPage = location.pathname === "/authors";
  const isAllPage = location.pathname === "/all";
  const username =
    typeof window !== "undefined" ? localStorage.getItem("username") : null;
  const hasToken =
    typeof window !== "undefined"
      ? !!(localStorage.getItem("token") || localStorage.getItem("access_token"))
      : false;
  const canShowGuides = isOnboardingGuideEligible();
  const onboardingDoneForUser = (() => {
    if (typeof window === "undefined" || !hasToken || !username) return false;
    try {
      const raw = localStorage.getItem(GUIDE_ONBOARDING_DONE_KEY);
      if (!raw) return false;
      const list = JSON.parse(raw);
      return Array.isArray(list) && list.includes(username);
    } catch {
      return false;
    }
  })();
  const novelCreatedForUser = (() => {
    if (typeof window === "undefined" || !hasToken || !username) return false;
    try {
      const raw = localStorage.getItem(GUIDE_NOVEL_CREATED_USERS_KEY);
      if (!raw) return false;
      const list = JSON.parse(raw);
      return Array.isArray(list) && list.includes(username);
    } catch {
      return false;
    }
  })();
  const activeGuideStep: GuideStep = !canShowGuides
    ? "none"
    : onboardingDoneForUser
      ? "none"
      : novelCreatedForUser
        ? "none"
      : hasToken
        ? "post"
        : registerVisited
          ? "login"
          : "register";
  const isBubbleVisible = (key: string) => !dismissedBubbles.has(String(key));
  const handleDismissBubble = (e: React.MouseEvent<HTMLElement>, key: string) => {
    e.preventDefault();
    e.stopPropagation();
    dismissGuideBubble(key);
    setDismissedBubbles(getDismissedGuideBubbles());
    setExpandedBubble((prev) => (prev === key ? "" : prev));
  };
  const handleExpandBubble = (e: React.MouseEvent<HTMLElement>, key: string) => {
    e.preventDefault();
    e.stopPropagation();
    setExpandedBubble((prev) => (prev === key ? "" : key));
  };
  const loginGuideText = hasToken
    ? t({
        ja: "ログイン済みです",
        en: "Already logged in",
      })
    : t({
        ja: "まずはログイン",
        en: "Login first",
      });
  const registerGuideText = t({
    ja: "会員登録はこちら",
    en: "Register here",
  });
  const postGuideText = t({
    ja: "小説作成はこちら",
    en: "Create novel here",
  });
  const POST_LOGIN_REDIRECT_KEY = "post_login_redirect_v1";
  const LOGIN_CHECK_INTERVAL_MS = 10 * 60 * 1000;
  const currentLangIndex = Math.max(0, LANGUAGE_ORDER.indexOf(lang));
  const nextLang = LANGUAGE_ORDER[(currentLangIndex + 1) % LANGUAGE_ORDER.length];

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    setQuery(params.get("q") ?? "");
    setExcludeQuery(params.get("exclude") ?? "");
    setSort(params.get("sort") || "new");
    setAgeLimit(params.get("age_limit") || "");
    setCreativeType(params.get("creative_type") || "");
  }, [location.search]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    markGoogleAdsTraffic(location.search);
  }, [location.search]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (location.pathname !== "/register") return;
    setRegisterVisited(true);
    try {
      localStorage.setItem(GUIDE_REGISTER_VISITED_KEY, "1");
    } catch {
      // ignore
    }
  }, [location.pathname]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!hasToken || !username) return;
    try {
      const raw = localStorage.getItem(GUIDE_LOGGED_IN_USERS_KEY);
      const parsed = JSON.parse(raw || "[]");
      const current = Array.isArray(parsed) ? parsed : [];
      if (!current.includes(username)) {
        current.push(username);
        localStorage.setItem(GUIDE_LOGGED_IN_USERS_KEY, JSON.stringify(current));
      }
    } catch {
      localStorage.setItem(GUIDE_LOGGED_IN_USERS_KEY, JSON.stringify([username]));
    }
  }, [hasToken, username]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    trackPageView();
  }, [location.pathname, location.search, location.hash]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem("search_query", query ?? "");
  }, [query]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem("search_exclude_query", excludeQuery ?? "");
  }, [excludeQuery]);

  useEffect(() => {
    const isLoginRoute = () => {
      const path = location.pathname;
      return (
        path === "/" ||
        path === "/authors" ||
        path === "/all" ||
        path.startsWith("/ai-novel") ||
        path.startsWith("/ai_chat") ||
        path.startsWith("/board") ||
        path.startsWith("/tags/") ||
        path.startsWith("/novels/") ||
        path.startsWith("/episodes/") ||
        path.startsWith("/users/") ||
        path === "/premium" ||
        path === "/contact" ||
        path === "/login" ||
        path === "/register" ||
        path === "/reset-password" ||
        path === "/oauth/callback"
      );
    };

    const isTokenExpired = (token: string) => {
      try {
        const parts = token.split(".");
        if (parts.length < 2) return false;
        const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
        const padded = base64 + "===".slice((base64.length + 3) % 4);
        const payload = JSON.parse(atob(padded));
        const exp = payload?.exp;
        if (!exp) return false;
        return Date.now() >= exp * 1000;
      } catch {
        return false;
      }
    };

    const checkLoginStatus = () => {
      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("token") || localStorage.getItem("access_token")
          : null;
      if (token && isTokenExpired(token)) {
        localStorage.removeItem("token");
        localStorage.removeItem("access_token");
      }

      const hasToken =
        typeof window !== "undefined"
          ? !!(localStorage.getItem("token") || localStorage.getItem("access_token"))
          : false;
      if (!hasToken && !isLoginRoute()) {
        const redirectPath = `${location.pathname}${location.search}${location.hash || ""}`;
        try {
          localStorage.setItem(POST_LOGIN_REDIRECT_KEY, redirectPath);
        } catch {
          // ignore
        }
        navigate("/login", { replace: true });
      }
    };

    checkLoginStatus();
    const timer = setInterval(checkLoginStatus, LOGIN_CHECK_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [location.pathname, location.search, location.hash, navigate]);

  useEffect(() => {
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("token") || localStorage.getItem("access_token")
        : null;
    if (!token) {
      setUnreadCount(0);
      return;
    }

    const loadUnreadCount = async () => {
      try {
        const res = await fetch("/api/notifications/unread_count", {
          headers: { Authorization: "Bearer " + token },
        });
        if (res.status === 401) {
          setUnreadCount(0);
          return;
        }
        if (!res.ok) return;
        const data = await res.json().catch(() => ({}));
        setUnreadCount(Math.max(0, Number(data.count) || 0));
      } catch {
        // ignore
      }
    };

    loadUnreadCount();
  }, [location.pathname, hasToken]);

  useEffect(() => {
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("token") || localStorage.getItem("access_token")
        : null;
    if (!token) return;
    const bridge =
      typeof window !== "undefined" ? window.AndroidFormBridge : null;
    // AndroidアプリでFCM登録できる環境では、Web側の疑似通知を止めて二重通知を防ぐ
    if (bridge && typeof bridge.registerMobilePush === "function") return;

    const username =
      typeof window !== "undefined" ? localStorage.getItem("username") || "user" : "user";
    const storageKey = `${ANDROID_NOTIFIED_KEY_PREFIX}${username}`;
    const notifiedIds = new Set(loadNotifiedIds(storageKey));

    const poll = async () => {
      try {
        const res = await fetch("/api/notifications?unread_only=true&limit=30", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.status === 401 || !res.ok) return;
        const items = await res.json().catch(() => []);
        if (!Array.isArray(items) || items.length === 0) return;
        const ordered = items
          .filter((n) => typeof n?.id === "number")
          .slice()
          .sort((a, b) => a.id - b.id);

        let changed = false;
        if (!bridge || typeof bridge.notifySiteNotification !== "function") return;
        for (const item of ordered) {
          if (notifiedIds.has(item.id)) continue;
          notifyAndroidSiteNotification(item);
          notifiedIds.add(item.id);
          changed = true;
        }
        if (changed) {
          saveNotifiedIds(storageKey, Array.from(notifiedIds).sort((a, b) => b - a));
        }
      } catch {
        // ignore
      }
    };

    poll();
    const timer = setInterval(poll, 15000);
    return () => clearInterval(timer);
  }, [hasToken]);

  useEffect(() => {
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("token") || localStorage.getItem("access_token")
        : null;
    if (!token) return;
    let stopped = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const tryRegister = () => {
      if (stopped) return false;
      try {
        const bridge =
          typeof window !== "undefined" ? window.AndroidFormBridge : null;
        if (!bridge || typeof bridge.registerMobilePush !== "function") return false;
        bridge.registerMobilePush(token);
        return true;
      } catch {
        return false;
      }
    };

    const ok = tryRegister();
    if (!ok) {
      timer = setInterval(() => {
        if (tryRegister()) {
          if (timer) clearInterval(timer);
          timer = null;
        }
      }, 3000);
    }

    return () => {
      stopped = true;
      if (timer) clearInterval(timer);
    };
  }, [hasToken, location.pathname]);

  useEffect(() => {
    if (typeof window === "undefined" || typeof document === "undefined") return undefined;
    const root = document.documentElement;
    const header = headerRef.current;
    if (!header) return undefined;

    const syncHeaderHeight = () => {
      root.style.setProperty("--mobile-header-height", `${header.offsetHeight}px`);
    };

    syncHeaderHeight();
    window.addEventListener("resize", syncHeaderHeight);

    const observer =
      typeof ResizeObserver !== "undefined" ? new ResizeObserver(syncHeaderHeight) : null;
    observer?.observe(header);

    return () => {
      window.removeEventListener("resize", syncHeaderHeight);
      observer?.disconnect();
    };
  }, [menuOpen, lang, unreadCount]);

  return (
    <div>
      <header ref={headerRef} className={`site-header ${menuOpen ? "menu-open" : ""}`}>
        <div className="site-header-left">
          <h1 className="site-title">
            {t({ ja: siteTitleJa, en: siteTitleEn, "zh-cn": siteTitleZhCn, "zh-tw": siteTitleZhTw, ko: siteTitleKo })}
          </h1>
        </div>

        {/* ナビゲーション */}
        <nav className={`nav-links ${menuOpen ? "nav-open" : ""}`}>
          <Link to="/" className="nav-link" onClick={() => setMenuOpen(false)}>
            {t(HEADER_I18N.home)}
          </Link>
          <Link to="/ranking" className="nav-link" onClick={() => setMenuOpen(false)}>
            {t(HEADER_I18N.ranking)}
          </Link>
          <Link to="/discover" className="nav-link" onClick={() => setMenuOpen(false)}>
            {t(HEADER_I18N.discover)}
          </Link>
          <Link
            to="/all"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            {t(HEADER_I18N.siteSwitch)}
          </Link>
          <Link
            to="/authors"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            {t(HEADER_I18N.forAuthors)}
          </Link>
          <Link
            to="/novels/new"
            className={`nav-link ${activeGuideStep === "post" ? "nav-link-with-guide onboarding-guide-anchor" : ""}`.trim()}
            onClick={() => setMenuOpen(false)}
          >
            {activeGuideStep === "post" && isBubbleVisible("app_post") && (
              <span
                className={`onboarding-guide-pop onboarding-guide-pop-below ${expandedBubble === "app_post" ? "is-expanded" : ""}`.trim()}
                role="note"
                onClick={(e) => handleExpandBubble(e, "app_post")}
              >
                <span className="onboarding-guide-message">{postGuideText}</span>
                <span className="onboarding-guide-dismiss" role="button" tabIndex={0} onClick={(e) => handleDismissBubble(e, "app_post")}>
                  {t({ ja: "吹き出しを消す", en: "Dismiss bubble" })}
                </span>
                <span
                  className="onboarding-guide-close"
                  role="button"
                  tabIndex={0}
                  onClick={(e) => handleDismissBubble(e, "app_post")}
                >
                  ×
                </span>
              </span>
            )}
            {t(HEADER_I18N.postNovel)}
          </Link>
          <Link
            to="/ai-novel?mode=new_novel"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            {t(HEADER_I18N.aiNovel)}
          </Link>
          <Link
            to="/ai_chat"
            className="nav-link"
            style={{ position: "relative", zIndex: 10 }}
            onClick={() => setMenuOpen(false)}
          >
            {t(HEADER_I18N.aiChat)}
          </Link>
          <Link
            to="/board"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            {t(HEADER_I18N.board)}
          </Link>
          <Link
            to="/premium"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            {t(HEADER_I18N.premium)}
          </Link>
          <Link
            to="/fanfic"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            {t(HEADER_I18N.fanficTop)}
          </Link>
          <Link
            to="/mypage"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            {t(HEADER_I18N.myPage)}
          </Link>
          <Link
            to="/login"
            className={`nav-link ${activeGuideStep === "login" ? "nav-link-with-guide onboarding-guide-anchor" : ""}`.trim()}
            onClick={() => setMenuOpen(false)}
          >
            {activeGuideStep === "login" && isBubbleVisible("app_login") && (
              <span
                className={`onboarding-guide-pop ${expandedBubble === "app_login" ? "is-expanded" : ""}`.trim()}
                role="note"
                onClick={(e) => handleExpandBubble(e, "app_login")}
              >
                <span className="onboarding-guide-message">{loginGuideText}</span>
                <span className="onboarding-guide-dismiss" role="button" tabIndex={0} onClick={(e) => handleDismissBubble(e, "app_login")}>
                  {t({ ja: "吹き出しを消す", en: "Dismiss bubble" })}
                </span>
                <span
                  className="onboarding-guide-close"
                  role="button"
                  tabIndex={0}
                  onClick={(e) => handleDismissBubble(e, "app_login")}
                >
                  ×
                </span>
              </span>
            )}
            {t(HEADER_I18N.login)}
          </Link>
          <Link
            to="/register"
            className={`nav-link nav-link-accent ${activeGuideStep === "register" ? "nav-link-with-guide onboarding-guide-anchor" : ""}`.trim()}
            onClick={() => setMenuOpen(false)}
          >
            {activeGuideStep === "register" && isBubbleVisible("app_register") && (
              <span
                className={`onboarding-guide-pop ${expandedBubble === "app_register" ? "is-expanded" : ""}`.trim()}
                role="note"
                onClick={(e) => handleExpandBubble(e, "app_register")}
              >
                <span className="onboarding-guide-message">{registerGuideText}</span>
                <span className="onboarding-guide-dismiss" role="button" tabIndex={0} onClick={(e) => handleDismissBubble(e, "app_register")}>
                  {t({ ja: "吹き出しを消す", en: "Dismiss bubble" })}
                </span>
                <span
                  className="onboarding-guide-close"
                  role="button"
                  tabIndex={0}
                  onClick={(e) => handleDismissBubble(e, "app_register")}
                >
                  ×
                </span>
              </span>
            )}
            {t(HEADER_I18N.register)}
          </Link>
        </nav>

        <div className="header-right">
          <button
            type="button"
            className="lang-toggle btn btn-border"
            onClick={() => setLang(nextLang)}
            aria-label={t(HEADER_I18N.switchLang)}
            title={t({
              ja: `${NEXT_LANGUAGE_NAME[lang]?.ja || "English"}へ切り替え`,
              en: `Switch to ${NEXT_LANGUAGE_NAME[lang]?.en || "English"}`,
              "zh-cn": `切换到${NEXT_LANGUAGE_NAME_LOCALIZED[lang]?.["zh-cn"] || "English"}`,
              "zh-tw": `切換到${NEXT_LANGUAGE_NAME_LOCALIZED[lang]?.["zh-tw"] || "English"}`,
              ko: `${NEXT_LANGUAGE_NAME_LOCALIZED[lang]?.ko || "English"}로 전환`,
            })}
          >
            {LANGUAGE_BUTTON_LABEL[lang] || "JP"}
          </button>
          <div className="login-status">
            {hasToken ? (
              <span>
                {t(HEADER_I18N.loggedIn)}:{" "}
                {username ? (
                  <Link
                    className="user-link"
                    to={`/users/${encodeURIComponent(username)}`}
                  >
                    {username}
                  </Link>
                ) : (
                  t(HEADER_I18N.user)
                )}
              </span>
            ) : (
              <button
                type="button"
                className="btn btn-border"
                onClick={() => {
                  setMenuOpen(false);
                  navigate("/login");
                }}
                style={{ fontSize: 12, padding: "4px 8px", lineHeight: 1.2 }}
              >
                {t(HEADER_I18N.notLoggedIn)}
              </button>
            )}
          </div>
          <Link
            to="/notifications"
            className="nav-bell"
            aria-label={t(HEADER_I18N.notifications)}
            title={t(HEADER_I18N.notifications)}
            onClick={() => setMenuOpen(false)}
          >
            <FontAwesomeIcon icon={faBell} />
            {unreadCount > 0 && (
              <span className="nav-bell-badge">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </Link>
          {/* スマホ用ハンバーガー */}
          {activeGuideStep !== "none" && isBubbleVisible("app_menu") && (
            <span
              className={`onboarding-guide-pop onboarding-guide-pop-right onboarding-guide-pop-below onboarding-guide-pop-menu ${expandedBubble === "app_menu" ? "is-expanded" : ""}`.trim()}
              role="note"
              onClick={(e) => handleExpandBubble(e, "app_menu")}
            >
              <span className="onboarding-guide-message">{t({ ja: "ここをタップ", en: "Tap here" })}</span>
              <span className="onboarding-guide-dismiss" role="button" tabIndex={0} onClick={(e) => handleDismissBubble(e, "app_menu")}>
                {t({ ja: "吹き出しを消す", en: "Dismiss bubble" })}
              </span>
              <span
                className="onboarding-guide-close"
                role="button"
                tabIndex={0}
                onClick={(e) => handleDismissBubble(e, "app_menu")}
              >
                ×
              </span>
            </span>
          )}
          <button
            type="button"
            className={`nav-toggle ${menuOpen ? "nav-toggle-open" : ""} ${activeGuideStep !== "none" ? "onboarding-guide-anchor onboarding-guide-anchor-right" : ""}`.trim()}
            onClick={() => setMenuOpen((v) => !v)}
            aria-label={t(HEADER_I18N.openMenu)}
          >
            <span />
            <span />
            <span />
          </button>
        </div>
      </header>

      {/* 検索バーはヘッダーの下に固定 */}
      {!isAuthorsPage && !isAllPage && (
        <SearchBar
          query={query}
          excludeQuery={excludeQuery}
          sort={sort}
          ageLimit={ageLimit}
          creativeType={creativeType}
          onChangeQuery={setQuery}
          onChangeExcludeQuery={setExcludeQuery}
          onChangeSort={setSort}
          onChangeAgeLimit={setAgeLimit}
          onChangeCreativeType={setCreativeType}
          onSearch={(searchOptions: SearchOptions = {}) => {
            const {
              query: inputQuery,
              excludeQuery: inputExclude,
              sort: inputSort,
              ageLimit: inputAgeLimit,
              creativeType: inputCreativeType,
            } = searchOptions;
            setMenuOpen(false);
            const q = (inputQuery ?? "").trim();
            const exclude = (inputExclude ?? "").trim();
            const sortValue = (inputSort || "new").trim();
            const ageValue = (inputAgeLimit || "").trim();
            const creativeValue = (inputCreativeType || "").trim();
            const params = new URLSearchParams();
            if (q) params.set("q", q);
            if (exclude) params.set("exclude", exclude);
            if (sortValue && sortValue !== "new") params.set("sort", sortValue);
            if (ageValue) params.set("age_limit", ageValue);
            if (creativeValue) params.set("creative_type", creativeValue);
            if (!q && !exclude && !ageValue && !creativeValue && sortValue === "new") {
              navigate("/");
              return;
            }
            navigate(`/?${params.toString()}`);
          }}
        />
      )}

      <main style={{ padding: "0 16px 32px" }}>
        <Routes>
          <Route path="/mypage/settings" element={<AccountSettings />} />
          <Route
            path="/"
            element={
              <Home
                query={query}
                excludeQuery={excludeQuery}
                sort={sort}
                ageLimit={ageLimit}
                creativeType={creativeType}
              />
            }
          />
          <Route
            path="/ranking"
            element={
              <Home
                query={query}
                excludeQuery={excludeQuery}
                sort={sort}
                ageLimit={ageLimit}
                creativeType={creativeType}
                showRanking
                rankingOnly
              />
            }
          />
          <Route path="/discover" element={<DiscoverPage />} />
          <Route path="/all" element={<AllSites />} />
          <Route path="/tags" element={<TagPage />} />
          <Route path="/tags/:slug" element={<TagPage />} />
          <Route path="/series/:slug" element={<SeriesPage />} />
          <Route path="/authors" element={<AuthorLanding />} />
          <Route path="/login" element={<Login />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/oauth/callback" element={<OAuthCallback />} />
          <Route path="/register" element={<Register />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/board" element={<Board />} />
          <Route path="/premium" element={<PremiumLP />} />
          <Route
            path="/fanfic"
            element={
              <FanficPage
                query={query}
                excludeQuery={excludeQuery}
                sort={sort}
                ageLimit={ageLimit}
              />
            }
          />
          <Route path="/mypage" element={<Mypage />} />
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/me/creator" element={<CreatorDashboard />} />
          <Route path="/author/dashboard" element={<AuthorDashboard />} />
          <Route path="/me/scheduled-episodes" element={<ScheduledEpisodes />} />
          <Route path="/me/support-plans" element={<SupportPlans />} />
          <Route path="/me/support-plans/manual" element={<StripePriceIdManual />} />
          <Route path="/admin" element={<AdminHome />} />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/admin/payouts" element={<AdminPayouts />} />
          <Route path="/admin/dashboard" element={<AdminDashboard />} />
          <Route path="/admin/users" element={<AdminUsers />} />
          <Route path="/admin/ai-jobs" element={<AdminAiJobs />} />
          <Route path="/admin/i18n-jobs" element={<AdminI18nJobs />} />
          <Route path="/users/:username" element={<UserPage />} />
          <Route path="/dms/:threadId" element={<DirectMessageThread />} />
          <Route path="/novels/new" element={<NewNovel />} />
          <Route path="/novels/:id" element={<NovelDetail />} />
          <Route path="/novels/:id/edit" element={<EditNovel />} />
          <Route path="/novels/:id/episodes/new" element={<NewEpisode />} />
	  <Route path="/ai-novel" element={<AINovelPage />} />
	  <Route path="/ai_chat" element={<AiChatPage />} />
	  <Route path="/ai_chat/girlfriend" element={<AiChatPage />} />
	  <Route path="/ai_chat/boyfriend" element={<AiChatPage />} />
	  <Route path="/ai_chat/lp" element={<AiChatLPPage />} />
	  <Route path="/ai_chat/howto" element={<AiChatHowToPage />} />
	  <Route path="/ai_chat/public" element={<AiChatPublicPage />} />
	  <Route path="/ai_chat/public/:characterId" element={<AiChatPublicPage />} />
	  <Route path="/ai_chat/public/:characterId/:slug" element={<AiChatPublicPage />} />
	  <Route path="/ai-logs" element={<AiLogsPage />} />
          <Route path="/episodes/:id/edit" element={<EditEpisode />} />
          <Route path="/episodes/:id" element={<EpisodeDetail />} />
          <Route path="/stripe/cancel" element={<StripeReturn mode="cancel" />} />
          <Route
            path="/stripe/success"
            element={<StripeReturn mode="success" />}
          />
          <Route
            path="/support/success"
            element={
              <SupportReturn
                mode="success"
                label={t(HEADER_I18N.support)}
              />
            }
          />
          <Route
            path="/support/cancel"
            element={
              <SupportReturn
                mode="cancel"
                label={t(HEADER_I18N.support)}
              />
            }
          />
          <Route
            path="/membership/success"
            element={
              <SupportReturn
                mode="success"
                label={t(HEADER_I18N.monthlySupport)}
              />
            }
          />
          <Route
            path="/membership/cancel"
            element={
              <SupportReturn
                mode="cancel"
                label={t(HEADER_I18N.monthlySupport)}
              />
            }
          />
        </Routes>
      </main>

      {!isAuthorsPage && (
        <footer
          style={{
            padding: "16px",
            borderTop: "1px solid #eee",
            display: "flex",
            justifyContent: "center",
            flexDirection: "column",
            alignItems: "center",
            gap: 8,
          }}
        >
          <Link className="btn btn-border" to="/contact" style={{ position: "relative", zIndex: 10 }}>
            {t(HEADER_I18N.contact)}
          </Link>
          <Link className="btn btn-border" to="/admin" style={{ position: "relative", zIndex: 10 }}>
            {t(HEADER_I18N.admin)}
          </Link>
        </footer>
      )}
    </div>
  );
}
