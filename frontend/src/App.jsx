import { Routes, Route, Link } from "react-router-dom";
import Home from "./pages/Home";
import NewNovel from "./pages/NewNovel";
import NovelDetail from "./pages/NovelDetail";
import NewEpisode from "./pages/NewEpisode";
import EditNovel from "./pages/EditNovel";
import EditEpisode from "./pages/EditEpisode";
import EpisodeDetail from "./pages/EpisodeDetail";
import Login from "./pages/Login";

export default function App() {
  const username = typeof window !== "undefined"
    ? localStorage.getItem("username")
    : null;
  const hasToken = typeof window !== "undefined"
    ? !!localStorage.getItem("token")
    : false;

  return (
    <div>
      <header
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid #ddd",
          marginBottom: 16,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 8,
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: 24 }}>小説投稿サイト</h1>
          <nav style={{ marginTop: 8 }}>
            <Link to="/" style={{ marginRight: 12 }}>
              トップ
            </Link>
            <Link to="/novels/new" style={{ marginRight: 12 }}>
              新規小説投稿
            </Link>
            <Link to="/login">ログイン</Link>
          </nav>
        </div>
        <div style={{ fontSize: 12, color: "#555", textAlign: "right" }}>
          {hasToken ? (
            <span>ログイン中: {username || "ユーザー"}</span>
          ) : (
            <span>未ログイン</span>
          )}
        </div>
      </header>

      <main style={{ padding: "0 16px 32px" }}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/novels/new" element={<NewNovel />} />
          <Route path="/novels/:id" element={<NovelDetail />} />
          <Route path="/novels/:id/edit" element={<EditNovel />} />
          <Route path="/novels/:id/episodes/new" element={<NewEpisode />} />
          <Route path="/episodes/:id/edit" element={<EditEpisode />} />
          <Route path="/episodes/:id" element={<EpisodeDetail />} />
        </Routes>
      </main>
    </div>
  );
}
