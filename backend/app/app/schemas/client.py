from typing import Optional
from pydantic import BaseModel
from datetime import datetime


# Properties to receive via API on creation
class ClientCreate(BaseModel):
    pass


# Properties to receive via API on update
class ClientUpdate(BaseModel):
    pass


class ClientInDBBase(BaseModel):
    id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Additional properties to return via API
class Client(ClientInDBBase):
    pass


# Additional properties stored in DB
class ClientInDB(ClientInDBBase):
    hashed_secret: str


class ClientWithSecret(BaseModel):
    client_id: str
    client_secret: str
