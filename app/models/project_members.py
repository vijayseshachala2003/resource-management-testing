import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class ProjectMember(Base):
    __tablename__ = "project_members"

    # Matches Supabase 'id' (uuid)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Matches Foreign Keys
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Matches 'USER-DEFINED' (We treat it as String in Python. 
    # IMPORTANT: You must send a value that exactly matches your Supabase Enum options)
    work_role = Column(String, nullable=False)
    
    # Matches 'assigned_from' (date, not null)
    assigned_from = Column(Date, nullable=False)
    
    # Matches 'assigned_to' (date, nullable)
    assigned_to = Column(Date, nullable=True)
    
    # Matches 'is_active' (boolean, default true)
    is_active = Column(Boolean, default=True, nullable=False)

    # Matches Timestamps (With fix for Not-Null violation)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), 
        default=func.now(),       # Fixes creation error
        onupdate=func.now(),      # Updates on edit
        nullable=False
    )

    # Relationships
    user = relationship("User")
    project = relationship("Project")