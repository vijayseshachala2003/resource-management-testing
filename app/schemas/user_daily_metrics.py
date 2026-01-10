from pydantic import BaseModel
from uuid import UUID
from datetime import date
from typing import Optional


class UserDailyMetricsBase(BaseModel):
    user_id: UUID
    project_id: UUID
    work_role: str
    metric_date: date
    hours_worked: float = 0
    tasks_completed: int = 0
    productivity_score: Optional[float] = None
    notes: Optional[str] = None


class UserDailyMetricsCreate(UserDailyMetricsBase):
    pass


class UserDailyMetricsUpdate(BaseModel):
    hours_worked: Optional[float] = None
    tasks_completed: Optional[int] = None
    productivity_score: Optional[float] = None
    notes: Optional[str] = None


class UserDailyMetricsResponse(UserDailyMetricsBase):
    id: UUID

    class Config:
        from_attributes = True
