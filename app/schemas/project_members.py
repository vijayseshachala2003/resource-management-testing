from pydantic import BaseModel
from uuid import UUID
from datetime import date
from typing import Optional

# Input
class MemberAssign(BaseModel):
    user_id: UUID
    work_role: str
    assigned_from: date
    assigned_to: Optional[date] = None

# Output
class MemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    project_id: UUID
    work_role: str
    assigned_from: date
    assigned_to: Optional[date]
    is_active: bool
    user_name: Optional[str] = None 

    class Config:
        from_attributes = True