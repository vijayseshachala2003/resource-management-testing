# app/schemas/project.py
from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime, date

class ProjectCreate(BaseModel):
    code: str
    name: str
    is_active: Optional[bool] = True
    start_date: date 
    end_date: Optional[date] = None

class ProjectResponse(ProjectCreate):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    
    # --- NEW FIELD FOR DASHBOARD LOGIC ---
    current_user_role: Optional[str] = "Contributor"

    class Config:
        from_attributes = True

class ProjectMemberDetail(BaseModel):
    user_id: UUID
    name: str
    email: str
    work_role: str
    is_active: bool
    assigned_from: date
    assigned_to: Optional[date]

    class Config:
        from_attributes = True