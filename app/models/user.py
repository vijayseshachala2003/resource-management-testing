import uuid
from sqlalchemy import Column, String, Boolean, Date, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base
import enum

# 👇 Python enum matching Postgres enum
class UserRole(enum.Enum):
    ADMIN = "ADMIN"
    USER = "USER"

class WorkRole(enum.Enum):
    CONTRACTOR = "CONTRACTOR"
    EMPLOYEE = "EMPLOYEE"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # supabase_user_id = Column(UUID(as_uuid=True), unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)

    # IMPORTANT: Enum mapping
    role = Column(Enum(UserRole, name="user_role"), nullable=False)

    is_active = Column(Boolean, default=True)

    doj = Column(Date, nullable=True)
    work_role = Column(String, nullable=True)  # string for now
    default_shift_id = Column(UUID(as_uuid=True), nullable=True)

    quality_rating = Column(String, nullable=True)
    rpm_user_id = Column(UUID(as_uuid=True), nullable=True)
    soul_id = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
