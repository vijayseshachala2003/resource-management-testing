from sqlalchemy.orm import Session
from uuid import UUID
from datetime import date
from app.models.user_project_history import UserProjectHistory

def sync_user_project_history(
    db: Session,
    user_id: UUID,
    project_id: UUID,
    work_role: str,
    hours: float,
    tasks: int,
    work_date: date,
):
    record = (
        db.query(UserProjectHistory)
        .filter(
            UserProjectHistory.user_id == user_id,
            UserProjectHistory.project_id == project_id,
        )
        .first()
    )

    if not record:
        record = UserProjectHistory(
            user_id=user_id,
            project_id=project_id,
            work_role=work_role,
            total_hours_worked=hours,
            total_tasks_completed=tasks,
            first_worked_date=work_date,
            last_worked_date=work_date,
        )
        db.add(record)
    else:
        record.total_hours_worked += hours
        record.total_tasks_completed += tasks
        record.last_worked_date = work_date

    db.commit()
# app/services/user_project_history.py
def sync_user_project_history(
    db: Session,
    user_id: UUID,
    project_id: UUID,
    work_role: str,
    hours: float,
    tasks: int,
    work_date: date
):
    ...
