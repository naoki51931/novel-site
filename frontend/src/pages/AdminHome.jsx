import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { useI18n } from "../lib/i18n";

export default function AdminHome() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [contactError, setContactError] = useState("");
  const [contactMessages, setContactMessages] = useState([]);
  const [contactLoading, setContactLoading] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        await apiFetch("/api/admin/auth/me", { credentials: "include" });
      } catch {
        navigate("/admin/login", { replace: true });
        return;
      }
      try {
        const messages = await apiFetch("/api/admin/contact/messages?limit=50", {
          credentials: "include",
        });
        setContactMessages(messages || []);
      } catch (e) {
        setContactError(
          e.message || t({ ja: "送信ログの取得に失敗しました。", en: "Failed to load messages." })
        );
      } finally {
        setContactLoading(false);
      }
    };
    checkAuth();
  }, [navigate, t]);

  const handleLogout = async () => {
    await apiFetch("/api/admin/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    navigate("/admin/login", { replace: true });
  };

  return (
    <div style={{ maxWidth: 700, margin: "0 auto" }}>
      <section
        id="admin-contact"
        style={{
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: 16,
          marginBottom: 20,
          background: "var(--surface)",
        }}
      >
        <h3 style={{ marginTop: 0 }}>{t({ ja: "お問い合わせ", en: "Contact" })}</h3>
        {contactError && <div style={{ color: "red" }}>{contactError}</div>}
        <div style={{ marginTop: 16 }}>
          <h4 style={{ marginBottom: 8 }}>{t({ ja: "送信ログ", en: "Send log" })}</h4>
          {contactLoading ? (
            <div>{t({ ja: "読み込み中...", en: "Loading..." })}</div>
          ) : contactMessages.length ? (
            <div style={{ display: "grid", gap: 10 }}>
              {contactMessages.map((message) => (
                <div
                  key={message.id}
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    padding: 10,
                    background: "var(--surface-2)",
                  }}
                >
                  <div style={{ fontWeight: 600 }}>{message.subject}</div>
                  <div style={{ whiteSpace: "pre-wrap", marginTop: 6 }}>{message.body}</div>
                  <div style={{ fontSize: 12, color: "var(--muted-text)", marginTop: 6 }}>
                    {message.admin_username
                      ? `${message.admin_username} / `
                      : ""}
                    {new Date(message.created_at).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: "var(--muted-text)" }}>
              {t({ ja: "送信ログはまだありません。", en: "No messages yet." })}
            </div>
          )}
        </div>
      </section>
      <h2 style={{ marginBottom: 16 }}>{t({ ja: "管理画面", en: "Admin" })}</h2>
      <p style={{ marginBottom: 12 }}>
        {t({ ja: "運営向けの管理機能です。", en: "Administration tools for operators." })}
      </p>
      <a href="#admin-contact" style={{ display: "inline-block", marginBottom: 12 }}>
        {t({ ja: "お問い合わせへ", en: "Go to Contact" })}
      </a>
      <Link className="btn btn-border" to="/admin/payouts">
        {t({ ja: "精算管理へ", en: "Go to Payouts" })}
      </Link>
      <Link className="btn btn-border" to="/admin/dashboard" style={{ marginLeft: 8 }}>
        {t({ ja: "支援/振込ダッシュボードへ", en: "Go to Support & Payout Dashboard" })}
      </Link>
      <Link className="btn btn-border" to="/admin/users" style={{ marginLeft: 8 }}>
        {t({ ja: "ユーザー管理へ", en: "Go to Users" })}
      </Link>
      <Link className="btn btn-border" to="/admin/ai-jobs" style={{ marginLeft: 8 }}>
        {t({ ja: "AIジョブ管理へ", en: "Go to AI Jobs" })}
      </Link>
      <button
        type="button"
        className="btn btn-border"
        onClick={handleLogout}
        style={{ marginLeft: 8 }}
      >
        {t({ ja: "ログアウト", en: "Log out" })}
      </button>
    </div>
  );
}
