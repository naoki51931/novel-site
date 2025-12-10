// frontend/src/App.jsx
import AccountSettings from "./pages/AccountSettings";
import Register from "./pages/Register.jsx";
import { useState } from "react";
import SearchBar from "./components/SearchBar.jsx";
import { Routes, Route, Link } from "react-router-dom";
import Home from "./pages/Home";
import NewNovel from "./pages/NewNovel";
import NovelDetail from "./pages/NovelDetail";
import NewEpisode from "./pages/NewEpisode";
import EditNovel from "./pages/EditNovel";
import EditEpisode from "./pages/EditEpisode";
import EpisodeDetail from "./pages/EpisodeDetail";
import StripeReturn from "./pages/StripeReturn";
import Login from "./pages/Login";
import Mypage from "./pages/Mypage";
import AINovelPage from "./pages/AINovelPage";
import AiLogsPage from "./pages/AiLogsPage";


export default function App() {
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);

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
            <span>ログイン中: {username || "ユーザー"}</span>
          ) : (
            <span>未ログイン</span>
          )}
        </div>
      </header>

      {/* 検索バーはヘッダーの下に固定 */}
      <SearchBar q={q} tag={tag} onChangeQ={setQ} onChangeTag={setTag} />

      <main style={{ padding: "0 16px 32px" }}>
        <Routes>
        <Route path="/mypage/settings" element={<AccountSettings />} />
          <Route path="/" element={<Home q={q} tag={tag} />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/mypage" element={<Mypage />} />
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

