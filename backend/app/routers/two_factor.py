from datetime import datetime, timedelta
import secrets
import threading

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import Session

from ..database import Base, engine, get_db
from ..models import User
from .auth import create_access_token  # 既存のJWT作成関数を利用する想定
from ..email_utils import send_login_code_email
from ..time_utils import UTCDateTime as DateTime, utcnow


# ============================
# DB テーブル定義
# ============================

class EmailLoginToken(Base):
    __tablename__ = "email_login_tokens"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), index=True, nullable=False)
    code = Column(String(20), nullable=False)  # 簡易に平文保存（本番で気になるならハッシュ化も可）
    created_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, default=False, nullable=False)


_email_login_token_table_ready = False
_email_login_token_table_lock = threading.Lock()


def ensure_email_login_token_table() -> None:
    global _email_login_token_table_ready
    if _email_login_token_table_ready:
        return
    with _email_login_token_table_lock:
        if _email_login_token_table_ready:
            return
        Base.metadata.create_all(bind=engine)
        _email_login_token_table_ready = True


# ============================
# Pydantic スキーマ
# ============================

class EmailCodeRequest(BaseModel):
    email: EmailStr


class EmailCodeVerify(BaseModel):
    email: EmailStr
    code: str


# ============================
# Router 本体
# ============================

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)


def _generate_code(length: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


@router.post("/request-email-code")
def request_email_code(payload: EmailCodeRequest, db: Session = Depends(get_db)):
    """
    email 宛に6桁コードを送るエンドポイント。
    ユーザーが存在しない場合も 200 を返して「存在有無」は漏らさない。
    """
    ensure_email_login_token_table()
    user = db.query(User).filter(User.email == payload.email).first()  # User に email カラムがある想定

    if user:
        now = utcnow()
        code = _generate_code()
        token = EmailLoginToken(
            email=payload.email,
            code=code,
            created_at=now,
            expires_at=now + timedelta(minutes=10),
            consumed=False,
        )
        db.add(token)
        db.commit()
        db.refresh(token)

        send_login_code_email(payload.email, code)

    return {"ok": True}


@router.post("/login-with-email-code")
def login_with_email_code(payload: EmailCodeVerify, db: Session = Depends(get_db)):
    """
    email + 6桁コードで JWT を発行する。
    """
    ensure_email_login_token_table()
    now = utcnow()
    token = (
        db.query(EmailLoginToken)
        .filter(
            EmailLoginToken.email == payload.email,
            EmailLoginToken.code == payload.code,
            EmailLoginToken.consumed == False,
            EmailLoginToken.expires_at >= now,
        )
        .order_by(EmailLoginToken.created_at.desc())
        .first()
    )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無効なコード、または有効期限切れです。",
        )

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ユーザーが見つかりません。",
        )

    # トークンは一度使ったら無効化
    token.consumed = True
    db.add(token)
    db.commit()

    # 既存の JWT 発行ロジックを利用
    access_token = create_access_token({"sub": user.username})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
    }
