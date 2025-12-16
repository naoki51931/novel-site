import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";

const API_BASE = "";

export default function Login() {
  const navigate = useNavigate();

  const [step, setStep] = useState(1); // 1: ユーザー名+パスワード / 2: 6桁コード入力
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const savedUsername = localStorage.getItem("username");
  const hasToken = !!localStorage.getItem("token");

  // 1段階目: /api/auth/login/start
  const handleStart = async (e) => {
    e.preventDefault();
    setError("");
    setInfo("");

    if (!username.trim() || !password.trim()) {
      setError("ユーザー名とパスワードを入力してください。");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/login/start`, {
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

      // ここまで来たら 6桁コードが発行済み
      setStep(2);
      setInfo("認証コードをメールで送信しました。(SMTP未設定の場合はサーバーログに表示されます)");
    } catch (err) {
      console.error(err);
      setError(err.message || "ログイン中にエラーが発生しました。");
    } finally {
      setLoading(false);
    }
  };

  // 2段階目: /api/auth/login/verify
  const handleVerify = async (e) => {
    e.preventDefault();
    setError("");
    setInfo("");

    if (!code.trim()) {
      setError("認証コードを入力してください。");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/login/verify`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, code }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || "認証コードの検証に失敗しました。");
      }

      if (!data.access_token) {
        throw new Error("トークンの取得に失敗しました。");
      }

      // トークンとユーザー名を保存
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("username", username);

      navigate("/mypage");
    } catch (err) {
      console.error(err);
      setError(err.message || "認証中にエラーが発生しました。");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    navigate("/");
  };

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← トップに戻る</Link>
      </div>

      <h2>ログイン（二段階認証）</h2>

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

      {step === 1 && (
        <form onSubmit={handleStart}>
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
            <p style={{ color: "red", marginTop: 4, marginBottom: 8 }}>
              {error}
            </p>
          )}
          {info && (
            <p style={{ color: "green", marginTop: 4, marginBottom: 8 }}>
              {info}
            </p>
          )}

          <button className="btn btn-border" type="submit" disabled={loading}>
            {loading ? "送信中..." : "認証コードを送信"}
          </button>
        </form>
      )}

      {step === 2 && (
        <form onSubmit={handleVerify}>
          <div style={{ marginBottom: 8 }}>
            <p style={{ marginBottom: 4 }}>
              メールに届いた 6 桁の認証コードを入力してください。
              <br />
              ※ SMTP 未設定の場合は、サーバーログにコードが表示されます。
            </p>
            <label>
              認証コード（6桁）
              <br />
              <input
                type="text"
                value={code}
                maxLength={6}
                onChange={(e) => setCode(e.target.value)}
                style={{ width: "100%", padding: 4, letterSpacing: 2 }}
              />
            </label>
          </div>

          {error && (
            <p style={{ color: "red", marginTop: 4, marginBottom: 8 }}>
              {error}
            </p>
          )}
          {info && (
            <p style={{ color: "green", marginTop: 4, marginBottom: 8 }}>
              {info}
            </p>
          )}

          <button className="btn btn-border" type="submit" disabled={loading}>
            {loading ? "認証中..." : "ログイン"}
          </button>

          <div style={{ marginTop: 8, fontSize: 12 }}>
            <button
              type="button"
              style={{ textDecoration: "underline", border: "none", background: "none", padding: 0, cursor: "pointer" }}
              onClick={() => {
                // 1からやり直したいとき用
                setStep(1);
                setCode("");
                setInfo("");
                setError("");
              }}
            >
              ユーザー名・パスワード入力からやり直す
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
