from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from uuid import UUID
from typing import List, Optional
from datetime import datetime

from app.db.session import get_db
from app.models.attendance_request import AttendanceRequest
from app.models.project_members import ProjectMember
from app.models.project_owners import ProjectOwner
from app.schemas.attendance_request import (
    AttendanceRequestCreate,
    AttendanceRequestUpdate,
    AttendanceRequestResponse,
)
from app.core.dependencies import get_current_user
from app.models.user import User


router = APIRouter(
    prefix="/attendance/requests",
    tags=["Leave/WFH Requests"]
)

# CREATE 
@router.post("/", response_model=AttendanceRequestResponse)
def create_request(
    payload: AttendanceRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = AttendanceRequest(
    user_id=user.id,
    project_id=payload.project_id,
    request_type=payload.request_type,
    status="PENDING",
    start_date=payload.start_date,
    end_date=payload.end_date,
    start_time=payload.start_time,
    end_time=payload.end_time,
    reason=payload.reason,
    attachment_url=payload.attachment_url,
    updated_at=datetime.utcnow()
)

    db.add(req)
    db.commit()
    db.refresh(req)
    return req


# READ MY REQUESTS 
@router.get("/", response_model=List[AttendanceRequestResponse])
def get_my_requests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return db.query(AttendanceRequest).filter(
        AttendanceRequest.user_id == user.id
    ).order_by(AttendanceRequest.created_at.desc()).all()


# READ BY ID
@router.get("/{request_id}", response_model=AttendanceRequestResponse)
def get_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = db.query(AttendanceRequest).filter(
        and_(
            AttendanceRequest.id == request_id,
            AttendanceRequest.user_id == user.id,
            )
        ).first()

    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    return req


# UPDATE
@router.put("/{request_id}", response_model=AttendanceRequestResponse)
def update_request(
    request_id: UUID,
    payload: AttendanceRequestUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = db.query(AttendanceRequest).filter(
        and_(
            AttendanceRequest.id == request_id,
            AttendanceRequest.user_id == user.id,
        )
    ).first()

    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    for k, v in payload.dict(exclude_unset=True).items():
        setattr(req, k, v)

    db.commit()
    db.refresh(req)
    return req


#  DELETE 
@router.delete("/{request_id}")
def delete_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = db.query(AttendanceRequest).filter(
        and_(
            AttendanceRequest.id == request_id,
            AttendanceRequest.user_id == user.id,
        )
    ).first()

    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    db.delete(req)
    db.commit()

    return {"message": "Attendance request deleted successfully"}


# =====================
# ADMIN ROUTER - For managers to view all requests
# =====================
admin_router = APIRouter(
    prefix="/admin/attendance-requests",
    tags=["Admin - Leave/WFH Requests"]
)


@admin_router.get("/")
def list_all_requests_with_user_info(
    status: Optional[str] = None,
    user_id: Optional[UUID] = None,
    request_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admin endpoint to list all attendance requests with user info.
    Returns request data with user_name for display in Streamlit.
    """
    from app.models.user import User
    
    query = db.query(
        AttendanceRequest,
        User.name.label('user_name'),
        User.email.label('user_email')
    ).join(User, AttendanceRequest.user_id == User.id)

    role_value = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_value.upper() != "ADMIN":
        # Restrict visibility to project owners + reporting managers
        project_owner_match = db.query(ProjectOwner.id).join(
            ProjectMember,
            ProjectOwner.project_id == ProjectMember.project_id,
        ).filter(
            ProjectOwner.user_id == current_user.id,
            ProjectMember.user_id == AttendanceRequest.user_id,
            ProjectMember.is_active.is_(True),
            ProjectMember.assigned_from <= AttendanceRequest.start_date,
            or_(
                ProjectMember.assigned_to.is_(None),
                ProjectMember.assigned_to >= AttendanceRequest.start_date,
            ),
        )

        query = query.filter(
            or_(
                User.rpm_user_id == current_user.id,
                project_owner_match.exists(),
            )
        )

    if status:
        query = query.filter(AttendanceRequest.status == status)
    
    if user_id:
        query = query.filter(AttendanceRequest.user_id == user_id)
    
    if request_type:
        query = query.filter(AttendanceRequest.request_type == request_type)

    results = (
        query
        .order_by(AttendanceRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    
    # Convert to dict with user info
    response = []
    for req, user_name, user_email in results:
        req_dict = {
            "id": str(req.id),
            "user_id": str(req.user_id),
            "user_name": user_name,
            "user_email": user_email,
            "project_id": str(req.project_id) if req.project_id else None,
            "request_type": req.request_type,
            "status": req.status,
            "start_date": str(req.start_date),
            "end_date": str(req.end_date),
            "reason": req.reason,
            "created_at": str(req.created_at),
        }
        response.append(req_dict)
    
    return response


@admin_router.get("/{request_id}", response_model=AttendanceRequestResponse)
def admin_get_request(request_id: UUID, db: Session = Depends(get_db)):
    """Get a specific attendance request by ID"""
    req = db.query(AttendanceRequest).filter(
        AttendanceRequest.id == request_id
    ).first()
    
    if not req:
        raise HTTPException(status_code=404, detail="Attendance request not found")
    
    return req
