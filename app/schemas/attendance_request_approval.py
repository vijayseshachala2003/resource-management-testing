from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime
from enum import Enum


class AttendanceApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AttendanceRequestApprovalBase(BaseModel):
    request_id: UUID
    approver_user_id: UUID
    decision: AttendanceApprovalDecision
    comment: Optional[str] = None


class AttendanceRequestApprovalCreate(AttendanceRequestApprovalBase):
    decided_at: Optional[datetime] = None


class AttendanceRequestApprovalUpdate(BaseModel):
    decision: Optional[AttendanceApprovalDecision] = None
    comment: Optional[str] = None


class AttendanceRequestApprovalResponse(AttendanceRequestApprovalBase):
    id: UUID
    decided_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
