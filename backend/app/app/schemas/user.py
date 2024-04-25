from typing import Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime

from app.models.user import TXType


# Shared properties
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True
    is_superuser: bool = False
    full_name: Optional[str] = None


# Properties to receive via API on creation
class UserCreate(UserBase):
    email: EmailStr
    password: str
    balance_limit: float = 0.0


# Properties to receive via API on update
class UserUpdate(UserBase):
    password: Optional[str] = None


class UserInDBBase(UserBase):
    id: Optional[int] = None
    funding_address: Optional[str] = None
    balance: Optional[float] = 0.0

    class Config:
        from_attributes = True


# Additional properties to return via API
class User(UserInDBBase):
    pass


# Additional properties stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str


# Properties to receive via API on creation
class UserCreateWithKey(BaseModel):
    email: EmailStr
    wallet_id: str
    full_name: Optional[str] = None
    balance_limit: float = 0.0


# Additional properties to return via API
class UserWithKey(UserInDBBase):
    wallet_id: str
    key_salt: str
    wallet_key_index: int


class UserWithKeyInDb(UserWithKey):
    wallet_key: Optional[str] = None


######################################################
class AccountTransactionsBase(BaseModel):
    pass


# Properties to receive via API on creation
class AccountTransactionsCreate(AccountTransactionsBase):
    pass


# Properties to receive via API on update
class AccountTransactionsUpdate(AccountTransactionsBase):
    pass


class AccountTransactionsInDBBase(AccountTransactionsBase):
    id: Optional[int] = None
    type: TXType
    balance: Optional[float] = 0.0
    added_at: datetime
    owner_id: Optional[int] = None

    class Config:
        from_attributes = True


# Additional properties to return via API
class AccountTransactions(AccountTransactionsInDBBase):
    pass


# Additional properties stored in DB
class AccountTransactionsInDB(AccountTransactionsInDBBase):
    pass
