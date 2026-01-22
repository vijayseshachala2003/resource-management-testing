from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import Optional
from datetime import datetime, date
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"

class WorkRole(str, Enum):
    CONTRACTOR = "CONTRACTOR"
    EMPLOYEE = "EMPLOYEE"

class UserCreate(BaseModel):
    """
    Used by ADMIN to create a user record in backend DB.
    Auth account must already exist in Supabase.
    """
    email: EmailStr
    name: str
    role: UserRole
    work_role: Optional[str] = None
    doj: Optional[date] = None
    default_shift_id: Optional[UUID] = None
    rpm_user_id: Optional[UUID] = None
    soul_id: Optional[UUID] = None

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    name: str
    role: UserRole
    is_active: bool

    work_role: Optional[str]
    doj: Optional[date]
    default_shift_id: Optional[UUID]
    quality_rating: Optional[str]
    rpm_user_id: Optional[UUID]
    soul_id: Optional[UUID]

    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None

    work_role: Optional[str] = None
    doj: Optional[date] = None
    default_shift_id: Optional[UUID] = None
    rpm_user_id: Optional[UUID] = None
    soul_id: Optional[UUID] = None

class UserQualityUpdate(BaseModel):
    quality_rating: str

class UserSystemUpdate(BaseModel):
    rpm_user_id: Optional[UUID] = None
    soul_id: Optional[UUID] = None

