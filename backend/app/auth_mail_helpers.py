import smtplib
from email.mime.text import MIMEText  # type: ignore

from .notification_helpers import SMTP_FROM, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER


def send_password_reset_email(to_email: str, reset_url: str, expires_minutes: int) -> None:
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not to_email:
        print(f"[password-reset] SMTP設定が不足しているためログにのみ出力: url={reset_url}, to={to_email}")
        return

    subject = "小説投稿サイトLexis パスワード再設定"
    body = (
        "以下のリンクからパスワードを再設定してください。\n\n"
        f"{reset_url}\n\n"
        f"このリンクは {expires_minutes} 分間のみ有効です。\n"
        "心当たりがない場合は、このメールは破棄してください。"
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[password-reset] メール送信成功 to={to_email}")
    except Exception as e:
        print(f"[password-reset] メール送信失敗 to={to_email}, err={e!r}")


def send_register_email_verification_code(
    to_email: str,
    code: str,
    expires_minutes: int,
) -> None:
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not to_email:
        raise RuntimeError("SMTP設定が不足しています")

    subject = "小説投稿サイトLexis メール認証コード"
    body = (
        "会員登録のメール認証コードです。\n\n"
        f"認証コード: {code}\n\n"
        f"このコードは {expires_minutes} 分間有効です。"
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


def send_2fa_email(to_email: str, code: str):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not to_email:
        print(f"[2FA] SMTP設定が不足しているためログにのみ出力: code={code}, to={to_email}")
        return

    subject = "小説投稿サイトLexis ログイン認証コード"
    body = f"ログイン用認証コードは {code} です。\n10分以内に入力してください。"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[2FA] 認証コード送信成功 to={to_email}, code={code}")
    except Exception as e:
        print(f"[2FA] メール送信失敗 to={to_email}, code={code}, err={e!r}")
