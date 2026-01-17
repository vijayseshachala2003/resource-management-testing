from sqlalchemy import Column, String, Date, Time, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.base import Base


class AttendanceRequest(Base):
    __tablename__ = "attendance_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)

    request_type = Column(String, nullable=False)
    status = Column(String, nullable=False)   # <<< THIS WAS MISSING

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)

    reason = Column(Text, nullable=True)
    attachment_url = Column(Text, nullable=True)

    requested_at = Column(DateTime, nullable=False, server_default=func.now())

    reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
