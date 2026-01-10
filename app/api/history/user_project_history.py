from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from app.db.session import get_db
from app.models.user_project_history import UserProjectHistory
from app.schemas.user_project_history import UserProjectHistoryResponse

router = APIRouter(prefix="/history", tags=["User Project History"])

@router.get("/users/{user_id}", response_model=list[UserProjectHistoryResponse])
def get_user_project_history(
    user_id: UUID,
    db: Session = Depends(get_db)
):
    return (
        db.query(UserProjectHistory)
        .filter(UserProjectHistory.user_id == user_id)
        .all()
    )

@router.get("/projects/{project_id}", response_model=list[UserProjectHistoryResponse])
def get_project_user_history(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    return (
        db.query(UserProjectHistory)
        .filter(UserProjectHistory.project_id == project_id)
        .all()
    )
