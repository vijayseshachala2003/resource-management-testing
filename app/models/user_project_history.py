from sqlalchemy import Column, Date, Integer, Numeric, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid

class UserProjectHistory(Base):
    __tablename__ = "user_project_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)

    work_role = Column(String, nullable=False)

    total_hours_worked = Column(Numeric, default=0)
    total_tasks_completed = Column(Integer, default=0)

    first_worked_date = Column(Date)
    last_worked_date = Column(Date)
