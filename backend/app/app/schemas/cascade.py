import datetime

from pydantic import BaseModel


# Shared properties
class CascadeBase(BaseModel):
    task_id: str
    wn_task_id: str
    height: int


# Properties to receive on Cascade creation
class CascadeCreate(CascadeBase):
    pass


# Properties to receive on Cascade update
class CascadeUpdate(CascadeBase):
    updated_at: datetime.datetime = datetime.utcnow


# Properties shared by models stored in DB
class CascadeInDBBase(CascadeBase):
    id: int
    work_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    owner_id: int

    class Config:
        orm_mode = True


# Properties to return to client
class Cascade(CascadeInDBBase):
    pass


# Properties stored in DB
class CascadeInDB(CascadeInDBBase):
    pass
