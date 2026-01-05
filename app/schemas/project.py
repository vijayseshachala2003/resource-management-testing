from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class ProjectCreate(BaseModel):
    code: str
    name: str
    is_active: Optional[bool] = True

class ProjectResponse(ProjectCreate):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
