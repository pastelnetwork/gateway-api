from typing import Optional
from datetime import datetime

from pydantic import BaseModel


# Shared properties
class ApiKeyBase(BaseModel):
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
    id: Optional[int] = None
    api_key: str = None
    created_at: datetime
    owner_id: int
    pastel_id: Optional[str] = None
    # funding_address: Optional[str] = None
    # balance: Optional[float] = 0.0
    # balance_limit: Optional[float] = 0.0

    class Config:
        from_attributes = True


# Properties to return to client
class ApiKey(ApiKeyInDBBase):
    pass


# Properties stored in DB
class ApiKeyInDB(ApiKeyInDBBase):
    pass
