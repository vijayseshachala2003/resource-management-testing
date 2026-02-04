from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import UUID
from datetime import date
from typing import Optional
import pandas as pd
import io

from app.db.session import get_db
from app.models.project import Project
from app.models.user import User
from app.models.attendance_daily import AttendanceDaily
from app.models.project_members import ProjectMember
from app.models.user_daily_metrics import UserDailyMetrics
from app.models.user_quality import UserQuality 

router = APIRouter(prefix="/reports", tags=["Reports & Exports"])

# ------------------------------------------------------------------
# 1. DAILY SCORECARD (Used by Analytics Page)
# ------------------------------------------------------------------
@router.get("/project-daily-csv/{project_id}/{date_str}")
def export_project_daily_report(
    project_id: UUID, 
    date_str: str, 
    db: Session = Depends(get_db)
):
    """
    Generates the 'Daily Scorecard' CSV for the Analytics Dashboard.
    Now includes 'Minutes Worked'.
    """
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")

    results = db.query(
        UserDailyMetrics, 
        User.name, 
        User.email
    ).join(
        User, UserDailyMetrics.user_id == User.id
    ).filter(
        UserDailyMetrics.project_id == project_id,
        UserDailyMetrics.metric_date == target_date
    ).all()

    if not results:
        df = pd.DataFrame([{"Message": "No data found for this date"}])
    else:
        data = []
        for row in results:
            metric = row[0]
            name = row[1]
            email = row[2]
            
            # Get Rating (SCD Logic)
            q_record = db.query(UserQuality).filter(
                UserQuality.user_id == metric.user_id,
                UserQuality.project_id == project_id,
                func.date(UserQuality.valid_from) <= target_date
            ).filter(
                or_(
                    UserQuality.valid_to == None,
                    func.date(UserQuality.valid_to) >= target_date
                )
            ).order_by(UserQuality.valid_from.desc()).first()

            rating_text = "N/A"
            if q_record:
                rating_text = q_record.rating.value if hasattr(q_record.rating, 'value') else q_record.rating
            
            # Calculate Minutes
            hours = float(metric.hours_worked or 0)
            minutes = int(hours * 60)

            data.append({
                "User Name": name,
                "Email": email,
                "Role": metric.work_role,
                "Tasks Completed": metric.tasks_completed,
                "Minutes Worked": minutes,   # <--- NEW COLUMN
                "Hours Worked": round(hours, 2),
                "Productivity Score": metric.productivity_score,
                "Rating": rating_text
            })
        
        df = pd.DataFrame(data)

    stream = io.StringIO()
    df.to_csv(stream, index=False)
    
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=Daily_Report_{date_str}.csv"
    return response


# ------------------------------------------------------------------
# 2. ROLE DRILLDOWN (Daily Roster)
# ------------------------------------------------------------------
@router.get("/role-drilldown")
def export_role_drilldown(
    report_date: date,
    project_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    data = []
    
    if project_id:
        # Single project mode
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(404, "Project not found")

        members = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.is_active == True
        ).join(User, ProjectMember.user_id == User.id).all()

        for m in members:
            att = db.query(AttendanceDaily).filter(
                AttendanceDaily.user_id == m.user_id,
                AttendanceDaily.attendance_date == report_date
            ).first()

            minutes = att.minutes_worked if att else 0
            hours = round(minutes / 60, 2) if minutes else 0

            # Get tasks completed for this user on this date for this project
            metrics = db.query(UserDailyMetrics).filter(
                UserDailyMetrics.user_id == m.user_id,
                UserDailyMetrics.project_id == project_id,
                UserDailyMetrics.metric_date == report_date
            ).first()
            
            tasks_completed = metrics.tasks_completed if metrics else 0

            # Check if date is user's weekoff
            attendance_status = "ABSENT"
            if att:
                attendance_status = att.status
            else:
                # Check if it's a weekoff day (supports multiple weekoffs)
                user = m.user
                if user.weekoffs:
                    weekday_name = report_date.strftime("%A").upper()  # "SUNDAY", "MONDAY", etc.
                    # Check if weekday matches any of the user's weekoffs (array of enums)
                    weekoff_values = [w.value if hasattr(w, 'value') else str(w) for w in user.weekoffs]
                    if weekday_name in weekoff_values:
                        attendance_status = "WEEKOFF"

            row = {
                "project_code": project.code,
                "project_name": project.name,
                "date": report_date,
                "role": m.work_role,
                "user_name": m.user.name,
                "email": m.user.email,
                "attendance_status": attendance_status,
                "tasks_completed": tasks_completed,
                "minutes_worked": minutes,
                "hours_worked": hours
            }
            data.append(row)
    else:
        # All projects mode
        all_projects = db.query(Project).all()
        project_map = {p.id: p for p in all_projects}
        
        # Get all active project members across all projects
        all_members = db.query(ProjectMember).filter(
            ProjectMember.is_active == True
        ).join(User, ProjectMember.user_id == User.id).all()

        # Process each member
        for m in all_members:
            project = project_map.get(m.project_id)
            if not project:
                continue
                
            att = db.query(AttendanceDaily).filter(
                AttendanceDaily.user_id == m.user_id,
                AttendanceDaily.attendance_date == report_date
            ).first()

            minutes = att.minutes_worked if att else 0
            hours = round(minutes / 60, 2) if minutes else 0

            # Get tasks completed for this user on this date for this project
            metrics = db.query(UserDailyMetrics).filter(
                UserDailyMetrics.user_id == m.user_id,
                UserDailyMetrics.project_id == m.project_id,
                UserDailyMetrics.metric_date == report_date
            ).first()
            
            tasks_completed = metrics.tasks_completed if metrics else 0

            # Check if date is user's weekoff
            attendance_status = "ABSENT"
            if att:
                attendance_status = att.status
            else:
                # Check if it's a weekoff day (supports multiple weekoffs)
                user = m.user
                if user.weekoffs:
                    weekday_name = report_date.strftime("%A").upper()
                    weekoff_values = [w.value if hasattr(w, 'value') else str(w) for w in user.weekoffs]
                    if weekday_name in weekoff_values:
                        attendance_status = "WEEKOFF"

            row = {
                "project_code": project.code,
                "project_name": project.name,
                "date": report_date,
                "role": m.work_role,
                "user_name": m.user.name,
                "email": m.user.email,
                "attendance_status": attendance_status,
                "tasks_completed": tasks_completed,
                "minutes_worked": minutes,
                "hours_worked": hours
            }
            data.append(row)

    df = pd.DataFrame(data)
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        filename = f"roster_{project.code}_{report_date}.csv"
    else:
        filename = f"roster_all_projects_{report_date}.csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


# ------------------------------------------------------------------
# 3. PROJECT ALL-TIME HISTORY
# ------------------------------------------------------------------
@router.get("/project-history")
def export_project_history(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    metrics = db.query(UserDailyMetrics).filter(UserDailyMetrics.project_id == project_id).all()
    
    if not metrics:
        return StreamingResponse(iter(["No data available"]), media_type="text/csv")

    user_map = {}
    for m in metrics:
        if m.user_id not in user_map:
            user_map[m.user_id] = {"hours": 0, "tasks": 0, "scores": [], "dates": []}
        
        user_map[m.user_id]["hours"] += float(m.hours_worked or 0)
        user_map[m.user_id]["tasks"] += (m.tasks_completed or 0)
        if m.productivity_score:
            user_map[m.user_id]["scores"].append(float(m.productivity_score))
        user_map[m.user_id]["dates"].append(m.metric_date)

    summary_data = []
    for uid, stats in user_map.items():
        user = db.query(User).get(uid)
        avg_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
        
        total_hours = stats["hours"]
        total_minutes = int(total_hours * 60)

        summary_data.append({
            "project_name": project.name,
            "user_name": user.name,
            "email": user.email,
            "total_minutes": total_minutes, # <--- NEW COLUMN
            "total_hours": round(total_hours, 2),
            "total_tasks": stats["tasks"],
            "avg_score": round(avg_score, 2)
        })

    df = pd.DataFrame(summary_data)
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=history_{project.code}.csv"
    return response


# ------------------------------------------------------------------
# 4. USER PERFORMANCE REPORT
# ------------------------------------------------------------------
@router.get("/user-performance")
def export_user_performance(
    user_id: UUID,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db)
):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    metrics = db.query(UserDailyMetrics).filter(
        UserDailyMetrics.user_id == user_id,
        UserDailyMetrics.metric_date >= start_date,
        UserDailyMetrics.metric_date <= end_date
    ).order_by(UserDailyMetrics.metric_date).all()
    
    data = []
    for m in metrics:
        proj = db.query(Project).get(m.project_id)
        
        target_date = m.metric_date
        q_record = db.query(UserQuality).filter(
            UserQuality.user_id == user_id,
            UserQuality.project_id == m.project_id,
            func.date(UserQuality.valid_from) <= target_date
        ).filter(
            or_(
                UserQuality.valid_to == None,
                func.date(UserQuality.valid_to) >= target_date
            )
        ).order_by(UserQuality.valid_from.desc()).first()
        
        rating_text = "N/A"
        accuracy_value = None
        critical_rate_value = None
        
        if q_record:
            rating_text = q_record.rating.value if hasattr(q_record.rating, 'value') else q_record.rating
            accuracy_value = float(q_record.accuracy) if q_record.accuracy is not None else None
            critical_rate_value = float(q_record.critical_rate) if q_record.critical_rate is not None else None

        hours = float(m.hours_worked or 0)
        minutes = int(hours * 60)

        data.append({
            "Date": m.metric_date,
            "Project": proj.name if proj else "N/A",
            "Role": m.work_role,
            "Tasks": m.tasks_completed,
            "Minutes Worked": minutes,
            "Hours Worked": round(hours, 2),
            "Productivity Score": m.productivity_score,
            "Quality Rating": rating_text,
            "Accuracy": round(accuracy_value, 2) if accuracy_value is not None else "N/A",
            "Critical Rate": round(critical_rate_value, 2) if critical_rate_value is not None else "N/A"
        })

    df = pd.DataFrame(data)
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=report_{user.name}_{start_date}.csv"
    return response