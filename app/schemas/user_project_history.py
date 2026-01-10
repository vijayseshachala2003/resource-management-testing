from pydantic import BaseModel
from uuid import UUID
from datetime import date
from typing import Optional

class UserProjectHistoryResponse(BaseModel):
    user_id: UUID
    project_id: UUID
    work_role: str
    total_hours_worked: float
    total_tasks_completed: int
    first_worked_date: Optional[date]
    last_worked_date: Optional[date]

    class Config:
        from_attributes = True
