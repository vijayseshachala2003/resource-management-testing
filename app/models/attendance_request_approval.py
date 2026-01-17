import uuid
import enum
from sqlalchemy import Column, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from app.db.base import Base


class AttendanceApprovalDecision(enum.Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AttendanceRequestApproval(Base):
    __tablename__ = "attendance_request_approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    request_id = Column(UUID(as_uuid=True), nullable=False)
    approver_user_id = Column(UUID(as_uuid=True), nullable=False)
    
    decision = Column(
        Enum(AttendanceApprovalDecision, name="attendance_approval_decision", create_type=False),
        nullable=False
    )
    comment = Column(Text, nullable=True)
    
    decided_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
