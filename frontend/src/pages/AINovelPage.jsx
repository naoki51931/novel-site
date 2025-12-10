// frontend/src/pages/AINovelPage.jsx
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

/**
 * 既存プロジェクトで JWT をどこに保存しているかに合わせてここを調整する
 * 例:
 * - localStorage.getItem("token")
 * - localStorage.getItem("access_token")
 * - cookie など
 */
function getAuthToken() {
  return localStorage.getItem("access_token") || localStorage.getItem("token");
}

export default function AINovelPage() {
  const [titleHint, setTitleHint] = useState("");
  const [genre, setGenre] = useState("");
  const [characters, setCharacters] = useState("");
  const [tone, setTone] = useState("");
  const [length, setLength] = useState("medium");
  const [model, setModel] = useState("gpt-4.1-mini");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [quotaError, setQuotaError] = useState("");
  const [premiumError, setPremiumError] = useState("");
  const [result, setResult] = useState(null);

  const navigate = useNavigate();

  const handleGenerate = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setQuotaError("");
    setPremiumError("");
    setResult(null);

    const token = getAuthToken();
    if (!token) {
      setError("ログインが必要です。ログイン画面へ移動します。");
      setTimeout(() => {
        navigate("/login"); // 既存のログインパスに合わせて変更
      }, 800);
      setLoading(false);
      return;
    }

    try {
      const res = await fetch("/api/ai/novels/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          title_hint: titleHint || null,
          genre: genre || null,
          characters: characters || null,
          tone: tone || null,
          length: length || "medium",
        }),
      });

      if (res.status === 401) {
        setError("ログインの有効期限が切れています。再ログインしてください。");
        setTimeout(() => navigate("/login"), 800);
        setLoading(false);
        return;
      }

      if (res.status === 402) {
        setPremiumError("この機能は有料プラン専用です。マイページからプランをご確認ください。");
        setLoading(false);
        return;
      }

      if (res.status === 429) {
        const data = await res.json().catch(() => ({}));
        setQuotaError(
          data.detail || "本日の AI 小説生成の上限回数に達しました。明日またお試しください。"
        );
        setLoading(false);
        return;
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `生成に失敗しました (status=${res.status})`);
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      console.error(err);
      setError(err.message || "生成中にエラーが発生しました。");
    } finally {
      setLoading(false);
    }
  };

  const handleCopyToClipboard = async () => {
    if (!result) return;
    const text = `${result.generated_title}\n\n${result.body}`;
    try {
      await navigator.clipboard.writeText(text);
      alert("クリップボードにコピーしました。");
    } catch (e) {
      alert("コピーに失敗しました。手動で選択してコピーしてください。");
    }
  };

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto", padding: "1.5rem" }}>
      <h1 style={{ fontSize: "1.8rem", marginBottom: "1rem" }}>AI小説生成（有料会員専用）</h1>

      <p style={{ marginBottom: "1.5rem", color: "#555" }}>
        お題や登場人物を入力して、「AI小説を生成する」を押すとお試し小説を生成します。
        <br />
        生成結果は後から自分で編集して、小説やエピソードとして投稿してもOKです。
      </p>

      <form
        onSubmit={handleGenerate}
        style={{
          display: "grid",
          gap: "0.75rem",
          marginBottom: "1.5rem",
          padding: "1rem",
          border: "1px solid #ddd",
          borderRadius: "8px",
        }}
      >
        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
            タイトルのイメージ（任意）
          </label>
          <input
            type="text"
            value={titleHint}
            onChange={(e) => setTitleHint(e.target.value)}
            placeholder="例: 月夜の喫茶店で始まる物語"
            style={{ width: "100%", padding: "0.5rem" }}
          />
        </div>

        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
            ジャンル（任意）
          </label>
          <input
            type="text"
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
            placeholder="例: ファンタジー / 日常 / SF / ラブコメ"
            style={{ width: "100%", padding: "0.5rem" }}
          />
        </div>

        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
            登場人物・設定
          </label>
          <textarea
            value={characters}
            onChange={(e) => setCharacters(e.target.value)}
            rows={3}
            placeholder="例: 大学生の主人公と、不思議な店主がいる深夜の喫茶店。主人公は最近よく見る夢の話を打ち明ける。"
            style={{ width: "100%", padding: "0.5rem", resize: "vertical" }}
          />
        </div>

        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
            雰囲気・トーン（任意）
          </label>
          <input
            type="text"
            value={tone}
            onChange={(e) => setTone(e.target.value)}
            placeholder="例: ほのぼの / 少し切ない / ダーク寄り など"
            style={{ width: "100%", padding: "0.5rem" }}
          />
        </div>

        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
            長さ
          </label>
          <select
            value={length}
            onChange={(e) => setLength(e.target.value)}
            style={{ width: "100%", padding: "0.5rem" }}
          >
            <option value="short">短め（800〜1200文字程度）</option>
            <option value="medium">ふつう（2000〜3000文字程度）</option>
            <option value="long">長め（4000〜6000文字程度）</option>
          </select>
        </div>
        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
            使用モデル
          </label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            style={{ width: "100%", padding: "0.5rem" }}
          >
            <option value="gpt-4.1-mini">GPT-4.1 Mini（高速・低コスト）</option>
            <option value="gpt-4.1">GPT-4.1（高品質）</option>
            <option value="gpt-4.1-preview">GPT-4.1 Preview（長文向け）</option>
            <option value="gpt-4o-mini">GPT-4o Mini</option>
            <option value="gpt-4o">GPT-4o</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{
            marginTop: "0.5rem",
            padding: "0.7rem 1.2rem",
            fontWeight: "bold",
            borderRadius: "6px",
            border: "none",
            cursor: loading ? "default" : "pointer",
            opacity: loading ? 0.7 : 1,
          }}
        >
          {loading ? "生成中..." : "AI小説を生成する"}
        </button>
	<button
          type="button"
          className="btn btn-border"
          onClick={() => navigate("/ai-logs")}
        >
          利用履歴を見る
        </button>

      </form>

      {premiumError && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            backgroundColor: "#fff5f5",
            border: "1px solid #f5c2c7",
            borderRadius: "6px",
            color: "#842029",
          }}
        >
          {premiumError}
        </div>
      )}

      {quotaError && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            backgroundColor: "#fff8e1",
            border: "1px solid #ffecb5",
            borderRadius: "6px",
            color: "#8a6d3b",
          }}
        >
          {quotaError}
        </div>
      )}

      {error && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            backgroundColor: "#f8d7da",
            border: "1px solid #f5c2c7",
            borderRadius: "6px",
            color: "#842029",
          }}
        >
          {error}
        </div>
      )}

      {result && (
        <div
          style={{
            marginTop: "1.5rem",
            padding: "1rem",
            border: "1px solid #ddd",
            borderRadius: "8px",
            backgroundColor: "#fafafa",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
            <h2 style={{ fontSize: "1.4rem", marginBottom: "0.5rem" }}>
              {result.generated_title || "生成された小説"}
            </h2>
            <button
              type="button"
              onClick={handleCopyToClipboard}
              style={{
                height: "2.2rem",
                alignSelf: "center",
                padding: "0.3rem 0.8rem",
                borderRadius: "4px",
                border: "1px solid #ccc",
                cursor: "pointer",
              }}
            >
              文章をコピー
            </button>
          </div>

          <div style={{ fontSize: "0.85rem", color: "#666", marginBottom: "0.5rem" }}>
            {result.model && <span>モデル: {result.model} / </span>}
            {typeof result.used_tokens === "number" && (
              <span>使用トークン: {result.used_tokens}</span>
            )}
          </div>

          <pre
            style={{
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              backgroundColor: "#fff",
              padding: "0.75rem",
              borderRadius: "6px",
              border: "1px solid #eee",
              maxHeight: "600px",
              overflowY: "auto",
            }}
          >
            {result.body}
          </pre>
        </div>
      )}
    </div>
  );
}

