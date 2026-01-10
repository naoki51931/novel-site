import { useEffect, useState } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";

const POST_LOGIN_REDIRECT_KEY = "post_login_redirect_v1";

export default function OAuthCallback() {
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useI18n();
  const [error, setError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const errorParam = params.get("error");
    if (errorParam) {
      setError(errorParam);
      return;
    }

    const token = params.get("token");
    if (!token) {
      setError(
        t({
          ja: "ログインに必要な情報が不足しています。",
          en: "Missing information required to log in.",
        })
      );
      return;
    }

    const username = params.get("username");
    try {
      localStorage.setItem("token", token);
      if (username) {
        localStorage.setItem("username", username);
      }
    } catch {
      setError(
        t({ ja: "ログイン情報の保存に失敗しました。", en: "Failed to save login info." })
      );
      return;
    }

    const redirect = params.get("redirect");
    let nextPath = redirect && redirect.startsWith("/") ? redirect : null;
    if (!nextPath) {
      try {
        const stored = localStorage.getItem(POST_LOGIN_REDIRECT_KEY);
        if (stored && stored.startsWith("/")) {
          nextPath = stored;
        }
        localStorage.removeItem(POST_LOGIN_REDIRECT_KEY);
      } catch {
        // ignore
      }
    }
    if (!nextPath) nextPath = "/mypage";
    navigate(nextPath, { replace: true });
  }, [location.search, navigate]);

  if (error) {
    return (
      <div style={{ maxWidth: 480, margin: "2rem auto", textAlign: "center" }}>
        <h2>{t({ ja: "ログインに失敗しました", en: "Login failed" })}</h2>
        <p style={{ color: "var(--muted-text)" }}>{error}</p>
        <Link to="/login" className="btn btn-border">
          {t({ ja: "ログイン画面へ戻る", en: "Back to login" })}
        </Link>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 480, margin: "2rem auto", textAlign: "center" }}>
      <h2>{t({ ja: "ログイン処理中...", en: "Signing you in..." })}</h2>
      <p style={{ color: "var(--muted-text)" }}>
        {t({ ja: "少々お待ちください。", en: "Please wait a moment." })}
      </p>
    </div>
  );
}
