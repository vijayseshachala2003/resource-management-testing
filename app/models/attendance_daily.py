import uuid
from sqlalchemy import Column, String, Integer, ForeignKey,Numeric, DateTime, Date, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class AttendanceDaily(Base):

    __tablename__ = "attendance_daily"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)

    attendance_date = Column(Date, nullable=False)

    shift_id = Column(UUID(as_uuid=True), ForeignKey("shifts.id"), nullable=True)

    status = Column(String, default = "UNKNOWN", nullable=False) #(e.g., PRESENT, ABSENT, LEAVE).
    minutes_late = Column(Integer,default=0, nullable=False) #number of minutes late

    first_clock_in_at = Column(DateTime(timezone=True), nullable=True)

    last_clock_out_at = Column(DateTime(timezone=True), nullable=True)

    minutes_worked = Column(Numeric, nullable=True)

    request_id = Column(UUID(as_uuid=True), ForeignKey("attendance_requests.id"), nullable=True)

    notes = Column(Text, nullable=True)

    source = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(),  onupdate=func.now(), nullable=False)

    #relationships
    user = relationship("User", foreign_keys=[user_id])
    project = relationship("Project")
    shift = relationship("Shift")
    #request = relationship("AttendanceRequest")