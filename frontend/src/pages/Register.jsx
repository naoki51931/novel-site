import { useState } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { trackEvent } from "../lib/analytics";

const API_BASE = import.meta.env.VITE_BACKEND_ORIGIN || "https://shosetsu-toukou-site.org";

export default function Register() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState(""); // ← 追加
  const [emailCode, setEmailCode] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  const [codeSentMessage, setCodeSentMessage] = useState("");
  const [error, setError] = useState("");

  const handleSendCode = async () => {
    setError("");
    setCodeSentMessage("");
    try {
      setSendingCode(true);
      const res = await fetch(API_BASE + "/api/auth/register/email/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        let msg = t({ ja: "認証コード送信に失敗しました", en: "Failed to send verification code." });
        try {
          const data = await res.json();
          if (data?.detail) msg = data.detail;
        } catch {}
        throw new Error(msg);
      }
      setCodeSentMessage(
        t({
          ja: "認証コードをメール送信しました。受信した6桁コードを入力してください。",
          en: "Verification code sent. Enter the 6-digit code from your email.",
        })
      );
    } catch (e) {
      setError(
        e.message ||
          t({ ja: "認証コード送信中にエラーが発生しました", en: "An error occurred while sending code." })
      );
    } finally {
      setSendingCode(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setCodeSentMessage("");

    try {
      const res = await fetch(API_BASE + "/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          email,      // ← email を送信
          email_code: emailCode,
          password,
        }),
      });

      if (!res.ok) {
        let msg = t({ ja: "ユーザー登録に失敗しました", en: "Registration failed." });
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
      trackEvent("sign_up", {
        method: "email",
        page_path: location.pathname,
      });

      navigate("/");

    } catch (e) {
      console.error(e);
      setError(
        e.message ||
          t({ ja: "登録処理中にエラーが発生しました", en: "An error occurred during registration." })
      );
    }
  };

  return (
    <div className="register-container">
      <h2 className="register-title">{t({ ja: "ユーザー登録", en: "Register" })}</h2>

      {error && <p className="register-error">{error}</p>}

      <form onSubmit={handleSubmit} className="register-form">

        <div className="form-group">
          <label>{t({ ja: "ユーザー名", en: "Username" })}</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="input"
            required
          />
        </div>

        <div className="form-group">
          <label>{t({ ja: "メールアドレス", en: "Email" })}</label>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input"
              required
              style={{ flex: 1 }}
            />
            <button
              type="button"
              className="btn btn-border"
              onClick={handleSendCode}
              disabled={sendingCode || !email.trim()}
            >
              {sendingCode
                ? t({ ja: "送信中...", en: "Sending..." })
                : t({ ja: "認証コード送信", en: "Send code" })}
            </button>
          </div>
          {codeSentMessage && (
            <div style={{ color: "green", marginTop: 6, fontSize: 13 }}>{codeSentMessage}</div>
          )}
        </div>

        <div className="form-group">
          <label>{t({ ja: "メール認証コード", en: "Email verification code" })}</label>
          <input
            type="text"
            value={emailCode}
            onChange={(e) => setEmailCode(e.target.value)}
            className="input"
            required
            maxLength={6}
            placeholder={t({ ja: "6桁コード", en: "6-digit code" })}
          />
        </div>

        <div className="form-group">
          <label>{t({ ja: "パスワード", en: "Password" })}</label>
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
            {t({ ja: "パスワードを表示", en: "Show password" })}
          </label>
        </div>

        <button type="submit" className="btn-primary">
          {t({ ja: "登録する", en: "Register" })}
        </button>
      </form>

      <div className="register-footer">
        {t({ ja: "すでにアカウントをお持ちですか？", en: "Already have an account?" })}{" "}
        <Link to="/login">{t({ ja: "ログインはこちら", en: "Log in here" })}</Link>
      </div>
    </div>
  );
}
