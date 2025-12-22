import { useEffect, useState } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";

export default function OAuthCallback() {
  const location = useLocation();
  const navigate = useNavigate();
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
      setError("ログインに必要な情報が不足しています。");
      return;
    }

    const username = params.get("username");
    try {
      localStorage.setItem("token", token);
      if (username) {
        localStorage.setItem("username", username);
      }
    } catch {
      setError("ログイン情報の保存に失敗しました。");
      return;
    }

    const redirect = params.get("redirect");
    const nextPath = redirect && redirect.startsWith("/") ? redirect : "/mypage";
    navigate(nextPath, { replace: true });
  }, [location.search, navigate]);

  if (error) {
    return (
      <div style={{ maxWidth: 480, margin: "2rem auto", textAlign: "center" }}>
        <h2>ログインに失敗しました</h2>
        <p style={{ color: "var(--muted-text)" }}>{error}</p>
        <Link to="/login" className="btn btn-border">
          ログイン画面へ戻る
        </Link>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 480, margin: "2rem auto", textAlign: "center" }}>
      <h2>ログイン処理中...</h2>
      <p style={{ color: "var(--muted-text)" }}>少々お待ちください。</p>
    </div>
  );
}
