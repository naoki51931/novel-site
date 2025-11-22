import { Routes, Route, Link } from "react-router-dom";
import Home from "./pages/Home";
import NovelDetail from "./pages/NovelDetail";
import NewNovel from "./pages/NewNovel";
import NewEpisode from "./pages/NewEpisode";

export default function App() {
  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: "16px" }}>
      <header>
        <h1>
          <Link to="/" style={{ textDecoration: "none", color: "inherit" }}>
            小説投稿サイト
          </Link>
        </h1>
        <nav style={{ marginBottom: "12px" }}>
          <Link to="/" style={{ marginRight: "12px" }}>
            トップ
          </Link>
          <Link to="/novels/new">新規小説投稿</Link>
        </nav>
        <hr />
      </header>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/novels/new" element={<NewNovel />} />
        <Route path="/novels/:id" element={<NovelDetail />} />
        <Route path="/novels/:id/episodes/new" element={<NewEpisode />} />
      </Routes>
    </div>
  );
}
