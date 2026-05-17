from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..features.auth_routes import router as auth_feature_router
from ..database import get_db


def create_access_token(data: dict) -> str:
    from .. import main as legacy

    return legacy.create_access_token(data)


from .two_factor import router as two_factor_router


router = APIRouter()
router.include_router(auth_feature_router)
router.include_router(two_factor_router)


def _parse_payload(model_cls, payload: dict):
    try:
        return model_cls(**payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.post("/api/auth/register/email/start")
def start_register_email_verification(payload: dict, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.RegisterEmailStartRequest, payload)
    return legacy.start_register_email_verification(model_payload, request=request, db=db)


@router.post("/api/auth/register")
def register_user(payload: dict, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.UserCreate, payload)
    return legacy.register_user(model_payload, db=db)


@router.post("/api/auth/password-reset/request")
def password_reset_request(payload: dict, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.PasswordResetRequest, payload)
    return legacy.password_reset_request(model_payload, db=db)


@router.post("/api/auth/password-reset/confirm")
def password_reset_confirm(payload: dict, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.PasswordResetConfirm, payload)
    return legacy.password_reset_confirm(model_payload, db=db)


@router.get("/api/auth/oauth/{provider}/start")
async def oauth_start(
    provider: str,
    redirect: str | None = None,
    client: str | None = Query(None),
    direct: int | None = Query(0),
    request: Request = None,
):
    from .. import main as legacy

    return await legacy.oauth_start(
        provider=provider,
        redirect=redirect,
        client=client,
        direct=direct,
        request=request,
    )


@router.get("/api/auth/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str | None = None,
    state: str | None = None,
    oauth_token: str | None = None,
    oauth_verifier: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    request: Request = None,
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    return await legacy.oauth_callback(
        provider=provider,
        code=code,
        state=state,
        oauth_token=oauth_token,
        oauth_verifier=oauth_verifier,
        error=error,
        error_description=error_description,
        request=request,
        db=db,
    )


@router.post("/api/admin/auth/login")
def admin_login(payload: dict, request: Request, response: Response):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.AdminLoginRequest, payload)
    return legacy.admin_login(model_payload, request=request, response=response)


@router.post("/api/admin/auth/logout")
def admin_logout(response: Response):
    from .. import main as legacy

    return legacy.admin_logout(response=response)


@router.get("/api/admin/auth/me")
def admin_me(request: Request, response: Response):
    from .. import main as legacy

    return legacy.admin_me(request=request, response=response)


@router.post("/api/auth/login/start")
def login_start(payload: dict, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.UserLogin, payload)
    return legacy.login_start(model_payload, request=request, db=db)


@router.post("/api/auth/login/verify")
def login_verify(payload: dict, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.LoginVerify, payload)
    return legacy.login_verify(model_payload, db=db)
