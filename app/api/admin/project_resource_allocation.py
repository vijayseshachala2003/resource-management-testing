from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, aliased

from app.core.dependencies import get_current_user, get_db
from app.models.project_members import ProjectMember
from app.models.user import User
from app.models.attendance_daily import AttendanceDaily
from app.models.shift import Shift
from app.models.history import TimeHistory

router = APIRouter(
    prefix="/admin/project-resource-allocation",
    tags=["Admin - Dashboard"],
)


@router.get("/")
def project_resource_allocation(
    project_id: str = Query(..., description="Project UUID"),
    target_date: date = Query(date.today()),
    only_active: bool = Query(True),
    only_pm_apm: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns resource allocation snapshot for a project on a given date.

    Tables involved:
    - project_members
    - users (employee + reporting manager)
    - attendance_daily
    - shifts (via users.default_shift_id)
    """
    
    # Convert string project_id to UUID for proper filtering
    try:
        project_id_uuid = UUID(project_id)
    except (ValueError, TypeError):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid project_id format: {project_id}"
        )

    Manager = aliased(User)

    query = (
        db.query(
            ProjectMember,
            User,
            Manager,
            AttendanceDaily,
            Shift,
        )
        .join(User, ProjectMember.user_id == User.id)
        .outerjoin(Manager, User.rpm_user_id == Manager.id)
        .outerjoin(
            AttendanceDaily,
            (AttendanceDaily.user_id == User.id)
            & (AttendanceDaily.attendance_date == target_date),
        )
        # ✅ FIX: shift comes from USER, not project_member
        .outerjoin(Shift, User.default_shift_id == Shift.id)
        .filter(ProjectMember.project_id == project_id_uuid)
        # Removed date range filtering - show all active members regardless of assignment dates
        # The target_date is still used for attendance data, but doesn't filter project members
    )

    if only_active:
        query = query.filter(ProjectMember.is_active.is_(True))

    if only_pm_apm:
        # PM and APM are work roles, not user roles - filter by ProjectMember.work_role
        query = query.filter(ProjectMember.work_role.in_(["PM", "APM"]))

    rows = query.all()

    result = []

    for pm, user, manager, attendance, shift in rows:
        result.append(
            {
                "user_id": user.id,
                "name": user.name,
                "email": user.email,

                # ✅ DESIGNATION (system role)
                "designation": user.role.value if user.role else None,

                # ✅ WORK ROLE (project role) - shows allocated role from ProjectMember
                "work_role": pm.work_role,

                "reporting_manager": manager.name if manager else None,
                "shift": shift.name if shift else None,

                "attendance_status": attendance.status if attendance else "ABSENT",
                "first_clock_in": attendance.first_clock_in_at if attendance else None,
                "last_clock_out": attendance.last_clock_out_at if attendance else None,
                "minutes_worked": attendance.minutes_worked if attendance else 0,
            }
        )

    return {
        "project_id": project_id,
        "date": target_date,
        "total_resources": len(result),
        "resources": result,
    }


@router.get("/role-counts")
def get_project_role_counts(
    project_id: str = Query(..., description="Project UUID"),
    target_date: date = Query(date.today()),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns role counts for a project on a given date.
    Counts each unique (user_id, work_role) combination separately,
    so if a user worked in multiple roles, each role is counted.
    
    Example: If user clocks in as "ANNOTATION" in morning and "QC" in afternoon,
    both roles will be counted (ANNOTATION: 1, QC: 1).
    """
    try:
        project_id_uuid = UUID(project_id)
    except (ValueError, TypeError):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid project_id format: {project_id}"
        )
    
    # Query TimeHistory to get all unique (user_id, work_role) combinations
    # Note: TimeHistory is already imported at the top
    
    role_combinations = (
        db.query(
            TimeHistory.user_id,
            TimeHistory.work_role
        )
        .filter(
            TimeHistory.project_id == project_id_uuid,
            TimeHistory.sheet_date == target_date
        )
        .distinct()
        .all()
    )
    
    # Count how many users worked in each role
    # Each unique (user_id, work_role) combination counts as 1
    role_counts = {}
    for user_id, work_role in role_combinations:
        if work_role and work_role.strip() and work_role != "Unknown":
            role_counts[work_role] = role_counts.get(work_role, 0) + 1
    
    return {
        "project_id": project_id,
        "date": target_date,
        "role_counts": role_counts
    }
