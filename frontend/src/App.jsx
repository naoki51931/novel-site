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


export default function App() {
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const POST_LOGIN_REDIRECT_KEY = "post_login_redirect_v1";
  const LOGIN_CHECK_INTERVAL_MS = 10 * 60 * 1000;

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    setQuery(params.get("q") ?? "");
  }, [location.search]);

  useEffect(() => {
    const isLoginRoute = () => {
      const path = location.pathname;
      return (
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

  return (
    <div>
      <header className="site-header">
        <div className="site-header-left">
          <h1 className="site-title">小説投稿サイト</h1>
        </div>

        {/* スマホ用ハンバーガー */}
        <button
          type="button"
          className={`nav-toggle ${menuOpen ? "nav-toggle-open" : ""}`}
          onClick={() => setMenuOpen((v) => !v)}
          aria-label="メニューを開く"
        >
          <span />
          <span />
          <span />
        </button>

        {/* ナビゲーション */}
        <nav className={`nav-links ${menuOpen ? "nav-open" : ""}`}>
          <Link to="/" className="nav-link" onClick={() => setMenuOpen(false)}>
            トップ
          </Link>
          <Link
            to="/novels/new"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            新規小説投稿
          </Link>
          <Link
            to="/mypage"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            マイページ
          </Link>
          <Link
            to="/login"
            className="nav-link"
            onClick={() => setMenuOpen(false)}
          >
            ログイン
          </Link>
          <Link
            to="/register"
            className="nav-link nav-link-accent"
            onClick={() => setMenuOpen(false)}
          >
            Register
          </Link>
        </nav>

        <div className="login-status">
          {hasToken ? (
            <span>
              ログイン中:{" "}
              {username ? (
                <Link
                  className="user-link"
                  to={`/users/${encodeURIComponent(username)}`}
                >
                  {username}
                </Link>
              ) : (
                "ユーザー"
              )}
            </span>
          ) : (
            <span>未ログイン</span>
          )}
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
          <Route path="/login" element={<Login />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/oauth/callback" element={<OAuthCallback />} />
          <Route path="/register" element={<Register />} />
          <Route path="/mypage" element={<Mypage />} />
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
        </Routes>
      </main>
    </div>
  );
}
