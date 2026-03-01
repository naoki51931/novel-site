import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { redirectToAndroidAppLogin } from "../lib/mobileAppRedirect";
import { getApiBase } from "../lib/apiBase";

const API_BASE = getApiBase();
const PENDING_AI_POST_KEY = "pending_ai_post_v1";
const PENDING_AI_POST_ERROR_KEY = "pending_ai_post_error_v1";
const POST_LOGIN_REDIRECT_KEY = "post_login_redirect_v1";

function loadPendingAiPost() {
  try {
    const raw = localStorage.getItem(PENDING_AI_POST_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function clearPendingAiPost() {
  try {
    localStorage.removeItem(PENDING_AI_POST_KEY);
  } catch {
    // ignore
  }
}

function savePendingAiPostError(message) {
  try {
    localStorage.setItem(PENDING_AI_POST_ERROR_KEY, message);
  } catch {
    // ignore
  }
}

function consumePostLoginRedirect() {
  try {
    const path = localStorage.getItem(POST_LOGIN_REDIRECT_KEY);
    if (!path) return null;
    localStorage.removeItem(POST_LOGIN_REDIRECT_KEY);
    return path;
  } catch {
    return null;
  }
}

export default function Login() {
  const navigate = useNavigate();
  const { t } = useI18n();

  const [step, setStep] = useState(1); // 1: ユーザー名+パスワード / 2: 6桁コード入力
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [oauthLoading, setOauthLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const savedUsername = localStorage.getItem("username");
  const hasToken = !!localStorage.getItem("token");

  const handleLoginSuccess = async (accessToken) => {
    if (!accessToken) {
      throw new Error(t({ ja: "トークンの取得に失敗しました。", en: "Failed to obtain token." }));
    }

    const redirectPath = consumePostLoginRedirect();
    const pending = loadPendingAiPost();

    if (!pending?.body) {
      const appClientHint =
        typeof window !== "undefined" &&
        (() => {
          try {
            const params = new URLSearchParams(window.location.search || "");
            const client = (params.get("client") || "").toLowerCase();
            return client === "app" || params.get("app_client") === "1";
          } catch {
            return false;
          }
        })();
      const nextPath = redirectPath && redirectPath.startsWith("/") ? redirectPath : "/mypage";
      const moved = redirectToAndroidAppLogin({
        appClient: appClientHint,
        token: accessToken,
        username,
        redirect: nextPath,
      });
      if (moved) return;
    }

    // トークンとユーザー名を保存
    localStorage.setItem("token", accessToken);
    localStorage.setItem("username", username);

    if (!pending || !pending.body) {
      if (redirectPath && redirectPath.startsWith("/")) {
        navigate(redirectPath);
      } else {
        navigate("/mypage");
      }
      return;
    }

    setInfo(
      t({
        ja: "ログイン完了。保存していた AI 小説を投稿しています…",
        en: "Login complete. Posting your saved AI novel...",
      })
    );

    try {
      const token = accessToken;

      if (pending.kind === "new_novel") {
        const novelPayload = {
          title: pending.generated_title || t({ ja: "AI生成小説", en: "AI-generated novel" }),
          description: t({ ja: "AI生成", en: "AI-generated" }),
          age_limit: pending.age_limit === "r18" ? "r18" : "all",
          is_ai_generated: true,
          tag_names: [],
        };

        const novelRes = await fetch(`${API_BASE}/api/novels`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(novelPayload),
        });
        const novelData = await novelRes.json().catch(() => ({}));
        if (!novelRes.ok) {
          throw new Error(
            novelData.detail ||
              t(
                {
                  ja: "小説の作成に失敗しました (status={{status}})",
                  en: "Failed to create novel (status={{status}})",
                },
                { status: novelRes.status }
              )
          );
        }
        const novelId = novelData?.id;
        if (!novelId) {
          throw new Error(
            t({ ja: "小説IDが取得できませんでした。", en: "Could not get novel ID." })
          );
        }

        const episodePayload = {
          episode_number: 1,
          title: t({ ja: "第1話", en: "Episode 1" }),
          body: pending.body,
          tag_names: [],
        };
        const epRes = await fetch(`${API_BASE}/api/novels/${novelId}/episodes`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(episodePayload),
        });
        const epData = await epRes.json().catch(() => ({}));
        if (!epRes.ok) {
          throw new Error(
            epData.detail ||
              t(
                {
                  ja: "第1話の投稿に失敗しました (status={{status}})",
                  en: "Failed to post Episode 1 (status={{status}})",
                },
                { status: epRes.status }
              )
          );
        }

        clearPendingAiPost();
        navigate(`/novels/${novelId}`);
        return;
      }

      if (pending.kind === "next_episode") {
        const novelId = pending.continue_novel_id;
        if (!novelId) {
          throw new Error(
            t({
              ja: "投稿先の小説IDが取得できませんでした。",
              en: "Could not get destination novel ID.",
            })
          );
        }

        const listRes = await fetch(`${API_BASE}/api/novels/${novelId}/episodes`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const listData = await listRes.json().catch(() => []);
        if (!listRes.ok) {
          throw new Error(
            (listData && listData.detail) ||
              t(
                {
                  ja: "エピソード一覧の取得に失敗しました (status={{status}})",
                  en: "Failed to fetch episode list (status={{status}})",
                },
                { status: listRes.status }
              )
          );
        }

        const numbers = Array.isArray(listData)
          ? listData
              .map((e) => (typeof e?.number === "number" ? e.number : null))
              .filter((n) => n !== null)
          : [];
        const maxNumber = numbers.length ? Math.max(...numbers) : 0;
        const nextNumber = maxNumber + 1;

        const episodePayload = {
          episode_number: nextNumber,
          title:
            (pending.post_episode_title || "").trim() ||
            t(
              { ja: "第{{num}}話", en: "Episode {{num}}" },
              { num: nextNumber }
            ),
          body: pending.body,
          tag_names: [],
        };
        const epRes = await fetch(`${API_BASE}/api/novels/${novelId}/episodes`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(episodePayload),
        });
        const epData = await epRes.json().catch(() => ({}));
        if (!epRes.ok) {
          throw new Error(
            epData.detail ||
              t(
                {
                  ja: "エピソードの投稿に失敗しました (status={{status}})",
                  en: "Failed to post episode (status={{status}})",
                },
                { status: epRes.status }
              )
          );
        }

        clearPendingAiPost();
        navigate(`/novels/${novelId}`);
        return;
      }

      navigate("/mypage");
    } catch (e2) {
      console.error(e2);
      savePendingAiPostError(
        e2?.message ||
          t({
            ja: "保存していた AI 小説の投稿に失敗しました。",
            en: "Failed to post your saved AI novel.",
          })
      );
      navigate("/ai-novel?restore_pending=1");
    }
  };

  // 1段階目: /api/auth/login/start
  const handleStart = async (e) => {
    e.preventDefault();
    setError("");
    setInfo("");

    if (!username.trim() || !password.trim()) {
      setError(
        t({
          ja: "ユーザー名とパスワードを入力してください。",
          en: "Please enter your username and password.",
        })
      );
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
        throw new Error(data.detail || t({ ja: "ログインに失敗しました。", en: "Login failed." }));
      }

      if (data.access_token) {
        if (data.two_factor_skipped) {
          setInfo(
            t({
              ja: "メール認証をスキップしてログインしました。",
              en: "Logged in without email verification.",
            })
          );
        }
        await handleLoginSuccess(data.access_token);
        return;
      }

      // ここまで来たら 6桁コードが発行済み
      setStep(2);
      setInfo(
        t({
          ja: "認証コードをメールで送信しました。(SMTP未設定の場合はサーバーログに表示されます)",
          en: "We sent a verification code by email. (If SMTP isn't configured, it appears in server logs.)",
        })
      );
    } catch (err) {
      console.error(err);
      setError(
        err.message ||
          t({ ja: "ログイン中にエラーが発生しました。", en: "An error occurred during login." })
      );
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
      setError(t({ ja: "認証コードを入力してください。", en: "Please enter the verification code." }));
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
        throw new Error(
          data.detail ||
            t({ ja: "認証コードの検証に失敗しました。", en: "Failed to verify the code." })
        );
      }

      if (!data.access_token) {
        throw new Error(t({ ja: "トークンの取得に失敗しました。", en: "Failed to obtain token." }));
      }
      await handleLoginSuccess(data.access_token);
    } catch (err) {
      console.error(err);
      setError(
        err.message || t({ ja: "認証中にエラーが発生しました。", en: "An error occurred during verification." })
      );
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    navigate("/");
  };

  const handleOAuth = async (provider) => {
    setError("");
    setInfo("");
    setOauthLoading(true);
    try {
      const isAppClient =
        typeof window !== "undefined" &&
        !!window.AndroidFormBridge &&
        typeof window.AndroidFormBridge.registerMobilePush === "function";
      const oauthClient = isAppClient ? "app" : "web";
      window.location.href = `${API_BASE}/api/auth/oauth/${provider}/start?client=${encodeURIComponent(oauthClient)}&direct=1`;
      return;
    } catch (err) {
      console.error(err);
      setError(
        err.message || t({ ja: "OAuth でエラーが発生しました。", en: "An error occurred during OAuth." })
      );
      setOauthLoading(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">{t({ ja: "← トップに戻る", en: "← Back to Home" })}</Link>
      </div>

      <h2>{t({ ja: "ログイン（二段階認証）", en: "Login (2FA)" })}</h2>
      <div style={{ marginTop: 6, marginBottom: 14, fontSize: 13 }}>
        <Link to="/register">
          {t({ ja: "会員登録はこちら", en: "Create an account" })}
        </Link>
      </div>

      <div style={{ marginBottom: 16, display: "grid", gap: 8 }}>
        <button
          type="button"
          className="btn btn-border"
          disabled={oauthLoading}
          onClick={() => handleOAuth("google")}
        >
          {t({ ja: "Googleでログイン", en: "Login with Google" })}
        </button>
        <button
          type="button"
          className="btn btn-border"
          disabled={oauthLoading}
          onClick={() => handleOAuth("x")}
        >
          {t({ ja: "Xでログイン", en: "Login with X" })}
        </button>
        <div style={{ textAlign: "center", color: "var(--muted-text)" }}>
          {t({ ja: "または", en: "or" })}
        </div>
      </div>

      {hasToken && (
        <div
          style={{
            padding: 8,
            marginBottom: 12,
            border: "1px solid var(--border)",
            borderRadius: 6,
            backgroundColor: "var(--login-status-bg)",
            fontSize: 14,
          }}
        >
          <div>
            {t({ ja: "現在ログイン中", en: "Currently logged in" })}:{" "}
            {savedUsername || t({ ja: "不明なユーザー", en: "Unknown user" })}
          </div>
          <button
            type="button"
            className="btn btn-border"
            style={{ marginTop: 8 }}
            onClick={handleLogout}
          >
            {t({ ja: "ログアウトする", en: "Log out" })}
          </button>
        </div>
      )}

      {step === 1 && (
        <form onSubmit={handleStart}>
          <div style={{ marginBottom: 8 }}>
            <label>
              {t({ ja: "ユーザー名", en: "Username" })}
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
              {t({ ja: "パスワード", en: "Password" })}
              <br />
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
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
            {loading
              ? t({ ja: "送信中...", en: "Sending..." })
              : t({ ja: "認証コードを送信", en: "Send verification code" })}
          </button>

          <div style={{ marginTop: 12, fontSize: 12 }}>
            <Link to="/reset-password">
              {t({ ja: "パスワードを忘れた場合", en: "Forgot password?" })}
            </Link>
          </div>
        </form>
      )}

      {step === 2 && (
        <form onSubmit={handleVerify}>
          <div style={{ marginBottom: 8 }}>
            <p style={{ marginBottom: 4 }}>
              {t({
                ja: "メールに届いた 6 桁の認証コードを入力してください。",
                en: "Enter the 6-digit verification code sent to your email.",
              })}
              <br />
              {t({
                ja: "※ SMTP 未設定の場合は、サーバーログにコードが表示されます。",
                en: "If SMTP isn't configured, the code appears in server logs.",
              })}
            </p>
            <label>
              {t({ ja: "認証コード（6桁）", en: "Verification code (6 digits)" })}
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
            {loading ? t({ ja: "認証中...", en: "Verifying..." }) : t({ ja: "ログイン", en: "Login" })}
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
              {t({
                ja: "ユーザー名・パスワード入力からやり直す",
                en: "Start over with username and password",
              })}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
