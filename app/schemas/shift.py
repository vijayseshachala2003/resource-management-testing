from pydantic import BaseModel
from datetime import time
from uuid import UUID
from typing import Optional

class ShiftBase(BaseModel):
    name: str
    start_time: time
    end_time: time
    timezone: str
    is_active: bool = True

class ShiftCreate(ShiftBase):
    pass

class ShiftUpdate(BaseModel):
    name: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None

class ShiftResponse(ShiftBase):
    id: UUID

    class Config:
        from_attributes = True
