from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.db.session import get_db
from app.models.attendance_daily import AttendanceDaily
from app.schemas.attendance_daily import (
    AttendanceDailyCreate,
    AttendanceDailyUpdate,
    AttendanceDailyResponse,
)

router = APIRouter(
    prefix="/attendance-daily",
    tags=["Attendance Daily"]
)

#CREATE (POST)
@router.post("/", response_model=AttendanceDailyResponse)
def create_attendance(
    payload: AttendanceDailyCreate,
    db: Session = Depends(get_db),
):
    attendance = AttendanceDaily(**payload.model_dump())

    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    return attendance

#READ[LIST] - (GET)
@router.get("/", response_model=List[AttendanceDailyResponse])
def list_attendance(
    user_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None,
    attendance_date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(AttendanceDaily)

    if user_id:
        query = query.filter(AttendanceDaily.user_id == user_id)

    if project_id:
        query = query.filter(AttendanceDaily.project_id == project_id)

    if attendance_date:
        query = query.filter(AttendanceDaily.attendance_date == attendance_date)

    return query.order_by(AttendanceDaily.attendance_date.desc()).all()

#READ(GET)
@router.get("/{attendance_id}", response_model=AttendanceDailyResponse)
def get_attendance(
    attendance_id: UUID,
    db: Session = Depends(get_db),
):
    attendance = db.query(AttendanceDaily).filter(
        AttendanceDaily.id == attendance_id
    ).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance entry not found",
        )

    return attendance

#UPDATE (PUT)
@router.put("/{attendance_id}", response_model=AttendanceDailyResponse)
def update_attendance(
    attendance_id: UUID,
    payload: AttendanceDailyUpdate,
    db: Session = Depends(get_db),
):
    attendance = db.query(AttendanceDaily).filter(
        AttendanceDaily.id == attendance_id
    ).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance entry not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(attendance, field, value)

    db.commit()
    db.refresh(attendance)

    return attendance

#DELETE (DELETE)
@router.delete("/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(
    attendance_id: UUID,
    db: Session = Depends(get_db),
):
    attendance = db.query(AttendanceDaily).filter(
        AttendanceDaily.id == attendance_id
    ).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance entry not found",
        )

    db.delete(attendance)
    db.commit()
