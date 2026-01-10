from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from uuid import UUID
from datetime import date

from app.db.session import get_db
from app.models.user_daily_metrics import UserDailyMetrics
from app.schemas.user_daily_metrics import (
    UserDailyMetricsCreate,
    UserDailyMetricsResponse
)

router = APIRouter(prefix="/admin/metrics/user_daily", tags=["Metrics"])

@router.post("/", response_model=UserDailyMetricsResponse)
def upsert_daily_metrics(
    payload: UserDailyMetricsCreate,
    db: Session = Depends(get_db),
):
    metrics = db.query(UserDailyMetrics).filter(
        and_(
            UserDailyMetrics.user_id == payload.user_id,
            UserDailyMetrics.project_id == payload.project_id,
            UserDailyMetrics.metric_date == payload.metric_date,
        )
    ).first()

    if metrics:
        # UPDATE
        metrics.hours_worked = payload.hours_worked
        metrics.tasks_completed = payload.tasks_completed
        metrics.productivity_score = payload.productivity_score
        metrics.notes = payload.notes
        metrics.work_role = payload.work_role
    else:
        # INSERT
        metrics = UserDailyMetrics(**payload.model_dump())
        db.add(metrics)

    db.commit()
    db.refresh(metrics)
    return metrics

@router.get("/", response_model=List[UserDailyMetricsResponse])
def get_daily_metrics(
    user_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    query = db.query(UserDailyMetrics)

    if user_id:
        query = query.filter(UserDailyMetrics.user_id == user_id)
    if project_id:
        query = query.filter(UserDailyMetrics.project_id == project_id)
    if start_date:
        query = query.filter(UserDailyMetrics.metric_date >= start_date)
    if end_date:
        query = query.filter(UserDailyMetrics.metric_date <= end_date)

    return query.order_by(UserDailyMetrics.metric_date.desc()).all()

from app.services.user_project_history_service import (
    sync_user_project_history,
)
