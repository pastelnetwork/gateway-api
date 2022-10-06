from typing import Optional
import datetime

from pydantic import BaseModel


# Shared properties
class ApiKeyBase(BaseModel):
    api_key: str = None
    can_nft: Optional[bool] = False
    can_sense: Optional[bool] = False
    can_cascade: Optional[bool] = False


# Properties to receive on ApiKey creation
class ApiKeyCreate(ApiKeyBase):
    pass


# Properties to receive on ApiKey update
class ApiKeyUpdate(ApiKeyBase):
    pass


# Properties shared by models stored in DB
class ApiKeyInDBBase(ApiKeyBase):
    id: int
    created_at: datetime.datetime
    owner_id: int

    class Config:
        orm_mode = True


# Properties to return to client
class ApiKey(ApiKeyInDBBase):
    pass


# Properties stored in DB
class ApiKeyInDB(ApiKeyInDBBase):
    pass
