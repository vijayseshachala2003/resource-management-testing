import os
import uuid
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import UUID
from datetime import date

from app.db.session import SessionLocal
from app.models.user import User, UserRole

# ============================================
# AUTH TOGGLE CONFIGURATION
# ============================================
# To DISABLE Supabase Auth: Set DISABLE_AUTH=true in .env
# To ENABLE Supabase Auth:  Set DISABLE_AUTH=false in .env
# Default: DISABLED (true) for development convenience
# ============================================
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "true").lower() == "true"

# Print auth mode on import (for debugging)
if DISABLE_AUTH:
    print("🔓 AUTH MODE: DISABLED (Bypass Mode - No authentication required)")
else:
    print("🔒 AUTH MODE: ENABLED (Supabase Authentication Required)")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================
# TEMPORARY AUTH BYPASS - Supabase Auth Disabled
# ============================================
# Set DISABLE_AUTH=true in .env to use this bypass
# Set DISABLE_AUTH=false to enable Supabase auth
# ============================================

if DISABLE_AUTH:
    def get_current_user(db: Session = Depends(get_db)) -> User:
        """
        AUTH BYPASS MODE - Returns a default admin user.
        No authentication required - all requests use admin@local.dev
        """
        user = db.query(User).filter(User.email == "admin@local.dev").first()

        if not user:
            user = User(
                id=uuid.uuid4(),
                email="admin@local.dev",
                name="Local Admin",
                role=UserRole.ADMIN,
                is_active=True,
                doj=date.today(),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        return user
else:
    # Hybrid Auth Mode - Supports both Supabase and JWT tokens
    from app.core.supabase_auth import get_user_from_token
    from app.core.security import decode_access_token
    
    def get_current_user(
        authorization: str = Header(...),
        db: Session = Depends(get_db),
    ) -> User:
        """
        HYBRID AUTH MODE - Validates both JWT and Supabase tokens.
        Tries JWT first, then falls back to Supabase if JWT validation fails.
        """
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header",
            )

        token = authorization.replace("Bearer ", "")
        
        # Try JWT authentication first
        try:
            decoded = decode_access_token(token)
            if decoded and decoded.get("type") == "access":
                user_id = decoded.get("sub")
                if user_id:
                    user = db.query(User).filter(User.id == user_id).first()
                    if user:
                        if not user.is_active:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="User is inactive",
                            )
                        return user
        except HTTPException:
            # JWT validation failed, try Supabase
            pass
        except Exception:
            # JWT validation failed, try Supabase
            pass
        
        # Fall back to Supabase authentication
        try:
            supabase_user = get_user_from_token(token)
            
            # Try finding user
            user = db.query(User).filter(User.email == supabase_user.email).first()
            
            # Auto-provision user if not exists
            if not user:
                user = User(
                    email=supabase_user.email,
                    name=supabase_user.user_metadata.get("name", supabase_user.email.split("@")[0]),
                    role=UserRole.USER,  # default role
                    is_active=True,
                    doj=date.today(),  # default DOJ
                )
                
                db.add(user)
                db.commit()
                db.refresh(user)
            
            return user
        except Exception:
            # Both JWT and Supabase validation failed
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

