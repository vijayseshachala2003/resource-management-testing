import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

DISABLE_AUTH = os.getenv("DISABLE_AUTH", "true").lower() == "true"


# -------------------------
# DB Dependency
# -------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------
# LOGIN - Supports both Supabase and JWT
# -------------------------
@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Login endpoint that supports both Supabase and JWT authentication.
    Tries Supabase first, then falls back to database password authentication.
    """
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    # Try Supabase authentication first (if enabled)
    auth_method = "jwt"
    if not DISABLE_AUTH:
        try:
            from app.core.supabase_auth import supabase
            if supabase:
                # Try Supabase login
                try:
                    supabase_res = supabase.auth.sign_in_with_password({
                        "email": payload.email,
                        "password": payload.password,
                    })
                    if supabase_res and supabase_res.session:
                        # Supabase auth succeeded - return Supabase token
                        return {
                            "access_token": supabase_res.session.access_token,
                            "refresh_token": supabase_res.session.refresh_token if hasattr(supabase_res.session, 'refresh_token') else None,
                            "token_type": "bearer",
                            "user_id": str(user.id),
                            "user_name": user.name,
                            "user_email": user.email,
                            "user_role": user.role.value,
                            "auth_method": "supabase",
                        }
                except Exception:
                    # Supabase auth failed, continue to JWT
                    pass
        except Exception:
            # Supabase not available, continue to JWT
            pass

    # Fall back to JWT authentication (database password)
    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. This account may require Supabase authentication.",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Create JWT tokens
    access_token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role.value,
        }
    )

    refresh_token = create_refresh_token(
        {
            "sub": str(user.id),
        }
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "user_name": user.name,
        "user_email": user.email,
        "user_role": user.role.value,
        "auth_method": "jwt",
    }


# -------------------------
# REFRESH TOKEN
# -------------------------
@router.post("/refresh")
def refresh_token(payload: RefreshTokenRequest):
    """Refresh JWT access token using refresh token."""
    decoded = decode_token(payload.refresh_token)

    if not decoded or decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = decoded.get("sub")

    access_token = create_access_token(
        {
            "sub": user_id,
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


# -------------------------
# LOGOUT
# -------------------------
@router.post("/logout")
def logout():
    """Logout endpoint (stateless - client deletes tokens)."""
    return {"message": "Logged out successfully"}
