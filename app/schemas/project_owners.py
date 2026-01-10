from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

# Input Schema: This is what you send in the POST request
class OwnerAssign(BaseModel):
    user_id: UUID
    work_role: str  # e.g., "PM", "APM"

# Output Schema: This is what the API returns to you
class OwnerResponse(BaseModel):
    id: UUID
    user_id: UUID
    project_id: UUID
    work_role: str
    assigned_at: datetime
    
    # Extra field to show the user's name in the UI
    user_name: Optional[str] = None 

    class Config:
        from_attributes = True