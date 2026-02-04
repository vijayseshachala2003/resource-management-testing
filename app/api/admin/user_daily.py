from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional
from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel

from app.db.session import get_db
from app.models.user_daily_metrics import UserDailyMetrics
from app.models.user_quality import UserQuality, QualityRating
from app.models.user import User
from app.models.project_members import ProjectMember
from app.core.dependencies import get_current_user
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
    quality_rating: Optional[str] = None  # "GOOD", "AVERAGE", "BAD", or None if not assessed
    quality_score: Optional[float] = None  # Numeric score (0-10) or None
    accuracy: Optional[float] = None  # Accuracy percentage (0-100) or None
    critical_rate: Optional[float] = None  # Critical rate percentage (0-100) or None
    source: Optional[str] = None  # "MANUAL" or "AUTO_CALC"
    assessed_by: Optional[UUID] = None  # User who assessed the quality
    notes: Optional[str] = None  # Assessment notes
    
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
    
    This endpoint returns quality assessments even if there's no corresponding UserDailyMetrics record.
    It queries UserQuality directly to show manual assessments.
    """
    results = []
    seen_combinations = set()  # Track (user_id, project_id, date) to avoid duplicates
    
    # First, get quality ratings from UserQuality table directly
    # This ensures manual quality assessments show up even without daily metrics
    quality_query = db.query(UserQuality).filter(
        UserQuality.is_current == True
    )
    
    if user_id:
        quality_query = quality_query.filter(UserQuality.user_id == user_id)
    if project_id:
        quality_query = quality_query.filter(UserQuality.project_id == project_id)
    
    # Get all current quality records
    quality_records = quality_query.all()
    
    # For each quality record, use the valid_from date as the metric_date
    # This shows the date the quality assessment applies to (the date it was assessed for)
    for quality_record in quality_records:
        # Use valid_from date as that's when the quality assessment becomes valid
        if quality_record.valid_from:
            target_date = quality_record.valid_from.date()
        else:
            continue  # Skip if no date available
        
        # Apply date filters if provided
        if start_date and target_date < start_date:
            continue
        if end_date and target_date > end_date:
            continue
        
        key = (quality_record.user_id, quality_record.project_id, target_date)
        if key not in seen_combinations:
            seen_combinations.add(key)
            rating = quality_record.rating.value if hasattr(quality_record.rating, 'value') else str(quality_record.rating)
            results.append({
                "user_id": quality_record.user_id,
                "project_id": quality_record.project_id,
                "metric_date": target_date,
                "quality_rating": rating,
                "quality_score": float(quality_record.quality_score) if quality_record.quality_score else None,
                "accuracy": float(quality_record.accuracy) if quality_record.accuracy else None,
                "critical_rate": float(quality_record.critical_rate) if quality_record.critical_rate else None,
                "source": quality_record.source,
                "assessed_by": quality_record.assessed_by_user_id,
                "notes": quality_record.notes
            })
    
    # Also get quality ratings for dates that have UserDailyMetrics (for backward compatibility)
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
    
    # For each metric, find the quality rating that was valid on that date
    for metric in metrics:
        target_date = metric.metric_date
        key = (metric.user_id, metric.project_id, target_date)
        
        # Skip if we already have this combination from UserQuality query
        if key in seen_combinations:
            continue
        
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
        
        # Quality is manually assessed - return None if not assessed
        if quality_record:
            rating = quality_record.rating.value if hasattr(quality_record.rating, 'value') else str(quality_record.rating)
            quality_score = float(quality_record.quality_score) if quality_record.quality_score else None
            accuracy = float(quality_record.accuracy) if quality_record.accuracy else None
            critical_rate = float(quality_record.critical_rate) if quality_record.critical_rate else None
            source = quality_record.source
            assessed_by = quality_record.assessed_by_user_id
            notes = quality_record.notes
        else:
            # No quality assessment exists - return None values
            rating = None
            quality_score = None
            accuracy = None
            critical_rate = None
            source = None
            assessed_by = None
            notes = None
        
        seen_combinations.add(key)
        results.append({
            "user_id": metric.user_id,
            "project_id": metric.project_id,
            "metric_date": target_date,
            "quality_rating": rating,
            "quality_score": quality_score,
            "accuracy": accuracy,
            "critical_rate": critical_rate,
            "source": source,
            "assessed_by": assessed_by,
            "notes": notes
        })
    
    # Sort by date descending
    results.sort(key=lambda x: x["metric_date"], reverse=True)
    
    return results

# =====================================================================
# QUALITY ASSESSMENT ENDPOINT
# =====================================================================

class QualityAssessmentCreate(BaseModel):
    user_id: UUID
    project_id: UUID
    metric_date: date
    rating: str  # "GOOD", "AVERAGE", "BAD"
    quality_score: Optional[float] = None  # 0-10
    accuracy: Optional[float] = None  # Accuracy percentage (0-100)
    critical_rate: Optional[float] = None  # Critical rate percentage (0-100)
    notes: Optional[str] = None
    work_role: Optional[str] = None  # Will be fetched from project_members if not provided

class QualityAssessmentResponse(BaseModel):
    id: UUID
    user_id: UUID
    project_id: UUID
    rating: str
    quality_score: Optional[float]
    accuracy: Optional[float]  # Accuracy percentage (0-100)
    critical_rate: Optional[float]  # Critical rate percentage (0-100)
    notes: Optional[str]
    source: str
    assessed_by_user_id: Optional[UUID]
    assessed_at: datetime
    is_current: bool
    valid_from: datetime
    valid_to: Optional[datetime]
    
    class Config:
        from_attributes = True

@router.post("/quality", response_model=QualityAssessmentResponse)
def create_quality_assessment(
    payload: QualityAssessmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create or update a quality assessment for a user on a specific date.
    Uses SCD Type 2 versioning - archives old record and creates new one.
    """
    # Get current user (assessor)
    assessed_by = current_user.id
    
    # Get work_role from project_members if not provided
    work_role = payload.work_role
    if not work_role:
        member = db.query(ProjectMember).filter(
            ProjectMember.user_id == payload.user_id,
            ProjectMember.project_id == payload.project_id
        ).first()
        if member:
            work_role = member.work_role
        else:
            work_role = "UNKNOWN"
    
    # Validate rating
    try:
        rating_enum = QualityRating(payload.rating.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid rating. Must be one of: {[r.value for r in QualityRating]}"
        )
    
    # Validate quality_score if provided
    if payload.quality_score is not None:
        if payload.quality_score < 0 or payload.quality_score > 10:
            raise HTTPException(
                status_code=400,
                detail="Quality score must be between 0 and 10"
            )
    
    # Validate accuracy if provided
    if payload.accuracy is not None:
        if payload.accuracy < 0 or payload.accuracy > 100:
            raise HTTPException(
                status_code=400,
                detail="Accuracy must be between 0 and 100"
            )
    
    # Validate critical_rate if provided
    if payload.critical_rate is not None:
        if payload.critical_rate < 0 or payload.critical_rate > 100:
            raise HTTPException(
                status_code=400,
                detail="Critical rate must be between 0 and 100"
            )
    
    # Find existing current quality record
    current_quality = db.query(UserQuality).filter(
        UserQuality.user_id == payload.user_id,
        UserQuality.project_id == payload.project_id,
        UserQuality.is_current == True
    ).first()
    
    # Archive existing record if it exists
    if current_quality:
        current_quality.is_current = False
        current_quality.valid_to = datetime.now()
    
    # Create new quality record
    # Use metric_date for valid_from so the quality assessment applies to the selected date
    # Convert metric_date (date) to datetime at start of day
    valid_from_datetime = datetime.combine(payload.metric_date, datetime.min.time())
    
    new_quality = UserQuality(
        user_id=payload.user_id,
        project_id=payload.project_id,
        work_role=work_role,
        rating=rating_enum,
        quality_score=payload.quality_score,
        accuracy=payload.accuracy,
        critical_rate=payload.critical_rate,
        notes=payload.notes,
        source="MANUAL",
        assessed_by_user_id=assessed_by,
        assessed_at=datetime.now(),  # When it was assessed (now)
        is_current=True,
        valid_from=valid_from_datetime,  # When it becomes valid (the metric_date)
        valid_to=None
    )
    
    db.add(new_quality)
    db.commit()
    db.refresh(new_quality)
    
    # Return response
    return QualityAssessmentResponse(
        id=new_quality.id,
        user_id=new_quality.user_id,
        project_id=new_quality.project_id,
        rating=new_quality.rating.value,
        quality_score=float(new_quality.quality_score) if new_quality.quality_score else None,
        accuracy=float(new_quality.accuracy) if new_quality.accuracy else None,
        critical_rate=float(new_quality.critical_rate) if new_quality.critical_rate else None,
        notes=new_quality.notes,
        source=new_quality.source,
        assessed_by_user_id=new_quality.assessed_by_user_id,
        assessed_at=new_quality.assessed_at,
        is_current=new_quality.is_current,
        valid_from=new_quality.valid_from,
        valid_to=new_quality.valid_to,
    )
