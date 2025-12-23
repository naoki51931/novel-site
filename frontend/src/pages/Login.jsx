import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";

const API_BASE = "";
const PENDING_AI_POST_KEY = "pending_ai_post_v1";
const PENDING_AI_POST_ERROR_KEY = "pending_ai_post_error_v1";

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

export default function Login() {
  const navigate = useNavigate();

  const [step, setStep] = useState(1); // 1: ユーザー名+パスワード / 2: 6桁コード入力
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [oauthLoading, setOauthLoading] = useState(false);
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

      const pending = loadPendingAiPost();
      if (!pending || !pending.body) {
        navigate("/mypage");
        return;
      }

      setInfo("ログイン完了。保存していた AI 小説を投稿しています…");

      try {
        const token = data.access_token;

        if (pending.kind === "new_novel") {
          const novelPayload = {
            title: pending.generated_title || "AI生成小説",
            description: "AI生成",
            age_limit: "all",
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
            throw new Error(novelData.detail || `小説の作成に失敗しました (status=${novelRes.status})`);
          }
          const novelId = novelData?.id;
          if (!novelId) {
            throw new Error("小説IDが取得できませんでした。");
          }

          const episodePayload = {
            episode_number: 1,
            title: "第1話",
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
            throw new Error(epData.detail || `第1話の投稿に失敗しました (status=${epRes.status})`);
          }

          clearPendingAiPost();
          navigate(`/novels/${novelId}`);
          return;
        }

        if (pending.kind === "next_episode") {
          const novelId = pending.continue_novel_id;
          if (!novelId) {
            throw new Error("投稿先の小説IDが取得できませんでした。");
          }

          const listRes = await fetch(`${API_BASE}/api/novels/${novelId}/episodes`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          const listData = await listRes.json().catch(() => []);
          if (!listRes.ok) {
            throw new Error(
              (listData && listData.detail) ||
                `エピソード一覧の取得に失敗しました (status=${listRes.status})`
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
            title: (pending.post_episode_title || "").trim() || `第${nextNumber}話`,
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
            throw new Error(epData.detail || `エピソードの投稿に失敗しました (status=${epRes.status})`);
          }

          clearPendingAiPost();
          navigate(`/novels/${novelId}`);
          return;
        }

        navigate("/mypage");
      } catch (e2) {
        console.error(e2);
        savePendingAiPostError(
          e2?.message || "保存していた AI 小説の投稿に失敗しました。"
        );
        navigate("/ai-novel?restore_pending=1");
      }
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

  const handleOAuth = async (provider) => {
    setError("");
    setInfo("");
    setOauthLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/oauth/${provider}/start`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.auth_url) {
        throw new Error(data.detail || "OAuth の開始に失敗しました。");
      }
      window.location.href = data.auth_url;
    } catch (err) {
      console.error(err);
      setError(err.message || "OAuth でエラーが発生しました。");
      setOauthLoading(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">← トップに戻る</Link>
      </div>

      <h2>ログイン（二段階認証）</h2>

      <div style={{ marginBottom: 16, display: "grid", gap: 8 }}>
        <button
          type="button"
          className="btn btn-border"
          disabled={oauthLoading}
          onClick={() => handleOAuth("google")}
        >
          Googleでログイン
        </button>
        <button
          type="button"
          className="btn btn-border"
          disabled={oauthLoading}
          onClick={() => handleOAuth("x")}
        >
          Xでログイン
        </button>
        <div style={{ textAlign: "center", color: "var(--muted-text)" }}>
          または
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

          <div style={{ marginTop: 12, fontSize: 12 }}>
            <Link to="/reset-password">パスワードを忘れた場合</Link>
          </div>
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
