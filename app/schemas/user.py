from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import Optional
from datetime import datetime
from datetime import date
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: UserRole
    work_role: Optional[str] = None
    doj: Optional[date] = None
    default_shift_id: Optional[UUID] = None

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

    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

from typing import Optional
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"

class UserUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    work_role: Optional[str] = None
    doj: Optional[date] = None
    default_shift_id: Optional[UUID] = None

class UserQualityUpdate(BaseModel):
    quality_rating: str

class UserSystemUpdate(BaseModel):
    rpm_user_id: Optional[UUID] = None
    soul_id: Optional[UUID] = None

class UserPasswordUpdate(BaseModel):
    old_password: str
    new_password: str
