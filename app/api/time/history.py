from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import List, Optional
import uuid
from uuid import UUID
from app.db.session import SessionLocal
from app.models.history import TimeHistory
from app.models.project import Project
from app.schemas.history import TimeHistoryResponse, ClockInRequest, ClockOutRequest
from app.core.dependencies import get_current_user
from app.models.user import User

from app.schemas.history import ApprovalRequest

router = APIRouter(prefix="/time", tags=["Time Tracking"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 1. CLOCK IN ---
@router.post("/clock-in", response_model=TimeHistoryResponse)
def clock_in(
    payload: ClockInRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if user already has an active session (where clock_out_at is NULL)
    active_session = db.query(TimeHistory).filter(
        TimeHistory.user_id == current_user.id,
        TimeHistory.clock_out_at == None
    ).first()

    if active_session:
        raise HTTPException(
            status_code=400, 
            detail="You are already clocked in. Please clock out first."
        )

    # Create new session
    # Note: sheet_date defaults to today, status defaults to 'PENDING'
    new_session = TimeHistory(
        user_id=current_user.id,
        project_id=payload.project_id,
        work_role=payload.work_role,
        clock_in_at=datetime.now(),
        sheet_date=date.today(),
        tasks_completed=0,
        status="PENDING" ,
        
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    if new_session.project:
        new_session.project_name = new_session.project.name
    return new_session

# --- 2. CLOCK OUT ---
@router.put("/clock-out", response_model=TimeHistoryResponse)
def clock_out(
    payload: ClockOutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Find the active session for this user
    active_session = db.query(TimeHistory).filter(
        TimeHistory.user_id == current_user.id,
        TimeHistory.clock_out_at == None
    ).first()

    if not active_session:
        raise HTTPException(
            status_code=400, 
            detail="No active session found. You must clock in first."
        )

    # Update the session
    active_session.clock_out_at = datetime.now()
    active_session.tasks_completed = payload.tasks_completed
    active_session.notes = payload.notes
    
    db.commit()
    db.refresh(active_session)
    return active_session

# --- 3. GET HISTORY ---
@router.get("/history", response_model=List[TimeHistoryResponse])
def get_history(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(TimeHistory).filter(
        TimeHistory.user_id == current_user.id
    )

    if start_date:
        query = query.filter(TimeHistory.sheet_date >= start_date)

    if end_date:
        query = query.filter(TimeHistory.sheet_date <= end_date)

    results = query.order_by(TimeHistory.clock_in_at.desc()).all()
    
    # Attach project names for UI
    for r in results:
        if r.project:
            r.project_name = r.project.name
            
    return results



# --- 4. APPROVE SESSION (Manager Action) ---
@router.put("/history/{history_id}/approve", response_model=TimeHistoryResponse)
def approve_session(
    history_id: UUID,
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user),
):
    # 1. Find the session
    session = db.query(TimeHistory).filter(TimeHistory.id == history_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Timesheet not found")

    # 2. Update fields
    # if session.user_id == current_user.id:
    #     raise HTTPException(
    #         status_code=403, 
    #         detail="You cannot approve your own timesheet."
    #     )
    # --------------------------
    
    session.status = payload.status
    session.approval_comment = payload.approval_comment
    session.approved_by_user_id = "087084fa-aff2-4c10-bb72-5b0c9963c4d5"
    session.approved_at = datetime.now()
    
    db.commit()
    db.refresh(session)
    
    # 3. Attach project name for UI (Safety check)
    if session.project:
        session.project_name = session.project.name
        
    return session

# --- 5. GET CURRENT ACTIVE SESSION (For Home Page Logic) ---
@router.get("/current", response_model=Optional[TimeHistoryResponse])
def get_current_active_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Checks if the user has a session running (Clock Out is NULL).
    Returns the session details if yes, or null if no.
    """
    active_session = db.query(TimeHistory).filter(
        TimeHistory.user_id == current_user.id,
        TimeHistory.clock_out_at == None
    ).first()

    if active_session:
        # Manually attach project name so the UI can display "Working on: Project Alpha"
        if active_session.project:
            active_session.project_name = active_session.project.name
        return active_session
    
    return None
