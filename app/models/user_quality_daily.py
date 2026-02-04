import uuid
from sqlalchemy import Column, String, Date, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
# Ensure you import from your correct base (app.db.base or app.db.base_class)
from app.db.base import Base 

class UserQualityDaily(Base):
    __tablename__ = "user_quality_daily"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    
    rating_date = Column(Date, nullable=False, index=True)
    
    # Stores "GOOD", "BAD", "AVERAGE" for that specific day
    rating = Column(String, nullable=False)
    
    # Stores the exact score (e.g. 10.0)
    quality_score = Column(Numeric(5, 2), nullable=True)
    
    work_role = Column(String, nullable=True)
    
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
