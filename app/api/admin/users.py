from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.session import SessionLocal, get_db
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserResponse
from typing import List, Optional
from uuid import UUID
#import hashlib

from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/admin/users",
    tags=["Admin Users"],
    dependencies=[Depends(get_current_user)],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#def hash_password(password: str) -> str:
  # return hashlib.sha256(password.encode()).hexdigest()

@router.get("/", response_model=List[UserResponse])
def list_users(
    name: Optional[str] = None,
    email: Optional[str] = None,
    roles: Optional[List[str]] = Query(None),
    rpm_user_id: Optional[UUID] = None,
    is_active: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(User)

    if name:
        query = query.filter(User.name.ilike(f"%{name}%"))

    if email:
        query = query.filter(User.email.ilike(f"%{email}%"))

    if roles:
        query = query.filter(User.role.in_(roles))

    if rpm_user_id:
        query = query.filter(User.rpm_user_id == rpm_user_id)

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    return (
        query
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


@router.post("/", response_model=UserResponse)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    
    user = User(
        email=payload.email,
        name=payload.name,
        # password_hash=hash_password(payload.password),
        role=UserRole(payload.role),
        work_role=payload.work_role,
        doj=payload.doj,
        default_shift_id=payload.default_shift_id,
    )
    

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

from fastapi import HTTPException, APIRouter, Depends, status
from app.schemas.user import UserQualityUpdate, UserUpdate

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user

@router.patch("/{user_id}/quality-rating", response_model=UserResponse)
def update_quality_rating(
    user_id: UUID,
    payload: UserQualityUpdate,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.quality_rating = payload.quality_rating

    db.commit()
    db.refresh(user)

    return user

from app.schemas.user import UserSystemUpdate
@router.patch("/{user_id}/system", response_model=UserResponse)
def update_system_identifiers(
    user_id: UUID,
    payload: UserSystemUpdate,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

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

# from app.core.security import hash_password
