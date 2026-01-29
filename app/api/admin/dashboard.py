# app/api/admin/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime

from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.history import TimeHistory
from app.models.project_owners import ProjectOwner
from app.schemas.dashboard import (
    GlobalStatsResponse, 
    LiveWorkerResponse, 
    PendingApprovalResponse
)
from app.core.dependencies import get_current_user

# Define the Router
router = APIRouter(prefix="/admin/dashboard", tags=["Admin - Dashboard"])

# Database Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/stats", response_model=GlobalStatsResponse)
def get_global_stats(db: Session = Depends(get_db)):
    """
    Returns the high-level metrics for the top of the dashboard.
    """
    # 1. Count Total Users
    total_users = db.query(User).count()

    # 2. Count Active Projects
    active_projects = db.query(Project).filter(Project.is_active == True).count()

    # 3. Sum Hours Worked Today
    today_minutes = db.query(func.sum(TimeHistory.minutes_worked)).filter(
        TimeHistory.sheet_date == date.today()
    ).scalar() or 0  # .scalar() handles the case where no work happened yet
    
    total_hours = round(today_minutes / 60, 1)
    active_projects_query = db.query(Project.name).filter(Project.is_active == True).all()
    
    

  
    active_names = [row.name for row in active_projects_query]

    return GlobalStatsResponse(
        total_users=total_users,
        active_projects=active_projects,
        total_hours_today=total_hours,
        active_project_names=active_names
       
    )

@router.get("/live", response_model=list[LiveWorkerResponse])
def get_live_workers(db: Session = Depends(get_db)):
    """
    Returns a list of users who have Clocked In but NOT Clocked Out.
    """
    # Find active sessions (Clock Out is None)
    active_sessions = db.query(TimeHistory).filter(
        TimeHistory.clock_out_at == None
    ).all()

    results = []
    now = datetime.now()

    for session in active_sessions:
        # Calculate how long they have been running (in minutes)
        duration = 0
        if session.clock_in_at:
            # Simple difference between NOW and Start Time
            delta = now - session.clock_in_at
            duration = int(delta.total_seconds() / 60)

        results.append(LiveWorkerResponse(
            user_id=session.user_id,
            user_name=session.user.name if session.user else "Unknown",
            project_name=session.project.name if session.project else "Unknown",
            work_role=session.work_role,
            clock_in_time=session.clock_in_at,
            current_duration_minutes=duration
        ))

    return results


@router.get("/pending-approvals", response_model=list[PendingApprovalResponse])
def get_pending_approvals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns completed sessions that are waiting for manager approval.
    Only shows approvals for projects where the current user is a project manager or admin.
    """
    # Base query for pending items
    query = db.query(TimeHistory).filter(
        TimeHistory.status == "PENDING",
        TimeHistory.clock_out_at != None
    )
    
    # Filter by project manager or admin
    if current_user.role == UserRole.ADMIN:
        # Admin sees all pending approvals
        pending_items = query.order_by(TimeHistory.clock_in_at.desc()).all()
    else:
        # Project managers only see approvals for their projects
        # Get list of project IDs where current user is a project owner
        managed_projects = db.query(ProjectOwner.project_id).filter(
            ProjectOwner.user_id == current_user.id
        ).all()
        managed_project_ids = [p[0] for p in managed_projects]
        
        if not managed_project_ids:
            # User is not a project manager, return empty list
            return []
        
        # Filter approvals to only show those from managed projects
        pending_items = query.filter(
            TimeHistory.project_id.in_(managed_project_ids)
        ).order_by(TimeHistory.clock_in_at.desc()).all()
    
    results = []
    for item in pending_items:
        # Calculate Duration from stored minutes or timestamps
        duration = 0.0
        if item.minutes_worked:
            duration = float(item.minutes_worked)
        elif item.clock_out_at and item.clock_in_at:
             duration = (item.clock_out_at - item.clock_in_at).total_seconds() / 60.0

        results.append(PendingApprovalResponse(
            history_id=item.id,
            user_name=item.user.name if item.user else "Unknown",
            project_name=item.project.name if item.project else "Unknown",
            work_role=item.work_role,
            sheet_date=item.sheet_date,
            clock_in=item.clock_in_at,
            clock_out=item.clock_out_at,
            tasks_completed=item.tasks_completed,
            duration_minutes=round(duration, 1)
        ))
        
    return results
