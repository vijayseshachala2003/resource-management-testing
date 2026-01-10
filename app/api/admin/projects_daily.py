from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from uuid import UUID

from app.db.session import SessionLocal
from app.models.history import TimeHistory
from app.models.project import Project
from app.models.project_metrics import ProjectDailyMetric
from app.schemas.project_metrics import MetricCalculationRequest, ProjectMetricResponse

# We keep the prefix specific so your URL is clean: /admin/metrics/project/...
router = APIRouter(prefix="/admin/projects_daily", tags=["Admin - Metrics"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 1. CALCULATE METRICS ---
# URL: POST /admin/metrics/project/calculate
@router.post("/project/calculate", response_model=list[ProjectMetricResponse])
def calculate_daily_metrics(
    payload: MetricCalculationRequest,
    db: Session = Depends(get_db)
):
    """
    Scans history for a specific project & date, sums up the work, 
    and saves it to the metrics table.
    """
    # 1. Aggregation Query
    raw_stats = db.query(
        TimeHistory.work_role,
        func.count(func.distinct(TimeHistory.user_id)).label("user_count"),
        func.sum(TimeHistory.tasks_completed).label("total_tasks"),
        func.sum(TimeHistory.minutes_worked).label("total_minutes")
    ).filter(
        TimeHistory.project_id == payload.project_id,
        TimeHistory.sheet_date == payload.target_date
    ).group_by(TimeHistory.work_role).all()

    saved_metrics = []
    
    # 2. Upsert Logic
    for row in raw_stats:
        role = row.work_role
        
        # Check if exists
        metric_entry = db.query(ProjectDailyMetric).filter(
            ProjectDailyMetric.project_id == payload.project_id,
            ProjectDailyMetric.metric_date == payload.target_date,
            ProjectDailyMetric.work_role == role
        ).first()

        if not metric_entry:
            metric_entry = ProjectDailyMetric(
                project_id=payload.project_id,
                metric_date=payload.target_date,
                work_role=role
            )
            db.add(metric_entry)

        # Update values
        metric_entry.active_users_count = row.user_count
        metric_entry.tasks_completed = row.total_tasks or 0
        
        total_mins = row.total_minutes or 0
        metric_entry.total_hours_worked = round(total_mins / 60, 2)
        
        saved_metrics.append(metric_entry)

    db.commit()
    
    for m in saved_metrics:
        db.refresh(m)
        
    return saved_metrics


# --- 2. GET REPORT ---
# URL: GET /admin/metrics/project/{project_id}
@router.get("/project/{project_id}", response_model=list[ProjectMetricResponse])
def get_project_metrics(
    project_id: UUID, 
    start_date: date = None,
    end_date: date = None,
    db: Session = Depends(get_db)
):
    query = db.query(ProjectDailyMetric).filter(
        ProjectDailyMetric.project_id == project_id
    )

    if start_date:
        query = query.filter(ProjectDailyMetric.metric_date >= start_date)
    if end_date:
        query = query.filter(ProjectDailyMetric.metric_date <= end_date)
        
    results = query.order_by(ProjectDailyMetric.metric_date.desc()).all()
    
    # Attach project name
    project_name = db.query(Project.name).filter(Project.id == project_id).scalar()
    for r in results:
        r.project_name = project_name
        
    return results