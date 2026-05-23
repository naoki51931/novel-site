from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from .. import notification_helpers


def public_create_contact_message_service(*, request: Request, payload, db: Session):
    from .. import main as legacy

    subject = (payload.subject or "").strip()
    body = (payload.body or "").strip()
    name = (payload.name or "").strip() or None
    email = (payload.email or "").strip() or None
    if not subject:
        raise HTTPException(400, "件名を入力してください")
    if not body:
        raise HTTPException(400, "本文を入力してください")

    try:
        user = legacy.get_optional_current_user(request, db)
    except HTTPException:
        user = None
    if user is None:
        recaptcha_ok = legacy.verify_recaptcha_token(
            payload.recaptcha_token or "",
            remote_ip=legacy._public_contact_remote_ip(request),
            expected_action=(payload.recaptcha_action or "CONTACT_MESSAGE"),
        )
        if not recaptcha_ok:
            raise HTTPException(400, "reCAPTCHA の検証に失敗しました")
        legacy._enforce_public_contact_abuse_guards(request, subject, body)

    sender_label = None
    if user:
        sender_label = f"user:{user.username}"
    elif name:
        sender_label = f"name:{name}"
    elif email:
        sender_label = f"email:{email}"

    header_lines = []
    if user:
        header_lines.append(f"User: {user.username}")
    if name:
        header_lines.append(f"Name: {name}")
    if email:
        header_lines.append(f"Email: {email}")
    header_text = "\n".join(header_lines)
    body_with_sender = f"{header_text}\n\n{body}" if header_text else body

    message = legacy.models.AdminContactMessage(
        admin_username=sender_label,
        subject=subject,
        body=body_with_sender,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    notification_helpers.send_public_contact_email(subject, body_with_sender)
    if user is None:
        legacy._record_public_contact_submission(legacy._public_contact_remote_ip(request), subject, body)
    return message
