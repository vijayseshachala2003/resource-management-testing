from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserPasswordUpdate
from app.core.dependencies import get_current_user
from app.core.security import verify_password, hash_password

router = APIRouter(prefix="/me", tags=["Me"])


@router.get("/", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user

@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: UserPasswordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect",
        )

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()

    return