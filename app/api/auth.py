# from fastapi import APIRouter, Depends, HTTPException, status
# from sqlalchemy.orm import Session

# from app.db.session import SessionLocal
# from app.models.user import User
# from app.schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest
# from app.core.security import (
#     verify_password,
#     create_access_token,
#     create_refresh_token,
#     decode_token,
# )

# router = APIRouter(prefix="/auth", tags=["Auth"])


# # -------------------------
# # DB Dependency
# # -------------------------
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # -------------------------
# # LOGIN
# # -------------------------
# @router.post("/login", response_model=TokenResponse)
# def login(payload: LoginRequest, db: Session = Depends(get_db)):
#     user = db.query(User).filter(User.email == payload.email).first()

#     if not user or not verify_password(payload.password, user.password_hash):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid email or password",
#         )

#     if not user.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="User is inactive",
#         )

#     access_token = create_access_token(
#         {
#             "sub": str(user.id),
#             "role": user.role.value,
#         }
#     )

#     refresh_token = create_refresh_token(
#         {
#             "sub": str(user.id),
#         }
#     )

#     return {
#         "access_token": access_token,
#         "refresh_token": refresh_token,
#         "token_type": "bearer",
#         "user_id": str(user.id),
#         "user_name": user.name,
#         "user_email": user.email,
#         "user_role": user.role.value,
#     }


# # -------------------------
# # REFRESH TOKEN
# # -------------------------
# @router.post("/refresh")
# def refresh_token(payload: RefreshTokenRequest):
#     decoded = decode_token(payload.refresh_token)

#     if not decoded or decoded.get("type") != "refresh":
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid refresh token",
#         )

#     user_id = decoded.get("sub")

#     access_token = create_access_token(
#         {
#             "sub": user_id,
#         }
#     )

#     return {
#         "access_token": access_token,
#         "token_type": "bearer",
#     }


# # -------------------------
# # LOGOUT
# # -------------------------
# @router.post("/logout")
# def logout():
#     # Stateless logout (client deletes tokens)
#     return {"message": "Logged out successfully"}
