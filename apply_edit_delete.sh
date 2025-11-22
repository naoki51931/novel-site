#!/usr/bin/env bash
set -e

cd ~/novel-site

echo "🧠 Updating backend/app/main.py ..."
cat <<'PYEOF' > backend/app/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from .database import Base, engine, get_db
from . import models, schemas

# テーブル作成
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Novel Site API")

app.add_middleware(
    CORSMiddleware(
        allow_origins=["*"],  # 本番ではドメインを絞る
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
)

# ===== 小説一覧・作成・取得 =====

@app.get("/api/novels", response_model=List[schemas.Novel])
def list_novels(db: Session = Depends(get_db)):
    novels = db.query(models.Novel).all()
    return novels


@app.post("/api/novels", response_model=schemas.Novel)
def create_novel(novel: schemas.NovelCreate, db: Session = Depends(get_db)):
    # 認証は未実装なので author_id は暫定1固定（あとでJWT連携）
    author_id = 1
    db_novel = models.Novel(
        title=novel.title,
        description=novel.description,
        author_id=author_id,
    )
    db.add(db_novel)
    db.commit()
    db.refresh(db_novel)
    return db_novel


@app.get("/api/novels/{novel_id}", response_model=schemas.Novel)
def get_novel(novel_id: int, db: Session = Depends(get_db)):
    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    return novel


@app.put("/api/novels/{novel_id}", response_model=schemas.Novel)
def update_novel(
    novel_id: int,
    novel_in: schemas.NovelUpdate,
    db: Session = Depends(get_db),
):
    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    if novel_in.title is not None:
        novel.title = novel_in.title
    if novel_in.description is not None:
        novel.description = novel_in.description

    db.commit()
    db.refresh(novel)
    return novel


@app.delete("/api/novels/{novel_id}", status_code=204)
def delete_novel(novel_id: int, db: Session = Depends(get_db)):
    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    db.delete(novel)
    db.commit()
    return


# ===== エピソード作成・取得・編集・削除 =====

@app.post("/api/novels/{novel_id}/episodes", response_model=schemas.Episode)
def create_episode(
    novel_id: int,
    episode: schemas.EpisodeCreate,
    db: Session = Depends(get_db),
):
    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    db_ep = models.Episode(
        novel_id=novel_id,
        title=episode.title,
        body=episode.body,
        episode_number=episode.episode_number,
    )
    db.add(db_ep)
    db.commit()
    db.refresh(db_ep)
    return db_ep


@app.get("/api/novels/{novel_id}/episodes", response_model=List[schemas.Episode])
def list_episodes(novel_id: int, db: Session = Depends(get_db)):
    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    episodes = (
        db.query(models.Episode)
        .filter(models.Episode.novel_id == novel_id)
        .order_by(models.Episode.episode_number)
        .all()
    )
    return episodes


@app.get("/api/episodes/{episode_id}", response_model=schemas.Episode)
def get_episode(episode_id: int, db: Session = Depends(get_db)):
    ep = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    return ep


@app.put("/api/episodes/{episode_id}", response_model=schemas.Episode)
def update_episode(
    episode_id: int,
    ep_in: schemas.EpisodeUpdate,
    db: Session = Depends(get_db),
):
    ep = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")

    if ep_in.episode_number is not None:
        ep.episode_number = ep_in.episode_number
    if ep_in.title is not None:
        ep.title = ep_in.title
    if ep_in.body is not None:
        ep.body = ep_in.body

    db.commit()
    db.refresh(ep)
    return ep


@app.delete("/api/episodes/{episode_id}", status_code=204)
def delete_episode(episode_id: int, db: Session = Depends(get_db)):
    ep = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")

    db.delete(ep)
    db.commit()
    return
PYEOF

echo "🧠 Updating frontend/src/App.jsx ..."
cat <<'JSEOF' > frontend/src/App.jsx
import { Routes, Route, Link } from "react-router-dom";
import Home from "./pages/Home";
import NovelDetail from "./pages/NovelDetail";
import NewNovel from "./pages/NewNovel";
import NewEpisode from "./pages/NewEpisode";
import EditNovel from "./pages/EditNovel";
import EditEpisode from "./pages/EditEpisode";

export default function App() {
  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "16px" }}>
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
        <Route path="/novels/:id/edit" element={<EditNovel />} />
        <Route path="/novels/:id/episodes/new" element={<NewEpisode />} />
        <Route path="/episodes/:episodeId/edit" element={<EditEpisode />} />
      </Routes>
    </div>
  );
}
JSEOF

echo "🧠 Creating frontend/src/pages/EditNovel.jsx ..."
cat <<'JSEOF' > frontend/src/pages/EditNovel.jsx
import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function EditNovel() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const run = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/novels/${id}`);
        if (!res.ok) throw new Error("小説の取得に失敗しました");
        const data = await res.json();
        setTitle(data.title);
        setDescription(data.description || "");
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [id]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/novels/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, description }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "更新に失敗しました");
      }
      navigate(`/novels/${id}`);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("この小説を削除しますか？（エピソードも削除されます）")) return;
    try {
      const res = await fetch(`${API_BASE}/api/novels/${id}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "削除に失敗しました");
      }
      navigate("/");
    } catch (e) {
      setError(String(e));
    }
  };

  if (loading) return <p>読み込み中...</p>;

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to={`/novels/${id}`}>← 小説詳細に戻る</Link>
      </div>
      <h2>小説を編集</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            タイトル
            <br />
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={{ width: "100%" }}
            />
          </label>
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>
            説明
            <br />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
              style={{ width: "100%" }}
            />
          </label>
        </div>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit" className="btn btn-border">
          更新する
        </button>
        <button
          type="button"
          className="btn btn-border"
          style={{ marginLeft: 8 }}
          onClick={handleDelete}
        >
          削除する
        </button>
      </form>
    </div>
  );
}
JSEOF

echo "🧠 Creating frontend/src/pages/EditEpisode.jsx ..."
cat <<'JSEOF' > frontend/src/pages/EditEpisode.jsx
import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function EditEpisode() {
  const { episodeId } = useParams();
  const navigate = useNavigate();
  const [novelId, setNovelId] = useState(null);
  const [episodeNumber, setEpisodeNumber] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const run = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/episodes/${episodeId}`);
        if (!res.ok) throw new Error("エピソードの取得に失敗しました");
        const data = await res.json();
        setNovelId(data.novel_id);
        setEpisodeNumber(data.episode_number);
        setTitle(data.title);
        setBody(data.body);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [episodeId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/episodes/${episodeId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          episode_number: Number(episodeNumber),
          title,
          body,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "更新に失敗しました");
      }
      navigate(`/novels/${novelId}`);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("このエピソードを削除しますか？")) return;
    try {
      const res = await fetch(`${API_BASE}/api/episodes/${episodeId}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "削除に失敗しました");
      }
      if (novelId) {
        navigate(`/novels/${novelId}`);
      } else {
        navigate("/");
      }
    } catch (e) {
      setError(String(e));
    }
  };

  if (loading) return <p>読み込み中...</p>;

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        {novelId && <Link to={`/novels/${novelId}`}>← 小説詳細に戻る</Link>}
      </div>
      <h2>エピソードを編集</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            話数
            <br />
            <input
              type="number"
              value={episodeNumber}
              onChange={(e) => setEpisodeNumber(e.target.value)}
            />
          </label>
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>
            タイトル
            <br />
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={{ width: "100%" }}
            />
          </label>
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>
            本文
            <br />
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={10}
              style={{ width: "100%" }}
            />
          </label>
        </div>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit" className="btn btn-border">
          更新する
        </button>
        <button
          type="button"
          className="btn btn-border"
          style={{ marginLeft: 8 }}
          onClick={handleDelete}
        >
          削除する
        </button>
      </form>
    </div>
  );
}
JSEOF

echo "✅ edit/delete 機能のソース更新が完了しました。"
echo "次のコマンドでビルド & 再起動してください:"
echo "  cd ~/novel-site/frontend && npm run build"
echo "  cd ~/novel-site && docker compose down && docker compose up --build -d"

