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
    CORSMiddleware,
    allow_origins=["*"],  # 本番ではドメインを絞る
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== 小説一覧・作成・取得 =====

@app.get("/api/novels", response_model=List[schemas.Novel])
def list_novels(db: Session = Depends(get_db)):
    novels = db.query(models.Novel).all()
    return novels


@app.post("/api/novels", response_model=schemas.Novel)
def create_novel(novel: schemas.NovelCreate, db: Session = Depends(get_db)):
    # TODO: JWTからuser_idを取る。暫定で1固定
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
    # relationship で episodes も一緒に返る
    return novel


# ===== エピソード作成・一覧 =====

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


@app.get(
    "/api/novels/{novel_id}/episodes",
    response_model=List[schemas.Episode],
)
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
PYEOF

echo "🧠 Updating frontend/src/App.jsx ..."
cat <<'JSEOF' > frontend/src/App.jsx
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
JSEOF

echo "🧠 Updating frontend/src/pages/Home.jsx ..."
cat <<'JSEOF' > frontend/src/pages/Home.jsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function Home() {
  const [novels, setNovels] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/novels`)
      .then((res) => res.json())
      .then(setNovels)
      .catch(console.error);
  }, []);

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString("ja-JP");
  };

  return (
    <div>
      <h2>新着小説</h2>
      {novels.length === 0 && <p>まだ小説が投稿されていません。</p>}
      <div>
        {novels.map((n) => {
          const episodeCount = n.episodes ? n.episodes.length : 0;
          return (
            <div
              key={n.id}
              style={{
                border: "1px solid #ccc",
                borderRadius: 8,
                padding: 12,
                marginBottom: 12,
              }}
            >
              <h3 style={{ margin: "0 0 4px" }}>
                <Link to={`/novels/${n.id}`}>{n.title}</Link>
              </h3>
              {n.description && (
                <p style={{ margin: "0 0 4px", whiteSpace: "pre-wrap" }}>
                  {n.description}
                </p>
              )}
              <div style={{ fontSize: 12, color: "#555" }}>
                <div>作者: demo</div>
                <div>エピソード数: {episodeCount}</div>
                <div>投稿日時: {formatDateTime(n.created_at)}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
JSEOF

echo "🧠 Updating frontend/src/pages/NovelDetail.jsx ..."
cat <<'JSEOF' > frontend/src/pages/NovelDetail.jsx
import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function NovelDetail() {
  const { id } = useParams();
  const [novel, setNovel] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/novels/${id}`)
      .then((res) => {
        if (!res.ok) throw new Error("Not found");
        return res.json();
      })
      .then((data) => {
        const episodes = (data.episodes || []).slice().sort((a, b) => {
          return (a.episode_number || 0) - (b.episode_number || 0);
        });
        setNovel({ ...data, episodes });
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  const formatDateTime = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleString("ja-JP");
  };

  if (loading) return <p>読み込み中...</p>;
  if (!novel) return <p>小説が見つかりませんでした。</p>;

  const episodes = novel.episodes || [];

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← 一覧に戻る</Link>
      </div>
      <h2>{novel.title}</h2>
      {novel.description && (
        <p style={{ whiteSpace: "pre-wrap" }}>{novel.description}</p>
      )}
      <div style={{ fontSize: 12, color: "#555", marginBottom: 12 }}>
        <div>作者: demo</div>
        <div>作成日時: {formatDateTime(novel.created_at)}</div>
      </div>

      <button
        onClick={() => navigate(`/novels/${id}/episodes/new`)}
        style={{ marginBottom: 16 }}
      >
        この小説にエピソードを追加
      </button>

      <h3>エピソード一覧</h3>
      {episodes.length === 0 && <p>まだエピソードがありません。</p>}
      <ul style={{ listStyle: "none", paddingLeft: 0 }}>
        {episodes.map((ep) => (
          <li
            key={ep.id}
            style={{
              border: "1px solid #ddd",
              borderRadius: 6,
              padding: 8,
              marginBottom: 8,
            }}
          >
            <strong>
              第{ep.episode_number}話 {ep.title}
            </strong>
            <div style={{ fontSize: 12, color: "#555", marginBottom: 4 }}>
              投稿日時: {formatDateTime(ep.created_at)}
            </div>
            <div style={{ whiteSpace: "pre-wrap" }}>{ep.body}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}
JSEOF

echo "🧠 Updating frontend/src/pages/NewNovel.jsx ..."
cat <<'JSEOF' > frontend/src/pages/NewNovel.jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function NewNovel() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!title.trim()) {
      setError("タイトルは必須です。");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/novels`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title,
          description: description || null,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "投稿に失敗しました");
      }

      const novel = await res.json();
      navigate(`/novels/${novel.id}`);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>新しい小説を投稿</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            タイトル（必須）
            <br />
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>
            説明・あらすじ（任意）
            <br />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? "投稿中..." : "投稿する"}
        </button>
      </form>
    </div>
  );
}
JSEOF

echo "🧠 Creating frontend/src/pages/NewEpisode.jsx ..."
cat <<'JSEOF' > frontend/src/pages/NewEpisode.jsx
import { useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";

const API_BASE = "http://18.169.218.56";

export default function NewEpisode() {
  const { id } = useParams(); // novel_id
  const [episodeNumber, setEpisodeNumber] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!episodeNumber || isNaN(Number(episodeNumber))) {
      setError("話数は数字で入力してください。");
      return;
    }
    if (!title.trim()) {
      setError("タイトルは必須です。");
      return;
    }
    if (!body.trim()) {
      setError("本文は必須です。");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/novels/${id}/episodes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          episode_number: Number(episodeNumber),
          title,
          body,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "エピソード投稿に失敗しました");
      }

      await res.json();
      navigate(`/novels/${id}`);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to={`/novels/${id}`}>← 小説詳細に戻る</Link>
      </div>
      <h2>エピソードを追加</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            話数（例: 1, 2, 3）
            <br />
            <input
              type="number"
              value={episodeNumber}
              onChange={(e) => setEpisodeNumber(e.target.value)}
              style={{ width: "100%", padding: 4 }}
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
              style={{ width: "100%", padding: 4 }}
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
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? "投稿中..." : "投稿する"}
        </button>
      </form>
    </div>
  );
}
JSEOF

echo "✅ Source files updated."
echo "次のコマンドでビルド & 再起動してください:"
echo "  cd ~/novel-site/frontend && npm run build"
echo "  cd ~/novel-site && docker compose down && docker compose up --build -d"

