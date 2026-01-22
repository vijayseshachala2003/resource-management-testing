from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, aliased

from app.core.dependencies import get_current_user, get_db
from app.models.project_members import ProjectMember
from app.models.user import User
from app.models.attendance_daily import AttendanceDaily
from app.models.shift import Shift

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
        .filter(ProjectMember.project_id == project_id)
    )

    if only_active:
        query = query.filter(ProjectMember.is_active.is_(True))

    if only_pm_apm:
        query = query.filter(User.role.in_(["PM", "APM"]))

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

        # ✅ WORK ROLE (project role)
        "work_role": pm.work_role,

        "reporting_manager": manager.name if manager else None,
        "shift": shift.name if shift else None,

        "attendance_status": attendance.status if attendance else "UNKNOWN",
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
