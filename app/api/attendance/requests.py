from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from uuid import UUID
from typing import List
from datetime import datetime

from app.db.session import get_db
from app.models.attendance_request import AttendanceRequest
from app.schemas.attendance_request import (
    AttendanceRequestCreate,
    AttendanceRequestUpdate,
    AttendanceRequestResponse,
)
from app.core.dependencies import get_current_user
from app.models.user import User


router = APIRouter(
    prefix="/attendance/requests",
    tags=["Attendance Requests"]
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
