import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useI18n } from "../lib/i18n";

const API_BASE = import.meta.env.VITE_BACKEND_ORIGIN || "https://shosetsu-toukou-site.org";

export default function ResetPassword() {
  const location = useLocation();
  const { t } = useI18n();
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
      setError(t({ ja: "メールアドレスを入力してください。", en: "Please enter your email." }));
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
        throw new Error(data.detail || t({ ja: "送信に失敗しました。", en: "Failed to send." }));
      }
      setInfo(
        t({
          ja: "再設定用のリンクを送信しました。受信トレイをご確認ください。",
          en: "We sent a reset link. Please check your inbox.",
        })
      );
    } catch (err) {
      console.error(err);
      setError(err.message || t({ ja: "送信中にエラーが発生しました。", en: "An error occurred while sending." }));
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (e) => {
    e.preventDefault();
    setError("");
    setInfo("");

    if (!newPassword.trim()) {
      setError(t({ ja: "新しいパスワードを入力してください。", en: "Please enter a new password." }));
      return;
    }
    if (newPassword !== confirmPassword) {
      setError(t({ ja: "パスワードが一致しません。", en: "Passwords do not match." }));
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
        throw new Error(data.detail || t({ ja: "再設定に失敗しました。", en: "Reset failed." }));
      }
      setInfo(
        t({ ja: "パスワードを更新しました。ログインしてください。", en: "Password updated. Please log in." })
      );
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      console.error(err);
      setError(err.message || t({ ja: "再設定中にエラーが発生しました。", en: "An error occurred during reset." }));
    } finally {
      setLoading(false);
    }
  };

  const isResetMode = !!token;

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/login">{t({ ja: "← ログインに戻る", en: "← Back to login" })}</Link>
      </div>

      <h2>{t({ ja: "パスワード再設定", en: "Reset Password" })}</h2>

      {!isResetMode && (
        <form onSubmit={handleRequest}>
          <div style={{ marginBottom: 8 }}>
            <label>
              {t({ ja: "登録メールアドレス", en: "Registered email" })}
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
            {loading ? t({ ja: "送信中...", en: "Sending..." }) : t({ ja: "再設定リンクを送信", en: "Send reset link" })}
          </button>
        </form>
      )}

      {isResetMode && (
        <form onSubmit={handleReset}>
          <div style={{ marginBottom: 8 }}>
            <label>
              {t({ ja: "新しいパスワード", en: "New password" })}
              <br />
              <input
                type={showPassword ? "text" : "password"}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                style={{ width: "100%", padding: 4 }}
              />
            </label>
          </div>

          <div style={{ marginBottom: 8 }}>
            <label>
              {t({ ja: "新しいパスワード（確認）", en: "Confirm new password" })}
              <br />
              <input
                type={showPassword ? "text" : "password"}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                style={{ width: "100%", padding: 4 }}
              />
            </label>
            <div style={{ marginTop: 6 }}>
              <label style={{ fontSize: 12 }}>
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

          {error && (
            <p style={{ color: "red", marginTop: 4, marginBottom: 8 }}>{error}</p>
          )}
          {info && (
            <p style={{ color: "green", marginTop: 4, marginBottom: 8 }}>{info}</p>
          )}

          <button className="btn btn-border" type="submit" disabled={loading}>
            {loading ? t({ ja: "更新中...", en: "Updating..." }) : t({ ja: "パスワードを更新", en: "Update password" })}
          </button>
        </form>
      )}
    </div>
  );
}
