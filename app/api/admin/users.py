from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased
from app.db.session import SessionLocal
from app.models.shift import Shift
from app.models.user import User, UserRole
from app.models.project_members import ProjectMember
from app.models.attendance_daily import AttendanceDaily
from app.core.dependencies import get_current_user
from app.schemas.user import UserBatchUpdateRequest, UserCreate, UserResponse, UserUpdate, UserSystemUpdate, UsersAdminSearchFilters, UserBatchUpdate
from typing import List, Optional
from uuid import UUID
from datetime import date
from math import ceil
import os


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
    # Log immediately so we know the endpoint was called
    print(f"[USERS API] ===== list_users endpoint called =====")
    print(f"[USERS API] Params: limit={limit}, offset={offset}, name={name}, email={email}, roles={roles}, is_active={is_active}")
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"list_users endpoint called - limit={limit}, offset={offset}")
    
    try:
        
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

        users = (
            query
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        
        print(f"[USERS API] Found {len(users)} users from database")
        logger.info(f"Found {len(users)} users from database")
        
        # Convert users to response format, handling weekoffs conversion
        result = []
        for user in users:
            try:
                # Handle weekoffs conversion
                weekoffs_list = None
                if user.weekoffs:
                    from app.schemas.user import WeekoffDays
                    try:
                        weekoffs_list = [WeekoffDays(w.value) if hasattr(w, 'value') else WeekoffDays(str(w)) for w in user.weekoffs]
                    except (ValueError, TypeError) as we:
                        logger.warning(f"Error converting weekoffs for user {user.id}: {str(we)}")
                        weekoffs_list = None
                
                # Create response - UserResponse expects UserRole enum, not string
                # The enum from database should work directly with Pydantic
                user_data = {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "role": user.role,  # Keep as enum - Pydantic will serialize it
                    "is_active": user.is_active,
                    "work_role": user.work_role,
                    "doj": user.doj,
                    "default_shift_id": user.default_shift_id,
                    "rpm_user_id": user.rpm_user_id,
                    "soul_id": user.soul_id,
                    "weekoffs": weekoffs_list,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                }
                result.append(UserResponse(**user_data))
            except Exception as user_err:
                # If one user fails, log and continue with others
                logger.error(f"Error serializing user {user.id}: {str(user_err)}", exc_info=True)
                continue
        
        print(f"[USERS API] Successfully serialized {len(result)} users")
        logger.info(f"Successfully serialized {len(result)} users")
        return result
    except Exception as e:
        import traceback
        import logging
        error_trace = traceback.format_exc()
        logger = logging.getLogger(__name__)
        logger.error(f"Error in list_users endpoint: {str(e)}", exc_info=True)
        # Print to console for immediate visibility
        print(f"[USERS API ERROR] {str(e)}")
        print(f"[USERS API ERROR TRACEBACK]\n{error_trace}")
        error_detail = f"Error fetching users: {str(e)}\n{error_trace}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
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
    try:
        selected_date_str = payload.date
        email = payload.email
        name = payload.name
        allocated = payload.allocated
        work_role = payload.work_role
        is_active = payload.is_active
        status = payload.status

        # Use selected_date if provided, otherwise use today
        if selected_date_str:
            from datetime import datetime
            try:
                today = datetime.strptime(selected_date_str, "%Y-%m-%d").date() if isinstance(selected_date_str, str) else selected_date_str
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid date format: {selected_date_str}. Expected format: YYYY-MM-DD"
                )
        else:
            today = date.today()
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

        # Build query - use outerjoin for Shift to handle missing shifts gracefully
        # Try to build query with Shift join, but handle if Shift table doesn't exist
        try:
            # Test if Shift table is accessible
            _ = db.query(Shift).limit(1).first()
            shift_available = True
        except Exception as shift_check_error:
            print(f"[WARNING] Shift table check failed: {str(shift_check_error)}")
            shift_available = False
        
        if shift_available:
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
        else:
            # Build query without Shift join if table doesn't exist
            from sqlalchemy import literal
            query = (
                db.query(
                    User.id,
                    User.name,
                    User.email,
                    User.role,
                    User.work_role,
                    User.is_active,
                    User.default_shift_id.label("shift_id"),
                    literal(None).label("shift_name"),  # Use literal None instead of Shift.name
                    Manager.name.label("reporting_manager"),
                    Manager.id.label("reporting_manager_id"),
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

        # Get total count before ordering (more efficient)
        total = query.count()
        
        # Apply ordering and get results
        results = (
            query
            .order_by(User.name.asc())
            .all()
        )

        # ---- Response ----
        # Convert role enum to string for JSON serialization
        items = []
        for r in results:
            try:
                # Handle role enum conversion
                role_value = r.role.value if hasattr(r.role, 'value') else str(r.role)
                items.append({
                    "id": r.id,
                    "name": r.name,
                    "email": r.email,
                    "role": role_value,
                    "work_role": r.work_role,
                    "is_active": r.is_active,
                    "shift_id": r.shift_id,
                    "shift_name": r.shift_name if r.shift_name else None,
                    "rpm_user_id": r.reporting_manager_id,
                    "allocated_projects": r.allocated_projects if r.allocated_projects else 0,
                    "today_status": r.today_status if r.today_status else "UNKNOWN",
                })
            except Exception as item_error:
                # Log error for individual item but continue with others
                print(f"[WARNING] Error processing user item: {str(item_error)}")
                continue
        
        return {
            "items": items,
            "meta": {
                "total": total,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        error_trace = traceback.format_exc()
        error_type = type(e).__name__
        error_msg = str(e)
        
        # Log detailed error information
        logger.error(f"Error in search_with_filters: {error_type}: {error_msg}", exc_info=True)
        print(f"[USERS API ERROR] search_with_filters: {error_type}: {error_msg}")
        print(f"[USERS API ERROR TRACEBACK]\n{error_trace}")
        
        # Provide more helpful error message based on error type
        if "relation" in error_msg.lower() or "does not exist" in error_msg.lower():
            detail_msg = f"Database table error: {error_msg}. Please check if all required tables exist."
        elif "column" in error_msg.lower() and "does not exist" in error_msg.lower():
            detail_msg = f"Database column error: {error_msg}. Please check database schema."
        elif "shift" in error_msg.lower():
            detail_msg = f"Shift table error: {error_msg}. The shifts table may not exist or have issues."
        else:
            detail_msg = f"Error fetching users: {error_type}: {error_msg}"
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail_msg
        ) 

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


@router.post("/{user_id}/create-supabase-account")
def create_supabase_account_for_user(
    user_id: UUID,
    password: str = Query(..., description="Temporary password for the user (they should change it after first login)"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Create a Supabase Auth account for an existing database user.
    This allows users who exist in the database to login via Supabase.
    
    Requires SUPABASE_SERVICE_ROLE_KEY in environment variables.
    """
    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found in database")
    
    # Check if Supabase auth is enabled
    DISABLE_AUTH = os.getenv("DISABLE_AUTH", "true").lower() == "true"
    if DISABLE_AUTH:
        raise HTTPException(
            status_code=400,
            detail="Supabase auth is disabled. Set DISABLE_AUTH=false to enable."
        )
    
    # Get Supabase Service Role Key (admin key)
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    
    if not SUPABASE_SERVICE_ROLE_KEY or not SUPABASE_URL:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_SERVICE_ROLE_KEY or SUPABASE_URL not configured. Please set these in your .env file."
        )
    
    try:
        from supabase import create_client
        
        # Create admin client with service role key
        supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        
        # Check if user already exists in Supabase
        try:
            existing_users = supabase_admin.auth.admin.list_users()
            for existing_user in existing_users.users:
                if existing_user.email == user.email:
                    return {
                        "message": "User already exists in Supabase",
                        "email": user.email,
                        "supabase_user_id": existing_user.id,
                        "action": "User can login with their Supabase credentials"
                    }
        except Exception:
            pass  # Continue to create user
        
        # Create user in Supabase with admin API
        create_response = supabase_admin.auth.admin.create_user({
            "email": user.email,
            "password": password,
            "email_confirm": True,  # Auto-confirm email so they can login immediately
            "user_metadata": {
                "name": user.name,
                "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            }
        })
        
        if not create_response or not create_response.user:
            raise HTTPException(
                status_code=500,
                detail="Failed to create user in Supabase"
            )
        
        return {
            "message": "Supabase account created successfully",
            "email": user.email,
            "supabase_user_id": create_response.user.id,
            "action": f"User can now login with email: {user.email} and the provided password",
            "note": "User should change their password after first login"
        }
        
    except Exception as e:
        error_msg = str(e)
        if "User already registered" in error_msg or "already exists" in error_msg.lower():
            return {
                "message": "User already exists in Supabase",
                "email": user.email,
                "action": "User can login with their existing Supabase credentials"
            }
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create Supabase account: {error_msg}"
        )


from fastapi import HTTPException, APIRouter, Depends, status
from app.schemas.user import UserUpdate

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

