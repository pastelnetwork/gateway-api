from typing import Optional
from pydantic import BaseModel


# Shared properties
class HistoryLogBase(BaseModel):
    wn_file_id: Optional[str] = None
    wn_task_id: Optional[str] = None
    task_status: Optional[str] = None
    status_messages: str
    retry_number: Optional[int]
    pastel_id: Optional[str] = None


class CascadeHistoryLogBase(HistoryLogBase):
    cascade_task_id: int


class CascadeHistoryLogCreate(CascadeHistoryLogBase):
    pass


class CascadeHistoryLogUpdate(CascadeHistoryLogBase):
    pass


# Properties shared by models stored in DB
class CascadeHistoryLogInDBBase(CascadeHistoryLogBase):

    class Config:
        orm_mode = True


# Properties to return to client
class CascadeHistoryLog(CascadeHistoryLogInDBBase):
    pass


# Properties stored in DB
class CascadeHistoryLogInDB(CascadeHistoryLogInDBBase):
    pass


class SenseHistoryLogBase(HistoryLogBase):
    sense_task_id: int


class SenseHistoryLogCreate(SenseHistoryLogBase):
    pass


class SenseHistoryLogUpdate(SenseHistoryLogBase):
    pass


# Properties shared by models stored in DB
class SenseHistoryLogInDBBase(SenseHistoryLogBase):
    id: int

    class Config:
        orm_mode = True


# Properties to return to client
class SenseHistoryLog(SenseHistoryLogInDBBase):
    pass


# Properties stored in DB
class SenseHistoryLogInDB(SenseHistoryLogInDBBase):
    pass
