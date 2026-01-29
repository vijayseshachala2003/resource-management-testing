from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from datetime import datetime

from app.db.session import get_db
from app.models.attendance_request import AttendanceRequest
from app.models.attendance_request_approval import AttendanceRequestApproval
from app.models.attendance_daily import AttendanceDaily
from app.models.project import Project
from app.schemas.attendance_request_approval import (
    AttendanceRequestApprovalCreate,
    AttendanceRequestApprovalUpdate,
    AttendanceRequestApprovalResponse,
)
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.notification_service import send_attendance_request_decision_email

router = APIRouter(
    prefix="/admin/attendance-request-approvals",
    tags=["Admin - Attendance Request Approvals"]
)

# ------------------------------------------------------------------
# 1. CREATE APPROVAL (The "Smart" Endpoint)
# ------------------------------------------------------------------
@router.post("/", response_model=AttendanceRequestApprovalResponse)
def create_approval(
    payload: AttendanceRequestApprovalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates an approval log AND updates the parent request status.
    If APPROVED, it also auto-fills the AttendanceDaily table.
    """
    # 1. Fetch the Parent Request
    request = db.query(AttendanceRequest).filter(
        AttendanceRequest.id == payload.request_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Parent Attendance Request not found")

    # 2. Prevent double-approval (Safety check)
    if request.status != "PENDING":
         raise HTTPException(status_code=400, detail=f"Request is already {request.status}")

    # 3. Create the Approval Log
    # Note: exclude_unset=True ensures we don't accidentally wipe defaults if using Pydantic v2
    approval_data = payload.model_dump(exclude_unset=True)
    # Always use the authenticated user as the approver to avoid FK mismatches
    approval_data["approver_user_id"] = current_user.id
    approval = AttendanceRequestApproval(**approval_data)
    
    # 4. CRITICAL: Update the Parent Request Status
    request.status = payload.decision  # 'APPROVED' or 'REJECTED'
    request.updated_at = datetime.utcnow()

    # 5. AUTOMATION: If Approved, update the Daily Roster (AttendanceDaily)
    # This ensures the user shows as "LEAVE" or "WFH" on the dashboard instead of "ABSENT"
    if payload.decision == "APPROVED" and request.project_id:
        # Check if daily entry already exists to avoid duplicates
        existing_daily = db.query(AttendanceDaily).filter(
            AttendanceDaily.user_id == request.user_id,
            AttendanceDaily.attendance_date == request.start_date
        ).first()

        new_status = "LEAVE" if request.request_type == "LEAVE" else "PRESENT" # WFH counts as Present usually
        
        if not existing_daily:
            daily_record = AttendanceDaily(
                user_id=request.user_id,
                project_id=request.project_id,
                attendance_date=request.start_date, # Note: For multi-day leave, you would loop from start to end date here
                status=new_status,
                source="AUTO",
                request_id=request.id,
                notes=f"{request.request_type} Approved: {request.reason}"
            )
            db.add(daily_record)
        else:
            # Update existing record (e.g., if they were marked Absent but now Leave is approved)
            existing_daily.status = new_status
            existing_daily.request_id = request.id
            existing_daily.source = "AUTO"
            existing_daily.notes = f"{request.request_type} Approved: {request.reason}"

    db.add(approval)
    db.commit()
    db.refresh(approval)

    # Send notification email (non-blocking failures)
    request_user = db.query(User).filter(User.id == request.user_id).first()
    if request_user and request_user.email:
        project_names = None
        if request.project_id:
            project = db.query(Project).filter(Project.id == request.project_id).first()
            if project and project.name:
                project_names = project.name
        send_attendance_request_decision_email(
            user_email=request_user.email,
            user_name=request_user.name or request_user.email,
            decision=payload.decision,
            comment=payload.comment,
            request_type=request.request_type,
            start_date=str(request.start_date),
            end_date=str(request.end_date),
            project_names=project_names,
        )

    return approval

# ------------------------------------------------------------------
# 2. LIST APPROVALS (Audit Log)
# ------------------------------------------------------------------
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

# ------------------------------------------------------------------
# 3. GET SINGLE APPROVAL
# ------------------------------------------------------------------
@router.get("/{approval_id}", response_model=AttendanceRequestApprovalResponse)
def get_approval(approval_id: UUID, db: Session = Depends(get_db)):
    approval = db.query(AttendanceRequestApproval).filter(
        AttendanceRequestApproval.id == approval_id
    ).first()
    
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    return approval

# ------------------------------------------------------------------
# 4. UPDATE APPROVAL (Correction)
# ------------------------------------------------------------------
@router.put("/{approval_id}", response_model=AttendanceRequestApprovalResponse)
def update_approval(
    approval_id: UUID,
    payload: AttendanceRequestApprovalUpdate,
    db: Session = Depends(get_db)
):
    """
    Updates the audit log entry itself (e.g. fixing a typo in the comment).
    Note: This does NOT automatically revert the status of the Request.
    """
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

# ------------------------------------------------------------------
# 5. DELETE APPROVAL
# ------------------------------------------------------------------
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