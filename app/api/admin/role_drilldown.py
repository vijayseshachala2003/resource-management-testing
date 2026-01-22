from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import date
from typing import Optional
from uuid import UUID

from app.db.session import get_db
from app.core.dependencies import get_current_user

from app.models.project_members import ProjectMember
from app.models.attendance_daily import AttendanceDaily
from app.models.user import User
from app.models.user_daily_metrics import UserDailyMetrics
from app.models.user_quality import UserQuality

router = APIRouter(
    prefix="/admin/role-drilldown",
    tags=["Admin Reports"]
)

@router.get("/")
def role_drilldown(
    project_id: UUID,
    date_: date = Query(..., alias="date"),
    role: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Role Drilldown Report
    """

    query = (
        db.query(
            User.name.label("user"),
            User.email,
            ProjectMember.work_role.label("role"),

            AttendanceDaily.status.label("attendance_status"),
            AttendanceDaily.minutes_worked,
            AttendanceDaily.first_clock_in_at,
            AttendanceDaily.last_clock_out_at,

            UserDailyMetrics.productivity_score,

            UserQuality.rating.label("quality_rating")
        )
        .join(ProjectMember, ProjectMember.user_id == User.id)

        .outerjoin(
            AttendanceDaily,
            (AttendanceDaily.user_id == User.id) &
            (AttendanceDaily.project_id == ProjectMember.project_id) &
            (AttendanceDaily.attendance_date == date_)
        )

        .outerjoin(
            UserDailyMetrics,
            (UserDailyMetrics.user_id == User.id) &
            (UserDailyMetrics.project_id == ProjectMember.project_id) &
            (UserDailyMetrics.metric_date == date_)
        )

        .outerjoin(
            UserQuality,
            (UserQuality.user_id == User.id) &
            (UserQuality.project_id == ProjectMember.project_id) &
            (UserQuality.is_current == True)
        )

        .filter(ProjectMember.project_id == project_id)
        .filter(ProjectMember.is_active == True)
    )

    if role:
        query = query.filter(ProjectMember.work_role == role)

    if status:
        query = query.filter(AttendanceDaily.status == status)

    results = query.all()

    return [
        {
            "user": r.user,
            "email": r.email,
            "role": r.role,

            "attendance_status": r.attendance_status or "UNKNOWN",
            "minutes_worked": r.minutes_worked or 0,

            "first_in": r.first_clock_in_at,
            "last_out": r.last_clock_out_at,

            "productivity_score": r.productivity_score,
            "quality_rating": (
                r.quality_rating.value
                if hasattr(r.quality_rating, "value")
                else r.quality_rating
            )
        }
        for r in results
    ]
