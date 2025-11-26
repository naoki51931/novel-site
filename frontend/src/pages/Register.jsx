import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";

const API_BASE = "";

export default function Register() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch(API_BASE + "/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        let msg = "ユーザー登録に失敗しました";
        try {
          const data = await res.json();
          if (data?.detail) msg = data.detail;
        } catch {}
        throw new Error(msg);
      }
      const data = await res.json();
      if (data.access_token) {
        localStorage.setItem("token", data.access_token);
      }
      navigate("/"); // トップへ
    } catch (e) {
      console.error(e);
      setError(e.message || "登録処理中にエラーが発生しました");
    }
  };

  return (
    <div>
      <h2>ユーザー登録</h2>
      {error && <p style={{ color: "red" }}>{error}</p>}

      <form onSubmit={handleSubmit} style={{ maxWidth: 400 }}>
        <div style={{ marginBottom: 12 }}>
          <label>
            ユーザー名
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="input"
            />
          </label>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label>
            パスワード
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input"
            />
          </label>
        </div>
        <button type="submit" className="btn btn-primary">
          登録する
        </button>
      </form>

      <div style={{ marginTop: 16 }}>
        すでにアカウントをお持ちですか？{" "}
        <Link to="/login">ログインはこちら</Link>
      </div>
    </div>
  );
}
