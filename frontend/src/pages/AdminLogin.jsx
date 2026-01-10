import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";
import { useI18n } from "../lib/i18n";

export default function AdminLogin() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      setError("");
      await apiFetch("/api/admin/auth/login", {
        method: "POST",
        body: { username, password },
        credentials: "include",
      });
      navigate("/admin/payouts", { replace: true });
    } catch (e2) {
      setError(e2.message || t({ ja: "ログインに失敗しました", en: "Login failed." }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 420, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 16 }}>{t({ ja: "管理者ログイン", en: "Admin Login" })}</h2>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <form onSubmit={handleSubmit} style={{ display: "grid", gap: 10 }}>
        <label>
          {t({ ja: "ユーザー名", en: "Username" })}
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <div>
          <label>
            {t({ ja: "パスワード", en: "Password" })}
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <div style={{ fontSize: 12, marginTop: 6 }}>
            <label>
              <input
                type="checkbox"
                checked={showPassword}
                onChange={(e) => setShowPassword(e.target.checked)}
                style={{ marginRight: 6 }}
              />
              {t({ ja: "パスワードを表示", en: "Show password" })}
            </label>
          </div>
        </div>
        <button type="submit" className="btn btn-border" disabled={loading}>
          {loading ? t({ ja: "ログイン中...", en: "Logging in..." }) : t({ ja: "ログイン", en: "Login" })}
        </button>
      </form>
    </div>
  );
}
