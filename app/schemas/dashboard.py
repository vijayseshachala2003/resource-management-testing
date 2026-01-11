# app/schemas/dashboard.py
from pydantic import BaseModel
from datetime import datetime, date
from uuid import UUID
from typing import Optional

# 1. For the "Big Numbers" Cards (Top of Dashboard)
class GlobalStatsResponse(BaseModel):
    total_users: int
    active_projects: int
    total_hours_today: float
    active_project_names: list[str]

# 2. For the "Live Pulse" (Who is working right now?)
class LiveWorkerResponse(BaseModel):
    user_id: UUID
    user_name: str
    project_name: str
    work_role: str
    clock_in_time: datetime
    current_duration_minutes: int  # Running timer

# 3. For the "Inbox" (Items waiting for approval)
class PendingApprovalResponse(BaseModel):
    history_id: UUID
    user_name: str
    project_name: str
    work_role: str
    sheet_date: date
    clock_in: datetime
    clock_out: Optional[datetime]
    tasks_completed: int
    duration_minutes: float