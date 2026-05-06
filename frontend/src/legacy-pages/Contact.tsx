import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useI18n } from "../lib/i18n";
import { apiFetch, authTokenExists } from "../lib/api";
import { getErrorMessage } from "../lib/errorUtils";

const RECAPTCHA_SITE_KEY = (process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY || "").toString().trim();

export default function Contact() {
  const { t } = useI18n();
  const isLoggedIn = authTokenExists();
  const shouldUseRecaptcha = !isLoggedIn && !!RECAPTCHA_SITE_KEY;
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [recaptchaReady, setRecaptchaReady] = useState(!shouldUseRecaptcha);

  useEffect(() => {
    if (!shouldUseRecaptcha) return;
    if (typeof window === "undefined") return;
    setRecaptchaReady(false);

    const scriptId = "google-recaptcha-enterprise-js";
    let script = document.getElementById(scriptId);
    if (!script) {
      script = document.createElement("script");
      script.id = scriptId;
      script.src = `https://www.google.com/recaptcha/enterprise.js?render=${encodeURIComponent(RECAPTCHA_SITE_KEY)}`;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }

    const onLoad = () => setRecaptchaReady(true);
    const onError = () => setRecaptchaReady(false);
    script.addEventListener("load", onLoad);
    script.addEventListener("error", onError);
    if (window.grecaptcha?.enterprise) {
      setRecaptchaReady(true);
    }
    return () => {
      script.removeEventListener("load", onLoad);
      script.removeEventListener("error", onError);
    };
  }, [shouldUseRecaptcha]);

  const requestRecaptchaToken = async (action: string) => {
    if (!shouldUseRecaptcha) return "";
    const grecaptchaEnterprise = window.grecaptcha?.enterprise;
    if (!grecaptchaEnterprise) {
      throw new Error(t({ ja: "reCAPTCHAの初期化に失敗しました", en: "Failed to initialize reCAPTCHA." }));
    }
    return await new Promise((resolve, reject) => {
      grecaptchaEnterprise.ready(async () => {
        try {
          const token = await grecaptchaEnterprise.execute(RECAPTCHA_SITE_KEY, { action });
          if (!token) {
            reject(new Error(t({ ja: "reCAPTCHAトークン取得に失敗しました", en: "Failed to get reCAPTCHA token." })));
            return;
          }
          resolve(token);
        } catch (e) {
          reject(e);
        }
      });
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
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
      const recaptchaToken = shouldUseRecaptcha ? await requestRecaptchaToken("CONTACT_MESSAGE") : "";
      await apiFetch("/api/contact/messages", {
        method: "POST",
        auth: true,
        body: {
          name: name.trim() || null,
          email: email.trim() || null,
          subject: subject.trim(),
          body: body.trim(),
          recaptcha_token: recaptchaToken,
          recaptcha_action: "CONTACT_MESSAGE",
        },
      });
      setSuccess(t({ ja: "送信しました。", en: "Sent successfully." }));
      setName("");
      setEmail("");
      setSubject("");
      setBody("");
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "送信に失敗しました。", en: "Failed to send." })));
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
      {shouldUseRecaptcha && (
        <p style={{ marginBottom: 16, fontSize: 13, color: recaptchaReady ? "var(--muted-text, #666)" : "#b45309" }}>
          {recaptchaReady
            ? t({
                ja: "未ログイン時は bot 対策のため reCAPTCHA が適用されます。",
                en: "reCAPTCHA is applied for guest submissions.",
              })
            : t({
                ja: "reCAPTCHA を読み込み中です。しばらく待ってから送信してください。",
                en: "Loading reCAPTCHA. Please wait before sending.",
              })}
        </p>
      )}
      <form onSubmit={handleSubmit} style={{ display: "grid", gap: 10 }}>
        <input
          type="text"
          value={name}
          onChange={(event: ChangeEvent<HTMLInputElement>) => setName(event.target.value)}
          placeholder={t({ ja: "お名前 (任意)", en: "Name (optional)" })}
          style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid #ccc" }}
        />
        <input
          type="email"
          value={email}
          onChange={(event: ChangeEvent<HTMLInputElement>) => setEmail(event.target.value)}
          placeholder={t({ ja: "メールアドレス (任意)", en: "Email (optional)" })}
          style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid #ccc" }}
        />
        <input
          type="text"
          value={subject}
          onChange={(event: ChangeEvent<HTMLInputElement>) => setSubject(event.target.value)}
          placeholder={t({ ja: "件名", en: "Subject" })}
          style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid #ccc" }}
        />
        <textarea
          value={body}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setBody(event.target.value)}
          placeholder={t({ ja: "本文", en: "Message" })}
          rows={6}
          style={{ padding: "10px 12px", borderRadius: 6, border: "1px solid #ccc" }}
        />
        {error && <div style={{ color: "red" }}>{error}</div>}
        {success && <div style={{ color: "green" }}>{success}</div>}
        <button
          type="submit"
          className="btn btn-border"
          disabled={sending || !subject.trim() || !body.trim() || (shouldUseRecaptcha && !recaptchaReady)}
        >
          {sending ? t({ ja: "送信中...", en: "Sending..." }) : t({ ja: "送信", en: "Send" })}
        </button>
      </form>
    </div>
  );
}
