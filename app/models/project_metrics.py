import uuid
from sqlalchemy import Column, Integer, Date, ForeignKey, Numeric, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class ProjectDailyMetric(Base):
    __tablename__ = "project_daily_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Core Links
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    metric_date = Column(Date, nullable=False)
    
    # Grouping by Role (e.g. "How did ANNOTATION team do vs QC team?")
    work_role = Column(String, nullable=False) 
    
    # The Stats
    tasks_completed = Column(Integer, default=0)
    active_users_count = Column(Integer, default=0)
    total_hours_worked = Column(Numeric(10, 2), default=0.00) # Numeric for precision
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    project = relationship("Project")