from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse
from app.db.session import SessionLocal

router = APIRouter(prefix="/me", tags=["Me"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
