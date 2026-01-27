from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased
from app.db.session import SessionLocal
from app.models.shift import Shift
from app.models.user import User, UserRole
from app.models.project_members import ProjectMember
from app.models.attendance_daily import AttendanceDaily
from app.core.dependencies import get_current_user
from app.schemas.user import UserBatchUpdateRequest, UserCreate, UserResponse, UserUpdate, UserQualityUpdate, UserSystemUpdate, UsersAdminSearchFilters, UserBatchUpdate
from typing import List, Optional
from uuid import UUID
from datetime import date
from math import ceil


router = APIRouter(
    prefix="/admin/users",
    tags=["Admin Users"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=List[UserResponse])
def list_users(
    name: Optional[str] = None,
    email: Optional[str] = None,
    roles: Optional[List[str]] = Query(None),
    rpm_user_id: Optional[UUID] = None,
    is_active: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(User)

    if name:
        query = query.filter(User.name.ilike(f"%{name}%"))

    if email:
        query = query.filter(User.email.ilike(f"%{email}%"))

    if roles:
        query = query.filter(User.role.in_(roles))

    if rpm_user_id:
        query = query.filter(User.rpm_user_id == rpm_user_id)

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    return (
        query
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

@router.get("/kpi_cards_info")
def kpi_cards_info(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    # total_users = db.query(func.count(User.id)).scalar()
    total_users = db.query(User.id).count()
    allocated = db.query(func.count(func.distinct(ProjectMember.user_id))).scalar()
    unallocated = total_users - allocated
    contractors = db.query(User).filter(User.work_role == 'CONTRACTOR').count()
    todays_date = date.today()
    on_leave = db.query(func.count(func.distinct(AttendanceDaily.user_id))).filter(
        AttendanceDaily.attendance_date == todays_date,
        AttendanceDaily.status == "LEAVE"
        ).scalar()
      

    return {
        "users": total_users,
        "allocated": allocated,
        "unallocated": unallocated,
        "contractors": contractors,
        "leave": on_leave
    }

@router.get("/reporting_managers")
def list_rep_managers(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    # Get the names of the PMs/ APMs / RMs with role as ADMIN
    reporting_managers = (
        db.query(
            User.id,
            User.name
        )
        .filter(User.role == "ADMIN")
        .all()
    )

    return [{
        "rpm_id": r.id,
        "rpm_name": r.name
    }
    for r in reporting_managers
    ]

@router.post("/users_with_filter")
def search_with_filters(
    payload: UsersAdminSearchFilters,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    date = payload.date
    email = payload.email
    name = payload.name
    allocated = payload.allocated
    work_role = payload.work_role
    is_active = payload.is_active
    status = payload.status

    today = date
    Manager = aliased(User)

    project_count_sq = (
        db.query(
            ProjectMember.user_id.label("user_id"),
            func.count(ProjectMember.id).label("project_count"),

        )
        .group_by(ProjectMember.user_id)
        .subquery()
    )

    attendance_sq = (
        db.query(
            AttendanceDaily.user_id.label("user_id"),
            func.max(AttendanceDaily.status).label("status"),
        )
        .filter(AttendanceDaily.attendance_date == today)
        .group_by(AttendanceDaily.user_id)
        .subquery()
    )

    query = (
        db.query(
            User.id,
            User.name,
            User.email,
            User.role,
            User.work_role,
            User.is_active,
            User.default_shift_id.label("shift_id"),
            Shift.name.label("shift_name"),
            Manager.name.label("reporting_manager"),
            Manager.id.label("reporting_manager_id"),
            # case(
            #     (User.work_role == "CONTRACTOR", True),
            #     else_=False
            # ).label("is_contractor"),
            func.coalesce(project_count_sq.c.project_count, 0).label(
                "allocated_projects"
            ),
            func.coalesce(attendance_sq.c.status, "UNKNOWN").label(
                "today_status"
            ),
        )
        .outerjoin(Manager, Manager.id == User.rpm_user_id)
        .outerjoin(project_count_sq, project_count_sq.c.user_id == User.id)
        .outerjoin(attendance_sq, attendance_sq.c.user_id == User.id)
        .outerjoin(Shift, Shift.id == User.default_shift_id)
    ) 

    # ---- Filters ----
    if email:
        query = query.filter(User.email.ilike(f"%{email}%"))

    if name:
        query = query.filter(User.name.ilike(f"%{name}%"))

    if work_role:
        query = query.filter(User.work_role == work_role)

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if allocated is not None:
        if allocated:
            query = query.filter(
                func.coalesce(project_count_sq.c.project_count, 0) > 0
            )
        else:
            query = query.filter(
                func.coalesce(project_count_sq.c.project_count, 0) == 0
            )

    if status is not None:
        query = query.filter(
            func.coalesce(attendance_sq.c.status, "UNKNOWN") == status
        )


    results = query.all()
    total = query.count()
    results = (
        query
        .order_by(User.name.asc())
        .all()
    )

    # ---- Response ----
    return {
        "items": [{
            "id": r.id,
            "name": r.name,
            "email": r.email,
            "role": r.role,
            "work_role": r.work_role,
            "is_active": r.is_active,
            "shift_id": r.shift_id,
            "shift_name": r.shift_name,
            "rpm_user_id": r.reporting_manager_id,
            "allocated_projects": r.allocated_projects,
            "today_status": r.today_status,
        }
        for r in results
        ],
        "meta": {
            "total": total,
        }
    } 

@router.post("/", response_model=UserResponse)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    
    user = User(
        email=payload.email,
        name=payload.name,
        role=UserRole(payload.role),
        work_role=payload.work_role,
        doj=payload.doj,
        default_shift_id=payload.default_shift_id,
        rpm_user_id=payload.rpm_user_id,
        soul_id=payload.soul_id,
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

from fastapi import HTTPException, APIRouter, Depends, status
from app.schemas.user import UserQualityUpdate, UserUpdate

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user

@router.patch("/{user_id}/quality-rating", response_model=UserResponse)
def update_quality_rating(
    user_id: UUID,
    payload: UserQualityUpdate,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.quality_rating = payload.quality_rating

    db.commit()
    db.refresh(user)

    return user

from app.schemas.user import UserSystemUpdate
@router.patch("/{user_id}/system", response_model=UserResponse)
def update_system_identifiers(
    user_id: UUID,
    payload: UserSystemUpdate,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return user

@router.patch("/bulk_update")
def bulk_upadte_users(
    payload: UserBatchUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):

    updated_ids = []
    failed = []

    for item in payload.updates:
        user_id = item.id
        changes = item.changes.dict(exclude_unset=True)

        if not changes:
            continue  # nothing to update

        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            failed.append({
                "id": str(user_id),
                "error": "User not found"
            })
            continue

        if "rpm_user_id" in changes and str(changes["rpm_user_id"]).split(" — ")[0] == user.id:
            failed.append({
                "id": str(user_id),
                "error": "User cannot be their own reporting manager"
            })
            continue

        for field, value in changes.items():
            setattr(user, field, value)

        updated_ids.append(str(user_id))

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Batch update failed")

    return {
        "updated": updated_ids,
        "failed": failed,
        "updated_count": len(updated_ids),
        "failed_count": len(failed),
    }


@router.delete("/{user_id}")
def deactivate_user(
    user_id: UUID,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()

    return {"message": "User deactivated successfully"}

