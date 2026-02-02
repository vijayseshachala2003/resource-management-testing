from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from uuid import UUID

from app.db.session import get_db
from app.models.history import TimeHistory
from app.models.user_daily_metrics import UserDailyMetrics
from app.models.project_daily_metrics import ProjectDailyMetrics
from app.models.user_project_history import UserProjectHistory
from app.models.project_members import ProjectMember
# Import your specific UserQuality model
from app.models.user_quality import UserQuality, QualityRating 
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["Analytics Engine"])

@router.post("/calculate-daily")
def calculate_daily_productivity(
    project_id: UUID, 
    calculation_date: date, 
    db: Session = Depends(get_db)
):
    # --- STEP 1: Fetch Logs ---
    daily_logs = db.query(
        TimeHistory.user_id,
        User.name.label("user_name"),
        func.sum(TimeHistory.minutes_worked).label("total_mins"),
        func.sum(TimeHistory.tasks_completed).label("total_tasks")
    ).join(
        User, TimeHistory.user_id == User.id
    ).filter(
        TimeHistory.project_id == project_id,
        TimeHistory.sheet_date == calculation_date,
        TimeHistory.status == "APPROVED" 
    ).group_by(TimeHistory.user_id, User.name).all()

    if not daily_logs:
        return {"status": "Skipped", "message": "No APPROVED work logs found.", "processed": 0}

    # --- STEP 2: Benchmarks ---
    total_project_tasks = sum(log.total_tasks for log in daily_logs)
    total_project_hours = sum(float(log.total_mins or 0) for log in daily_logs) / 60
    active_users = len(daily_logs)
    
    avg_tasks = total_project_tasks / active_users if active_users > 0 else 0
    avg_hours = total_project_hours / active_users if active_users > 0 else 0

    # Save Project Metrics (Standard update)
    p_metric = db.query(ProjectDailyMetrics).filter(
        ProjectDailyMetrics.project_id == project_id,
        ProjectDailyMetrics.metric_date == calculation_date
    ).first()

    if not p_metric:
        p_metric = ProjectDailyMetrics(project_id=project_id, metric_date=calculation_date)
        db.add(p_metric)

    p_metric.tasks_completed = total_project_tasks
    p_metric.active_users_count = active_users
    p_metric.total_hours_worked = total_project_hours
    p_metric.avg_productivity_score = 0
    p_metric.avg_hours_worked_per_user = avg_hours

    # --- STEP 3: Grade Users (Versioning Logic) ---
    bad_threshold = avg_tasks * 0.70 
    total_score_sum = 0
    results_summary = [] 

    for log in daily_logs:
        # 1. Determine Rating
        if log.total_tasks > avg_tasks:
            score = 10.0 
            rating_label = QualityRating.GOOD
        elif log.total_tasks < bad_threshold: 
            score = 3.0  
            rating_label = QualityRating.BAD
        else:
            score = 7.0  
            rating_label = QualityRating.AVERAGE

        total_score_sum += score

        # 2. Update Daily Metrics (Numbers)
        u_metric = db.query(UserDailyMetrics).filter(
            UserDailyMetrics.user_id == log.user_id,
            UserDailyMetrics.metric_date == calculation_date
        ).first()

        member = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == log.user_id
        ).first()
        current_role = member.work_role if member else "UNKNOWN"

        if not u_metric:
            u_metric = UserDailyMetrics(
                user_id=log.user_id, project_id=project_id, 
                metric_date=calculation_date, work_role=current_role
            )
            db.add(u_metric)

        u_metric.hours_worked = float(log.total_mins or 0) / 60
        u_metric.tasks_completed = log.total_tasks
        u_metric.productivity_score = score
        
        # 3. Update Quality (SCD Type 2 Versioning)
        # Find the CURRENT active record
        current_quality = db.query(UserQuality).filter(
            UserQuality.user_id == log.user_id,
            UserQuality.project_id == project_id,
            UserQuality.is_current == True
        ).first()

        # Check if we need to update history or if we just updated it today
        needs_new_version = True
        
        if current_quality:
            # If the record was already updated TODAY, just overwrite it (don't create duplicate history for same day)
            # We compare valid_from date with calculation_date
            if current_quality.valid_from and current_quality.valid_from.date() == calculation_date:
                current_quality.rating = rating_label
                current_quality.quality_score = score
                current_quality.assessed_at = func.now()
                needs_new_version = False
            else:
                # It's an old record. Archive it.
                current_quality.is_current = False
                current_quality.valid_to = func.now()
        
        # Create NEW version if needed
        if needs_new_version:
            new_quality = UserQuality(
                user_id=log.user_id,
                project_id=project_id,
                work_role=current_role,
                rating=rating_label,
                quality_score=score,
                source="AUTO_CALC",
                assessed_at=func.now(),
                is_current=True,
                valid_from=func.now(), # Starts now
                valid_to=None          # Valid indefinitely until next update
            )
            db.add(new_quality)

        # 4. Update History (Last Worked Date)
        history = db.query(UserProjectHistory).filter(
            UserProjectHistory.user_id == log.user_id,
            UserProjectHistory.project_id == project_id
        ).first()

        if not history:
            history = UserProjectHistory(
                user_id=log.user_id, project_id=project_id, 
                work_role=current_role, first_worked_date=calculation_date
            )
            db.add(history)
        history.last_worked_date = calculation_date
        
        results_summary.append({
            "user_name": log.user_name,
            "tasks": log.total_tasks,
            "score": score,
            "rating": rating_label.value
        })

    if active_users > 0:
        p_metric.avg_productivity_score = total_score_sum / active_users

    db.commit()
    
    return {
        "status": "Success", 
        "project_avg_tasks": round(avg_tasks, 2), 
        "bad_threshold": round(bad_threshold, 2),
        "processed_users": active_users,
        "details": results_summary
    }