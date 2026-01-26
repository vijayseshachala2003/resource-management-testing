from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional
from uuid import UUID
from datetime import date
from pydantic import BaseModel

from app.db.session import get_db
from app.models.user_daily_metrics import UserDailyMetrics
from app.models.user_quality import UserQuality
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

# =====================================================================
# QUALITY RATINGS ENDPOINT
# =====================================================================

class QualityRatingResponse(BaseModel):
    user_id: UUID
    project_id: UUID
    metric_date: date
    quality_rating: str  # "GOOD", "AVERAGE", "BAD"
    
    class Config:
        from_attributes = True

@router.get("/quality-ratings", response_model=List[QualityRatingResponse])
def get_quality_ratings(
    user_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    Get quality ratings for users/projects in a date range.
    Uses SCD (Slowly Changing Dimension) logic from UserQuality table.
    Returns the quality rating that was valid for each (user, project, date) combination.
    
    This endpoint is designed for dashboard use where you need quality ratings
    for multiple users/projects across a date range.
    """
    # First, get all UserDailyMetrics that match the filters
    metrics_query = db.query(UserDailyMetrics)
    
    if user_id:
        metrics_query = metrics_query.filter(UserDailyMetrics.user_id == user_id)
    if project_id:
        metrics_query = metrics_query.filter(UserDailyMetrics.project_id == project_id)
    if start_date:
        metrics_query = metrics_query.filter(UserDailyMetrics.metric_date >= start_date)
    if end_date:
        metrics_query = metrics_query.filter(UserDailyMetrics.metric_date <= end_date)
    
    metrics = metrics_query.all()
    
    if not metrics:
        return []
    
    # For each metric, find the quality rating that was valid on that date
    results = []
    for metric in metrics:
        target_date = metric.metric_date
        
        # Use SCD logic: find the UserQuality record that was valid on target_date
        quality_record = db.query(UserQuality).filter(
            UserQuality.user_id == metric.user_id,
            UserQuality.project_id == metric.project_id,
            func.date(UserQuality.valid_from) <= target_date
        ).filter(
            or_(
                UserQuality.valid_to == None,
                func.date(UserQuality.valid_to) >= target_date
            )
        ).order_by(UserQuality.valid_from.desc()).first()
        
        rating = "AVERAGE"  # Default
        if quality_record:
            # Convert enum to string
            rating = quality_record.rating.value if hasattr(quality_record.rating, 'value') else str(quality_record.rating)
        
        results.append({
            "user_id": metric.user_id,
            "project_id": metric.project_id,
            "metric_date": target_date,
            "quality_rating": rating
        })
    
    return results
