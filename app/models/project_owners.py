import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class ProjectOwner(Base):
    __tablename__ = "project_owners"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    work_role = Column(String, nullable=False)  
    
    # Timestamps
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # FIXED: Added 'default=func.now()' so it has a value on creation
    updated_at = Column(
        DateTime(timezone=True), 
        default=func.now(), 
        onupdate=func.now()
    )

    # Relationships
    user = relationship("User")
    project = relationship("Project")