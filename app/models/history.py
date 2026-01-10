import uuid
from sqlalchemy import Column, String, Integer, ForeignKey,Numeric, DateTime, Date, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class TimeHistory(Base):
    __tablename__ = "history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # --- Foreign Keys ---
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    
    # --- Enums (Stored as Strings in Python) ---
    work_role = Column(String, nullable=False)  # e.g., "ANNOTATION"
    status = Column(String, default="PENDING", nullable=False) # e.g., "PENDING"

    # --- Time Tracking ---
    sheet_date = Column(Date, nullable=False, default=func.current_date())
    clock_in_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    clock_out_at = Column(DateTime(timezone=True), nullable=True)

    # --- Productivity ---
    tasks_completed = Column(Integer, default=0, nullable=False)
    notes = Column(Text, nullable=True)
    # Add this line with the other columns
    minutes_worked = Column(Numeric, nullable=True) 

    # --- Approval (Manager Section) ---
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approval_comment = Column(Text, nullable=True)

    # --- Audit Timestamps ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), 
        default=func.now(), 
        onupdate=func.now(),
        nullable=False
    )

    # --- Relationships ---
    user = relationship("User", foreign_keys=[user_id])
    project = relationship("Project")
    approver = relationship("User", foreign_keys=[approved_by_user_id])