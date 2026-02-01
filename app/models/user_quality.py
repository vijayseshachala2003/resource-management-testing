import uuid
import enum
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Numeric, Enum as SqEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

# 1. Define the Enum (Shared by both UserQuality and ProjectQuality)
class QualityRating(str, enum.Enum):
    GOOD = "GOOD"
    BAD = "BAD"
    AVERAGE = "AVERAGE"

class UserQuality(Base):
    __tablename__ = "user_quality"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    
    work_role = Column(String, nullable=False)
    
    # 2. Use the Enum here
    rating = Column(SqEnum(QualityRating), nullable=False)
    
    quality_score = Column(Numeric(5, 2), nullable=True)
    accuracy = Column(Numeric(5, 2), nullable=True)  # Accuracy percentage (0-100)
    critical_rate = Column(Numeric(5, 2), nullable=True)  # Critical rate percentage (0-100)
    notes = Column(Text, nullable=True)
    source = Column(String, nullable=False, default="MANUAL")
    
    assessed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assessed_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Versioning fields
    is_current = Column(Boolean, nullable=False, default=True)
    valid_from = Column(DateTime(timezone=True), nullable=False, default=func.now())
    valid_to = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())