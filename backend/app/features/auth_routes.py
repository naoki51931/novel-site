from fastapi import APIRouter, Depends
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas_api import UserLogin

router = APIRouter()


def _parse_payload(model_cls, payload: dict):
    try:
        return model_cls(**payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.post('/api/auth/login')
def login(payload: dict, db: Session = Depends(get_db)):
    from ..services.auth_service import login_service

    model_payload = _parse_payload(UserLogin, payload)
    return login_service(payload=model_payload, db=db)
