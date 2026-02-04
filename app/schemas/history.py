from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, date
from typing import Optional

# 1. Clock In Request
class ClockInRequest(BaseModel):
    project_id: UUID
    work_role: str  # Must match your Enum (e.g., "ANNOTATION")
    clock_in_at: Optional[datetime] = None

# 2. Clock Out Request
class ClockOutRequest(BaseModel):
    tasks_completed: int
    notes: Optional[str] = None

# 3. Response Model (What the UI sees)
class TimeHistoryResponse(BaseModel):
    id: UUID
    user_id: UUID
    project_id: UUID
    work_role: str
    status: str
   
    minutes_worked: Optional[float] = None
    
    sheet_date: date
    clock_in_at: datetime
    clock_out_at: Optional[datetime]
    
    tasks_completed: int
    notes: Optional[str]
    
    # Helper fields for UI
    project_name: Optional[str] = None
    
    class Config:
        from_attributes = True
# Add this class to your existing file
class ApprovalRequest(BaseModel):
    status: str  # Must be "APPROVED" or "REJECTED"
    approval_comment: Optional[str] = None

class UserProductivityResponse(BaseModel):
    id: UUID
    user_id: UUID
    project_id: UUID
    work_role: str
    metric_date: date
    hours_worked: float
    tasks_completed: int
    productivity_score: Optional[float] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True