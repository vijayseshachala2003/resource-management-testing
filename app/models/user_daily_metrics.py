import uuid
from sqlalchemy import (
    Column, String, Integer, Text, Date, Numeric, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base


class UserDailyMetrics(Base):
    __tablename__ = "user_daily_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)

    work_role = Column(String, nullable=False)
    metric_date = Column(Date, nullable=False)

    hours_worked = Column(Numeric(5, 2), default=0)
    tasks_completed = Column(Integer, default=0)
    productivity_score = Column(Numeric(5, 2), nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
