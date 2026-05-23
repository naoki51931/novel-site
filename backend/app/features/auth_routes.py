from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter()


@router.post('/api/auth/login')
def login(payload: dict, db: Session = Depends(get_db)):
    from .. import main as legacy
    from ..services.auth_service import login_service

    model_payload = legacy.UserLogin(**payload)
    return login_service(payload=model_payload, db=db)
