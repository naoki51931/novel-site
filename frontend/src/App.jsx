// frontend/src/App.jsx
import AccountSettings from "./pages/AccountSettings";
import Register from "./pages/Register.jsx";
import { useEffect, useState } from "react";
import SearchBar from "./components/SearchBar.jsx";
import { Routes, Route, Link, useLocation, useNavigate } from "react-router-dom";
import Home from "./pages/Home";
import NewNovel from "./pages/NewNovel";
import NovelDetail from "./pages/NovelDetail";
import NewEpisode from "./pages/NewEpisode";
import EditNovel from "./pages/EditNovel";
import EditEpisode from "./pages/EditEpisode";
import EpisodeDetail from "./pages/EpisodeDetail";
import StripeReturn from "./pages/StripeReturn";
import Login from "./pages/Login";
import OAuthCallback from "./pages/OAuthCallback";
import Mypage from "./pages/Mypage";
import UserPage from "./pages/UserPage";
import AINovelPage from "./pages/AINovelPage";
import AiLogsPage from "./pages/AiLogsPage";
import DirectMessageThread from "./pages/DirectMessageThread";
import ResetPassword from "./pages/ResetPassword";
import CreatorDashboard from "./pages/CreatorDashboard";
import AdminHome from "./pages/AdminHome";
import AdminPayouts from "./pages/AdminPayouts";
import AdminLogin from "./pages/AdminLogin";
import AdminDashboard from "./pages/AdminDashboard";
import SupportReturn from "./pages/SupportReturn";
import SupportPlans from "./pages/SupportPlans";
import StripePriceIdManual from "./pages/StripePriceIdManual";
import Notifications from "./pages/Notifications";
import AuthorLanding from "./pages/AuthorLanding";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faBell } from "@fortawesome/free-regular-svg-icons";
import { trackPageView } from "./lib/analytics";
import { useI18n } from "./lib/i18n";


export default function App() {
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const navigate = useNavigate();
  const location = useLocation();
  const { t, lang, setLang } = useI18n();
  const POST_LOGIN_REDIRECT_KEY = "post_login_redirect_v1";
  const LOGIN_CHECK_INTERVAL_MS = 10 * 60 * 1000;

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    setQuery(params.get("q") ?? "");
  }, [location.search]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    trackPageView();
  }, [location.pathname, location.search, location.hash]);

  useEffect(() => {
    const isLoginRoute = () => {
      const path = location.pathname;
      return (
        path === "/" ||
        path === "/authors" ||
        path.startsWith("/ai-novel") ||
        path.startsWith("/novels/") ||
        path.startsWith("/episodes/") ||
        path.startsWith("/users/") ||
        path === "/login" ||
        path === "/register" ||
        path === "/reset-password" ||
        path === "/oauth/callback"
      );
    };

    const isTokenExpired = (token) => {
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
        typeof window !== "undefined" ? !!localStorage.getItem("token") : false;
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

  const username =
    typeof window !== "undefined" ? localStorage.getItem("username") : null;
  const hasToken =
    typeof window !== "undefined" ? !!localStorage.getItem("token") : false;

  useEffect(() => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null;
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

  return (
    <div>
      <header className={`site-header ${menuOpen ? "menu-open" : ""}`}>
        <div className="site-header-left">
          <h1 className="site-title">
            {t({ ja: "小説投稿サイト", en: "Novel Submission Site" })}
          </h1>
        </div>

        {/* ナビゲーション */}
        <nav className={`nav-links ${menuOpen ? "nav-open" : ""}`}>
          <Link to="/" className="nav-link" onClick={() => setMenuOpen(false)}>
            {t({ ja: "トップ", en: "Home" })}
          </Link>
          <Link
            to="/authors"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            {t({ ja: "作者向け", en: "For Authors" })}
          </Link>
          <Link
            to="/novels/new"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            {t({ ja: "新規小説投稿", en: "Post New Novel" })}
          </Link>
          <Link
            to="/mypage"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            {t({ ja: "マイページ", en: "My Page" })}
          </Link>
          <Link
            to="/login"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            {t({ ja: "ログイン", en: "Login" })}
          </Link>
          <Link
            to="/register"
            className="nav-link nav-link-accent"
            onClick={() => setMenuOpen(false)}
          >
            {t({ ja: "新規登録", en: "Register" })}
          </Link>
        </nav>

        <div className="header-right">
          <button
            type="button"
            className="lang-toggle btn btn-border"
            onClick={() => setLang(lang === "ja" ? "en" : "ja")}
            aria-label={t({ ja: "言語を切り替える", en: "Switch language" })}
            title={
              lang === "ja"
                ? t({ ja: "Englishへ切り替え", en: "Switch to English" })
                : t({ ja: "日本語へ切り替え", en: "Switch to Japanese" })
            }
          >
            {lang === "ja" ? "EN" : "JP"}
          </button>
          <div className="login-status">
            {hasToken ? (
              <span>
                {t({ ja: "ログイン中", en: "Logged in" })}:{" "}
                {username ? (
                  <Link
                    className="user-link"
                    to={`/users/${encodeURIComponent(username)}`}
                  >
                    {username}
                  </Link>
                ) : (
                  t({ ja: "ユーザー", en: "User" })
                )}
              </span>
            ) : (
              <span>{t({ ja: "未ログイン", en: "Not logged in" })}</span>
            )}
          </div>
          <Link
            to="/notifications"
            className="nav-bell"
            aria-label={t({ ja: "通知センター", en: "Notifications" })}
            title={t({ ja: "通知センター", en: "Notifications" })}
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
          <button
            type="button"
            className={`nav-toggle ${menuOpen ? "nav-toggle-open" : ""}`}
            onClick={() => setMenuOpen((v) => !v)}
            aria-label={t({ ja: "メニューを開く", en: "Open menu" })}
          >
            <span />
            <span />
            <span />
          </button>
        </div>
      </header>

      {/* 検索バーはヘッダーの下に固定 */}
      <SearchBar
        query={query}
        onChangeQuery={setQuery}
        onSearch={() => {
          setMenuOpen(false);
          const q = (query ?? "").trim();
          if (!q) {
            navigate("/");
            return;
          }
          const params = new URLSearchParams();
          params.set("q", q);
          navigate(`/?${params.toString()}`);
        }}
      />

      <main style={{ padding: "0 16px 32px" }}>
        <Routes>
          <Route path="/mypage/settings" element={<AccountSettings />} />
          <Route path="/" element={<Home query={query} />} />
          <Route path="/authors" element={<AuthorLanding />} />
          <Route path="/login" element={<Login />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/oauth/callback" element={<OAuthCallback />} />
          <Route path="/register" element={<Register />} />
          <Route path="/mypage" element={<Mypage />} />
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/me/creator" element={<CreatorDashboard />} />
          <Route path="/me/support-plans" element={<SupportPlans />} />
          <Route path="/me/support-plans/manual" element={<StripePriceIdManual />} />
          <Route path="/admin" element={<AdminHome />} />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/admin/payouts" element={<AdminPayouts />} />
          <Route path="/admin/dashboard" element={<AdminDashboard />} />
          <Route path="/users/:username" element={<UserPage />} />
          <Route path="/dms/:threadId" element={<DirectMessageThread />} />
          <Route path="/novels/new" element={<NewNovel />} />
          <Route path="/novels/:id" element={<NovelDetail />} />
          <Route path="/novels/:id/edit" element={<EditNovel />} />
          <Route path="/novels/:id/episodes/new" element={<NewEpisode />} />
	  <Route path="/ai-novel" element={<AINovelPage />} />
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
                label={t({ ja: "支援", en: "Support" })}
              />
            }
          />
          <Route
            path="/support/cancel"
            element={
              <SupportReturn
                mode="cancel"
                label={t({ ja: "支援", en: "Support" })}
              />
            }
          />
          <Route
            path="/membership/success"
            element={
              <SupportReturn
                mode="success"
                label={t({ ja: "月額支援", en: "Monthly Support" })}
              />
            }
          />
          <Route
            path="/membership/cancel"
            element={
              <SupportReturn
                mode="cancel"
                label={t({ ja: "月額支援", en: "Monthly Support" })}
              />
            }
          />
        </Routes>
      </main>

      <footer
        style={{
          padding: "16px",
          borderTop: "1px solid #eee",
          display: "flex",
          justifyContent: "center",
        }}
      >
        <Link className="btn btn-border" to="/admin">
          {t({ ja: "管理画面", en: "Admin" })}
        </Link>
      </footer>
    </div>
  );
}
