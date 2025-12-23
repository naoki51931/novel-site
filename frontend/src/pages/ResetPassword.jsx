import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

const API_BASE = "";

export default function ResetPassword() {
  const location = useLocation();
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const urlToken = params.get("token");
    setToken(urlToken || "");
    setError("");
    setInfo("");
  }, [location.search]);

  const handleRequest = async (e) => {
    e.preventDefault();
    setError("");
    setInfo("");

    if (!email.trim()) {
      setError("メールアドレスを入力してください。");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/password-reset/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || "送信に失敗しました。");
      }
      setInfo("再設定用のリンクを送信しました。受信トレイをご確認ください。");
    } catch (err) {
      console.error(err);
      setError(err.message || "送信中にエラーが発生しました。");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (e) => {
    e.preventDefault();
    setError("");
    setInfo("");

    if (!newPassword.trim()) {
      setError("新しいパスワードを入力してください。");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("パスワードが一致しません。");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/password-reset/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || "再設定に失敗しました。");
      }
      setInfo("パスワードを更新しました。ログインしてください。");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      console.error(err);
      setError(err.message || "再設定中にエラーが発生しました。");
    } finally {
      setLoading(false);
    }
  };

  const isResetMode = !!token;

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/login">← ログインに戻る</Link>
      </div>

      <h2>パスワード再設定</h2>

      {!isResetMode && (
        <form onSubmit={handleRequest}>
          <div style={{ marginBottom: 8 }}>
            <label>
              登録メールアドレス
              <br />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{ width: "100%", padding: 4 }}
              />
            </label>
          </div>

          {error && (
            <p style={{ color: "red", marginTop: 4, marginBottom: 8 }}>{error}</p>
          )}
          {info && (
            <p style={{ color: "green", marginTop: 4, marginBottom: 8 }}>{info}</p>
          )}

          <button className="btn btn-border" type="submit" disabled={loading}>
            {loading ? "送信中..." : "再設定リンクを送信"}
          </button>
        </form>
      )}

      {isResetMode && (
        <form onSubmit={handleReset}>
          <div style={{ marginBottom: 8 }}>
            <label>
              新しいパスワード
              <br />
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                style={{ width: "100%", padding: 4 }}
              />
            </label>
          </div>

          <div style={{ marginBottom: 8 }}>
            <label>
              新しいパスワード（確認）
              <br />
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                style={{ width: "100%", padding: 4 }}
              />
            </label>
          </div>

          {error && (
            <p style={{ color: "red", marginTop: 4, marginBottom: 8 }}>{error}</p>
          )}
          {info && (
            <p style={{ color: "green", marginTop: 4, marginBottom: 8 }}>{info}</p>
          )}

          <button className="btn btn-border" type="submit" disabled={loading}>
            {loading ? "更新中..." : "パスワードを更新"}
          </button>
        </form>
      )}
    </div>
  );
}
