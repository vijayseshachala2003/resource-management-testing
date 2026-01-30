from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user_id: str
    user_name: str
    user_email: str
    user_role: str
    auth_method: str = "jwt"  # "jwt" or "supabase"


class RefreshTokenRequest(BaseModel):
    refresh_token: str