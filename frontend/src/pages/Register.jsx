import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";

const API_BASE = "";

export default function Register() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState(""); // ← 追加
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    try {
      const res = await fetch(API_BASE + "/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          email,      // ← email を送信
          password,
        }),
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

      navigate("/");

    } catch (e) {
      console.error(e);
      setError(e.message || "登録処理中にエラーが発生しました");
    }
  };

  return (
    <div className="register-container">
      <h2 className="register-title">ユーザー登録</h2>

      {error && <p className="register-error">{error}</p>}

      <form onSubmit={handleSubmit} className="register-form">

        <div className="form-group">
          <label>ユーザー名</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="input"
            required
          />
        </div>

        <div className="form-group">
          <label>メールアドレス</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input"
            required
          />
        </div>

        <div className="form-group">
          <label>パスワード</label>
          <input
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input"
            required
          />
          <label style={{ display: "block", fontSize: 12, marginTop: 6 }}>
            <input
              type="checkbox"
              checked={showPassword}
              onChange={(e) => setShowPassword(e.target.checked)}
              style={{ marginRight: 6 }}
            />
            パスワードを表示
          </label>
        </div>

        <button type="submit" className="btn-primary">
          登録する
        </button>
      </form>

      <div className="register-footer">
        すでにアカウントをお持ちですか？{" "}
        <Link to="/login">ログインはこちら</Link>
      </div>
    </div>
  );
}
