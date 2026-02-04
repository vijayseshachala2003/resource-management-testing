"""
Scheduler Service for Automatic Calculations
Runs productivity, quality, and attendance calculations every 6 hours
"""
import logging
from datetime import date, timedelta, datetime
from typing import List
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.db.session import SessionLocal
from app.models.project import Project
from app.models.history import TimeHistory
from app.models.user_daily_metrics import UserDailyMetrics
from app.models.project_daily_metrics import ProjectDailyMetrics
from app.models.user_project_history import UserProjectHistory
from app.models.project_members import ProjectMember
from app.models.user_quality import UserQuality, QualityRating
from app.models.user import User
from sqlalchemy import func
from uuid import UUID

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Also print to console for visibility
import sys
def log_and_print(message, level='info'):
    """Log and print to ensure visibility"""
    if level == 'info':
        logger.info(message)
        print(f"[SCHEDULER] {message}")
    elif level == 'error':
        logger.error(message)
        print(f"[SCHEDULER ERROR] {message}", file=sys.stderr)
    elif level == 'warning':
        logger.warning(message)
        print(f"[SCHEDULER WARNING] {message}")

# Global scheduler instance
scheduler = BackgroundScheduler()


def calculate_daily_productivity_for_project(project_id: UUID, calculation_date: date, db: Session):
    """
    Standalone function to calculate productivity and quality metrics.
    This is the core logic extracted from analytics.py to be reusable.
    """
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
        # IMPORTANT: Filter by project_id as well since users can work on multiple projects per day
        u_metric = db.query(UserDailyMetrics).filter(
            UserDailyMetrics.user_id == log.user_id,
            UserDailyMetrics.project_id == project_id,
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


def calculate_all_projects_automatically():
    """
    Automatically calculates productivity and quality metrics for all active projects
    for dates that have APPROVED work logs. Only processes APPROVED entries - 
    all tasks must be manually approved before they are included in metrics.
    Processes last 30 days to catch up on any missed calculations and ensure
    all recent data is available for graphs.
    """
    db: Session = SessionLocal()
    try:
        # Get all active projects
        active_projects = db.query(Project).filter(Project.is_active == True).all()
        
        if not active_projects:
            log_and_print("No active projects found for automatic calculation")
            return
        
        # Calculate for last 30 days to catch up on any missed calculations
        # This ensures graphs show data for the past month
        today = date.today()
        dates_to_process = [today - timedelta(days=i) for i in range(30)]
        
        total_processed = 0
        total_skipped = 0
        errors = []
        
        log_and_print(f"Starting automatic calculation for {len(active_projects)} projects and {len(dates_to_process)} dates (last 30 days)")
        
        # Log which projects are being processed
        project_names = [p.name for p in active_projects]
        log_and_print(f"Active projects found: {', '.join(project_names)}")
        
        projects_with_data = set()
        projects_without_data = set()
        
        for project in active_projects:
            project_has_data = False
            project_logs_found = 0
            project_logs_approved = 0
            project_logs_pending = 0
            
            # Quick check: Does this project have ANY logs in the date range?
            total_logs_check = db.query(TimeHistory).filter(
                TimeHistory.project_id == project.id,
                TimeHistory.sheet_date >= dates_to_process[-1],  # Oldest date
                TimeHistory.sheet_date <= dates_to_process[0]    # Newest date
            ).count()
            
            if total_logs_check == 0:
                log_and_print(f"⏭️ Project '{project.name}': No work logs found in last 30 days", level='info')
                projects_without_data.add(project.name)
                continue
            
            # Count log statuses for this project
            approved_count = db.query(TimeHistory).filter(
                TimeHistory.project_id == project.id,
                TimeHistory.sheet_date >= dates_to_process[-1],
                TimeHistory.sheet_date <= dates_to_process[0],
                TimeHistory.status == "APPROVED"
            ).count()
            
            pending_count = db.query(TimeHistory).filter(
                TimeHistory.project_id == project.id,
                TimeHistory.sheet_date >= dates_to_process[-1],
                TimeHistory.sheet_date <= dates_to_process[0],
                TimeHistory.status == "PENDING",
                TimeHistory.clock_out_at.isnot(None)
            ).count()
            
            log_and_print(
                f"📊 Project '{project.name}': {total_logs_check} total logs "
                f"({approved_count} APPROVED, {pending_count} PENDING with clock-out)",
                level='info'
            )
            
            for calc_date in dates_to_process:
                try:
                    # Only check for APPROVED logs - all tasks must be manually approved
                    has_logs = db.query(TimeHistory).filter(
                        TimeHistory.project_id == project.id,
                        TimeHistory.sheet_date == calc_date,
                        TimeHistory.status == "APPROVED",
                        TimeHistory.clock_out_at.isnot(None)  # Only completed sessions
                    ).first()
                    
                    if not has_logs:
                        # Skip if no approved logs
                        continue
                    
                    project_has_data = True
                    
                    # Check if metrics already exist for this date (optional optimization)
                    # We still recalculate to ensure data is up-to-date
                    existing_metrics = db.query(UserDailyMetrics).filter(
                        UserDailyMetrics.project_id == project.id,
                        UserDailyMetrics.metric_date == calc_date
                    ).first()
                    
                    # If metrics exist and were calculated today, skip to save time
                    # Otherwise recalculate to catch any updates
                    if existing_metrics and existing_metrics.updated_at:
                        if existing_metrics.updated_at.date() == today:
                            # Already calculated today, skip
                            continue
                    
                    # Run the calculation
                    result = calculate_daily_productivity_for_project(
                        project_id=project.id,
                        calculation_date=calc_date,
                        db=db
                    )
                    
                    if result.get("status") == "Success":
                        total_processed += 1
                        log_and_print(
                            f"✅ Calculated metrics for project {project.name} on {calc_date}: "
                            f"{result.get('processed_users', 0)} users processed"
                        )
                    elif result.get("status") == "Skipped":
                        total_skipped += 1
                        logger.debug(
                            f"⏭️ Skipped project {project.name} on {calc_date}: {result.get('message', 'No data')}"
                        )
                    else:
                        errors.append(f"Project {project.name} on {calc_date}: {result}")
                        
                except Exception as e:
                    error_msg = f"Error calculating {project.name} on {calc_date}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)
            
            # Track which projects had data
            if project_has_data:
                projects_with_data.add(project.name)
            else:
                projects_without_data.add(project.name)
        
        log_and_print(
            f"Automatic calculation completed: {total_processed} processed, "
            f"{total_skipped} skipped, {len(errors)} errors"
        )
        
        # Log summary of which projects had data
        if projects_with_data:
            log_and_print(f"Projects with data processed: {', '.join(sorted(projects_with_data))}")
        if projects_without_data:
            log_and_print(
                f"Projects with no APPROVED logs (skipped): {', '.join(sorted(projects_without_data))}",
                level='info'
            )
        
        # Log summary of which projects had data
        if projects_with_data:
            log_and_print(f"Projects with data processed: {', '.join(sorted(projects_with_data))}")
        if projects_without_data:
            log_and_print(
                f"Projects with no APPROVED logs (skipped): {', '.join(sorted(projects_without_data))}",
                level='info'
            )
        
        if errors:
            log_and_print(f"Errors during automatic calculation: {errors[:5]}", level='warning')  # Show first 5 errors
            if len(errors) > 5:
                log_and_print(f"... and {len(errors) - 5} more errors", level='warning')
            
    except Exception as e:
        logger.error(f"Critical error in automatic calculation: {str(e)}", exc_info=True)
    finally:
        db.close()


def start_scheduler():
    """Start the background scheduler to run calculations every 6 hours"""
    if scheduler.running:
        logger.warning("Scheduler is already running")
        return
    
    # Schedule the job to run every 6 hours
    scheduler.add_job(
        func=calculate_all_projects_automatically,
        trigger=IntervalTrigger(hours=6),
        id='auto_calculate_metrics',
        name='Automatic Metrics Calculation',
        replace_existing=True,
        max_instances=1  # Prevent overlapping runs
    )
    
    scheduler.start()
    log_and_print("✅ Scheduler started - Automatic calculations will run every 6 hours")
    
    # Run immediately on startup to catch up on any missed calculations
    log_and_print("Running initial calculation on startup...")
    try:
        calculate_all_projects_automatically()
    except Exception as e:
        log_and_print(f"Error in initial calculation: {str(e)}", level='error')
        logger.error(f"Error in initial calculation: {str(e)}", exc_info=True)


def stop_scheduler():
    """Stop the background scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


# For testing or manual triggering
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    calculate_all_projects_automatically()
