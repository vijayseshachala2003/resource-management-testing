from fastapi import Depends, Header, HTTPException, status
from app.core.supabase_auth import get_user_from_token
from app.db.session import SessionLocal
from app.models.user import User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    authorization: str = Header(...),
    db=Depends(get_db),
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
        )

    token = authorization.replace("Bearer ", "")
    supabase_user = get_user_from_token(token)

    user = db.query(User).filter(User.email == supabase_user.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not registered in system",
        )

    return user
