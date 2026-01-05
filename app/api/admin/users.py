from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserResponse
#import hashlib

router = APIRouter(prefix="/admin/users", tags=["Admin - Users"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#def hash_password(password: str) -> str:
  # return hashlib.sha256(password.encode()).hexdigest()

@router.get("/", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@router.post("/", response_model=UserResponse)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    user = User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=UserRole(payload.role)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

from uuid import UUID
from fastapi import HTTPException
from app.schemas.user import UserUpdate

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.name is not None:
        user.name = payload.name

    if payload.role is not None:
        user.role = UserRole(payload.role)

    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}")
def deactivate_user(
    user_id: UUID,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()

    return {"message": "User deactivated successfully"}

from app.core.security import hash_password
