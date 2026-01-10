from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.models.shift import Shift
from app.schemas.shift import ShiftCreate, ShiftUpdate, ShiftResponse

router = APIRouter(prefix="/admin/shifts", tags=["Admin Shifts"])

@router.post("/", response_model=ShiftResponse)
def create_shift(payload: ShiftCreate, db: Session = Depends(get_db)):
    shift = Shift(**payload.model_dump())
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift

@router.get("/", response_model=List[ShiftResponse])
def list_shifts(db: Session = Depends(get_db)):
    return db.query(Shift).all()

@router.get("/{shift_id}", response_model=ShiftResponse)
def get_shift(shift_id: UUID, db: Session = Depends(get_db)):
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift

@router.put("/{shift_id}", response_model=ShiftResponse)
def update_shift(
    shift_id: UUID,
    payload: ShiftUpdate,
    db: Session = Depends(get_db)
):
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(shift, key, value)

    db.commit()
    db.refresh(shift)
    return shift

@router.delete("/{shift_id}")
def delete_shift(shift_id: UUID, db: Session = Depends(get_db)):
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    shift.is_active = False
    db.commit()
    return {"message": "Shift deactivated"}
