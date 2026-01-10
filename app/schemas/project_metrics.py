from pydantic import BaseModel
from uuid import UUID
from datetime import date
from typing import Optional

# Input: "Please calculate the scores for Project Alpha on Jan 8th"
class MetricCalculationRequest(BaseModel):
    project_id: UUID
    target_date: date

# Output: The Report Card
class ProjectMetricResponse(BaseModel):
    id: UUID
    project_id: UUID
    metric_date: date
    work_role: str
    
    tasks_completed: int
    active_users_count: int
    total_hours_worked: float
    
    project_name: Optional[str] = None

    class Config:
        from_attributes = True