from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


# Shared properties
class HistoryLogBase(BaseModel):
    task_id: int
    wn_file_id: Optional[str] = None
    wn_task_id: Optional[str] = None
    pastel_id: Optional[str] = None
    status_messages: Any = None


class HistoryLogCreate(HistoryLogBase):
    created_at: datetime = datetime.utcnow(),


class HistoryLogUpdate(HistoryLogBase):
    updated_at: datetime = datetime.utcnow(),


# Properties to return to client
class HistoryLogInDB(HistoryLogBase):
    id: int
    updated_at: datetime = datetime.utcnow(),
    created_at: datetime = datetime.utcnow(),

    class Config:
        from_attributes = True
