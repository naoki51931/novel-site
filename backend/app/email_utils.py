import os
import smtplib
from email.message import EmailMessage


SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER or "no-reply@example.com")


def send_login_code_email(to_email: str, code: str) -> None:
    """
    ログイン用6桁コードをメール送信する。
    SMTPが未設定の場合はコンソールに警告を出すだけ。
    """
    if not SMTP_HOST:
        print(f"[WARN] SMTP_HOST 未設定のためメール送信スキップ: code={code}, to={to_email}")
        return

    msg = EmailMessage()
    msg["Subject"] = "小説投稿サイトLexis ログイン確認コード"
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg.set_content(
        f"小説投稿サイトLexisへのログイン確認コードは {code} です。\n\n"
        "このコードは10分間のみ有効です。\n"
        "心当たりがない場合は、このメールは破棄してください。"
    )

    if SMTP_USE_TLS:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    else:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
