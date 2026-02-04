from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from uuid import UUID
from datetime import date

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.project_owners import ProjectOwner
from app.models.project_members import ProjectMember
from app.models.user_daily_metrics import UserDailyMetrics
from app.schemas.project import ProjectResponse
from app.schemas.user import UserResponse
from app.schemas.history import UserProductivityResponse

router = APIRouter(prefix="/project_manager", tags=["Project Manager"])

# --- 1. GET PROJECTS MANAGED BY USER ---
@router.get("/projects", response_model=List[ProjectResponse])
def get_managed_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns list of projects where the current user is a Project Owner.
    If user is ADMIN, returns all projects.
    """
    if current_user.role == UserRole.ADMIN:
        projects = db.query(Project).all()
    else:
        # Get projects assigned to this manager
        projects = (
            db.query(Project)
            .join(ProjectOwner, ProjectOwner.project_id == Project.id)
            .filter(ProjectOwner.user_id == current_user.id)
            .all()
        )
    return projects


# --- 2. GET MEMBERS OF A PROJECT ---
@router.get("/projects/{project_id}/members", response_model=List[UserResponse])
def get_project_members(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns list of active members assigned to a specific project.
    Validates that the current user manages this project (or is Admin).
    """
    # Validation
    if current_user.role != UserRole.ADMIN:
        is_owner = db.query(ProjectOwner).filter(
            ProjectOwner.project_id == project_id,
            ProjectOwner.user_id == current_user.id
        ).first()
        
        if not is_owner:
             raise HTTPException(status_code=403, detail="You do not manage this project.")

    # Fetch active members
    members = (
        db.query(User)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.is_active == True,
            User.is_active == True
        )
        .all()
    )
    return members


# --- 3. GET MEMBER PRODUCTIVITY HISTORY ---
@router.get("/members/{member_id}/productivity", response_model=List[UserProductivityResponse])
def get_member_productivity(
    member_id: UUID,
    project_id: Optional[UUID] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns detailed daily metrics for a specific team member.
    """
    query = db.query(UserDailyMetrics).filter(UserDailyMetrics.user_id == member_id)

    if project_id:
        query = query.filter(UserDailyMetrics.project_id == project_id)

    if start_date:
        query = query.filter(UserDailyMetrics.metric_date >= start_date)
    
    if end_date:
        query = query.filter(UserDailyMetrics.metric_date <= end_date)

    # Order by date desc
    metrics = query.order_by(UserDailyMetrics.metric_date.desc()).all()
    return metrics
