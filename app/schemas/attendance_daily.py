from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, date
from typing import Optional


# CREATE
class AttendanceDailyCreate(BaseModel):
    user_id: UUID
    project_id: UUID
    attendance_date: date

    status: str
    minutes_late: int = 0

    shift_id: Optional[UUID] = None
    first_clock_in_at: Optional[datetime] = None
    last_clock_out_at: Optional[datetime] = None
    minutes_worked: Optional[float] = None
    request_id: Optional[UUID] = None
    notes: Optional[str] = None

    source: str

# RESPONSE / READ
class AttendanceDailyResponse(BaseModel):
    id: UUID
    user_id: UUID
    project_id: UUID
    attendance_date: date

    shift_id: Optional[UUID]
    status: str
    minutes_late: int

    first_clock_in_at: Optional[datetime]
    last_clock_out_at: Optional[datetime]
    minutes_worked: Optional[float]

    request_id: Optional[UUID]
    notes: Optional[str]
    source: str

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True   # or orm_mode = True (based on repo)


# UPDATE
class AttendanceDailyUpdate(BaseModel):
    attendance_date: Optional[date] = None

    status: Optional[str] = None
    minutes_late: Optional[int] = None

    shift_id: Optional[UUID] = None
    first_clock_in_at: Optional[datetime] = None
    last_clock_out_at: Optional[datetime] = None
    minutes_worked: Optional[float] = None
    request_id: Optional[UUID] = None
    notes: Optional[str] = None
    source: Optional[str] = None