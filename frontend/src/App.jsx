import React from "react";
import { useRoutes, Link } from "react-router-dom";

import Home from "./pages/Home";
import NewNovel from "./pages/NewNovel";
import NovelDetail from "./pages/NovelDetail";
import NewEpisode from "./pages/NewEpisode";
import EditNovel from "./pages/EditNovel";
import EditEpisode from "./pages/EditEpisode";

function AppRoutes() {
  const routes = useRoutes([
    { path: "/", element: <Home /> },
    { path: "/novels/new", element: <NewNovel /> },
    { path: "/novels/:id", element: <NovelDetail /> },
    { path: "/novels/:id/edit", element: <EditNovel /> },
    { path: "/novels/:id/episodes/new", element: <NewEpisode /> },
    { path: "/episodes/:id/edit", element: <EditEpisode /> },
    // 将来 Episode 単体表示を作るならここに追加: { path: "/episodes/:id", element: <EpisodeDetail /> },
  ]);

  return routes;
}

export default function App() {
  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: 16 }}>
      <header style={{ marginBottom: 16, display: "flex", gap: 8 }}>
        <Link
          to="/"
          className="btn btn-border site-title-link"
          data-discover="true"
        >
          小説投稿サイト
        </Link>
        <Link to="/novels/new" className="btn btn-border">
          新規小説投稿
        </Link>
      </header>

      <main>
        <AppRoutes />
      </main>
    </div>
  );
}
