import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";

const API_BASE = "";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!username.trim() || !password.trim()) {
      setError("ユーザー名とパスワードを入力してください。");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || "ログインに失敗しました。");
      }

      if (!data.access_token) {
        throw new Error("トークンの取得に失敗しました。");
      }

      // トークンを保存
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("username", username);

      // トップへ戻る
      navigate("/");
    } catch (err) {
      console.error(err);
      setError(err.message || "ログイン中にエラーが発生しました。");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    navigate("/");
  };

  const savedUsername = localStorage.getItem("username");
  const hasToken = !!localStorage.getItem("token");

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← トップに戻る</Link>
      </div>

      <h2>ログイン</h2>

      {hasToken && (
        <div
          style={{
            padding: 8,
            marginBottom: 12,
            border: "1px solid #ddd",
            borderRadius: 6,
            backgroundColor: "#f8f8f8",
            fontSize: 14,
          }}
        >
          <div>現在ログイン中: {savedUsername || "不明なユーザー"}</div>
          <button
            type="button"
            className="btn btn-border"
            style={{ marginTop: 8 }}
            onClick={handleLogout}
          >
            ログアウトする
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            ユーザー名
            <br />
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            パスワード
            <br />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: "100%", padding: 4 }}
            />
          </label>
        </div>

        {error && (
          <p style={{ color: "red", marginTop: 4, marginBottom: 8 }}>{error}</p>
        )}

        <button className="btn btn-border" type="submit" disabled={loading}>
          {loading ? "ログイン中..." : "ログイン"}
        </button>
      </form>
    </div>
  );
}
