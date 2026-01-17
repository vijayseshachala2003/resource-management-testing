from pydantic import BaseModel
from uuid import UUID
from datetime import date, time, datetime
from typing import Optional


class AttendanceRequestBase(BaseModel):
    project_id: Optional[UUID] = None
    request_type: str

    start_date: date
    end_date: date

    start_time: Optional[time] = None
    end_time: Optional[time] = None

    reason: Optional[str] = None
    attachment_url: Optional[str] = None


class AttendanceRequestCreate(AttendanceRequestBase):
    pass  # it inherits everything from AttendanceRequestBase.


class AttendanceRequestUpdate(BaseModel):
    project_id: Optional[UUID] = None
    request_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    reason: Optional[str] = None
    attachment_url: Optional[str] = None
    status: Optional[str] = "PENDING"
    view_content: Optional[str] = None


class AttendanceRequestResponse(AttendanceRequestBase):
    id: UUID
    user_id: UUID
    status: str

    requested_at: datetime
    created_at: datetime
    updated_at: datetime

    reviewed_by_user_id : Optional[UUID]
    reviewed_at: Optional[datetime]
    review_comment: Optional[str]
    
    class Config:
        from_attributes = True