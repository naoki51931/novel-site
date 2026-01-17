import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { useI18n } from "../lib/i18n";

export default function AdminHome() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [contactSubject, setContactSubject] = useState("");
  const [contactBody, setContactBody] = useState("");
  const [contactSending, setContactSending] = useState(false);
  const [contactError, setContactError] = useState("");
  const [contactSuccess, setContactSuccess] = useState("");
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

  const refreshMessages = async () => {
    try {
      const messages = await apiFetch("/api/admin/contact/messages?limit=50", {
        credentials: "include",
      });
      setContactMessages(messages || []);
    } catch (e) {
      setContactError(
        e.message || t({ ja: "送信ログの取得に失敗しました。", en: "Failed to load messages." })
      );
    }
  };

  const handleContactSubmit = async (event) => {
    event.preventDefault();
    setContactError("");
    setContactSuccess("");
    try {
      setContactSending(true);
      await apiFetch("/api/admin/contact/messages", {
        method: "POST",
        credentials: "include",
        body: {
          subject: contactSubject,
          body: contactBody,
        },
      });
      setContactSuccess(t({ ja: "送信しました。", en: "Sent successfully." }));
      setContactSubject("");
      setContactBody("");
      await refreshMessages();
    } catch (e) {
      setContactError(
        e.message || t({ ja: "送信に失敗しました。", en: "Failed to send." })
      );
    } finally {
      setContactSending(false);
    }
  };

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
          border: "1px solid #ddd",
          borderRadius: 10,
          padding: 16,
          marginBottom: 20,
          background: "#fff",
        }}
      >
        <h3 style={{ marginTop: 0 }}>{t({ ja: "お問い合わせ", en: "Contact" })}</h3>
        <form onSubmit={handleContactSubmit} style={{ display: "grid", gap: 10 }}>
          <input
            type="text"
            value={contactSubject}
            onChange={(event) => setContactSubject(event.target.value)}
            placeholder={t({ ja: "件名", en: "Subject" })}
            style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid #ccc" }}
          />
          <textarea
            value={contactBody}
            onChange={(event) => setContactBody(event.target.value)}
            placeholder={t({ ja: "本文", en: "Message" })}
            rows={5}
            style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid #ccc" }}
          />
          {contactError && <div style={{ color: "red" }}>{contactError}</div>}
          {contactSuccess && <div style={{ color: "green" }}>{contactSuccess}</div>}
          <button
            type="submit"
            className="btn btn-border"
            disabled={contactSending || !contactSubject.trim() || !contactBody.trim()}
          >
            {contactSending ? t({ ja: "送信中...", en: "Sending..." }) : t({ ja: "送信", en: "Send" })}
          </button>
        </form>
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
                    border: "1px solid #eee",
                    borderRadius: 8,
                    padding: 10,
                    background: "#fafafa",
                  }}
                >
                  <div style={{ fontWeight: 600 }}>{message.subject}</div>
                  <div style={{ whiteSpace: "pre-wrap", marginTop: 6 }}>{message.body}</div>
                  <div style={{ fontSize: 12, color: "#666", marginTop: 6 }}>
                    {message.admin_username
                      ? `${message.admin_username} / `
                      : ""}
                    {new Date(message.created_at).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: "#666" }}>
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
