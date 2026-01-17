from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional

from app.db.session import get_db
from app.models.attendance_request_approval import AttendanceRequestApproval
from app.schemas.attendance_request_approval import (
    AttendanceRequestApprovalCreate,
    AttendanceRequestApprovalUpdate,
    AttendanceRequestApprovalResponse,
)

router = APIRouter(
    prefix="/admin/attendance-request-approvals",
    tags=["Admin - Attendance Request Approvals"]
)


@router.post("/", response_model=AttendanceRequestApprovalResponse)
def create_approval(
    payload: AttendanceRequestApprovalCreate,
    db: Session = Depends(get_db)
):
    approval = AttendanceRequestApproval(**payload.model_dump(exclude_unset=True))
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


@router.get("/", response_model=List[AttendanceRequestApprovalResponse])
def list_approvals(
    request_id: Optional[UUID] = None,
    approver_user_id: Optional[UUID] = None,
    decision: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(AttendanceRequestApproval)

    if request_id:
        query = query.filter(AttendanceRequestApproval.request_id == request_id)
    
    if approver_user_id:
        query = query.filter(AttendanceRequestApproval.approver_user_id == approver_user_id)
    
    if decision:
        query = query.filter(AttendanceRequestApproval.decision == decision)

    return (
        query
        .order_by(AttendanceRequestApproval.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


@router.get("/{approval_id}", response_model=AttendanceRequestApprovalResponse)
def get_approval(approval_id: UUID, db: Session = Depends(get_db)):
    approval = db.query(AttendanceRequestApproval).filter(
        AttendanceRequestApproval.id == approval_id
    ).first()
    
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    return approval


@router.put("/{approval_id}", response_model=AttendanceRequestApprovalResponse)
def update_approval(
    approval_id: UUID,
    payload: AttendanceRequestApprovalUpdate,
    db: Session = Depends(get_db)
):
    approval = db.query(AttendanceRequestApproval).filter(
        AttendanceRequestApproval.id == approval_id
    ).first()
    
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(approval, key, value)

    db.commit()
    db.refresh(approval)
    return approval


@router.delete("/{approval_id}")
def delete_approval(approval_id: UUID, db: Session = Depends(get_db)):
    approval = db.query(AttendanceRequestApproval).filter(
        AttendanceRequestApproval.id == approval_id
    ).first()
    
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    db.delete(approval)
    db.commit()
    
    return {"message": "Approval deleted successfully"}
