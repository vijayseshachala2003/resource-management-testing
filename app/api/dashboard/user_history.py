from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Optional

from app.core.dependencies import get_current_user, get_db
from app.models.user_daily_metrics import UserDailyMetrics
from app.schemas.user_daily_metrics import UserDailyMetricsResponse
from app.models.user import User

router = APIRouter(prefix="/dashboard/me", tags=["User Dashboard"])

@router.get("/history", response_model=List[UserDailyMetricsResponse])
def get_my_history(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(UserDailyMetrics).filter(
        UserDailyMetrics.user_id == current_user.id
    )

    if from_date:
        query = query.filter(UserDailyMetrics.metric_date >= from_date)
    if to_date:
        query = query.filter(UserDailyMetrics.metric_date <= to_date)

    return query.order_by(UserDailyMetrics.metric_date.desc()).all()
