import { useState } from "react";
import { useI18n } from "../lib/i18n";
import { apiFetch } from "../lib/api";

export default function Contact() {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (!subject.trim() || !body.trim()) {
      setError(
        t({ ja: "件名と本文を入力してください。", en: "Please enter a subject and message." })
      );
      return;
    }

    try {
      setSending(true);
      await apiFetch("/api/contact/messages", {
        method: "POST",
        auth: true,
        body: {
          name: name.trim() || null,
          email: email.trim() || null,
          subject: subject.trim(),
          body: body.trim(),
        },
      });
      setSuccess(t({ ja: "送信しました。", en: "Sent successfully." }));
      setName("");
      setEmail("");
      setSubject("");
      setBody("");
    } catch (e) {
      setError(e.message || t({ ja: "送信に失敗しました。", en: "Failed to send." }));
    } finally {
      setSending(false);
    }
  };

  return (
    <div style={{ maxWidth: 700, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 12 }}>{t({ ja: "お問い合わせ", en: "Contact" })}</h2>
      <p style={{ marginBottom: 16 }}>
        {t({
          ja: "運営にメッセージを送ります。返信が必要な場合はメールアドレスを記入してください。",
          en: "Send a message to the operator. Add an email address if you need a reply.",
        })}
      </p>
      <form onSubmit={handleSubmit} style={{ display: "grid", gap: 10 }}>
        <input
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder={t({ ja: "お名前 (任意)", en: "Name (optional)" })}
          style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid #ccc" }}
        />
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder={t({ ja: "メールアドレス (任意)", en: "Email (optional)" })}
          style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid #ccc" }}
        />
        <input
          type="text"
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
          placeholder={t({ ja: "件名", en: "Subject" })}
          style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid #ccc" }}
        />
        <textarea
          value={body}
          onChange={(event) => setBody(event.target.value)}
          placeholder={t({ ja: "本文", en: "Message" })}
          rows={6}
          style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid #ccc" }}
        />
        {error && <div style={{ color: "red" }}>{error}</div>}
        {success && <div style={{ color: "green" }}>{success}</div>}
        <button
          type="submit"
          className="btn btn-border"
          disabled={sending || !subject.trim() || !body.trim()}
        >
          {sending ? t({ ja: "送信中...", en: "Sending..." }) : t({ ja: "送信", en: "Send" })}
        </button>
      </form>
    </div>
  );
}
