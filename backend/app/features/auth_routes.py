from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter()


@router.post('/api/auth/login')
def login(payload: dict, db: Session = Depends(get_db)):
    from .. import main as legacy
    model_payload = legacy.UserLogin(**payload)
    return legacy.login(model_payload, db=db)
