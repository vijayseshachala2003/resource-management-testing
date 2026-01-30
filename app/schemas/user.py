from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import Optional, List
from datetime import datetime, date
from typing import List
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    USER = "USER"

class UsersAdminSearchFilters(BaseModel):
    """
    Used by ADMIN to fetch user details with filters from the DB.
    Auth account must already exist in Supabase.
    """
    date: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    work_role: Optional[str] = None
    is_active: Optional[bool] = None
    allocated: Optional[bool] = None
    status: Optional[str] = None
    
    page: int = 1
    page_size: int = 10


class WeekoffDays(str, Enum):
    SUNDAY = "SUNDAY"
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"

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

    work_role: Optional[str] = None
    doj: Optional[date] = None
    default_shift_id: Optional[UUID] = None
    rpm_user_id: Optional[UUID] = None
    soul_id: Optional[UUID] = None
    weekoffs: Optional[List[WeekoffDays]] = None  # List to support multiple weekoffs

    created_at: datetime
    updated_at: Optional[datetime] = None

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
    weekoffs: Optional[List[WeekoffDays]] = None

class WeekoffUpdate(BaseModel):
    weekoffs: List[WeekoffDays]  # Support multiple weekoffs

class UserBatchUpdate(BaseModel):
    id: UUID
    changes: UserUpdate

class UserBatchUpdateRequest(BaseModel):
    updates: List[UserBatchUpdate]

class UserQualityUpdate(BaseModel):
    quality_rating: str

class UserSystemUpdate(BaseModel):
    rpm_user_id: Optional[UUID] = None
    soul_id: Optional[UUID] = None

