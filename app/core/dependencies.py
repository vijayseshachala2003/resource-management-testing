from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date

from app.core.supabase_auth import get_user_from_token
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
        )

    token = authorization.replace("Bearer ", "")
    supabase_user = get_user_from_token(token)

    # Try finding user
    user = db.query(User).filter(User.email == supabase_user.email).first()

    # 🔥 AUTO-PROVISION USER IF NOT EXISTS
    if not user:
        user = User(
            email=supabase_user.email,
            name=supabase_user.user_metadata.get("name", supabase_user.email.split("@")[0]),
            role=UserRole.USER,          # default role
            is_active=True,
            doj=date.today(),             # default DOJ
        )

        db.add(user)
        db.commit()
        db.refresh(user)

    return user
