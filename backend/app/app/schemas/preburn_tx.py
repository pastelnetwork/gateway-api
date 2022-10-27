from typing import Optional
from pydantic import BaseModel

from app.models.preburn_tx import PBTXStatus

# Shared properties
class PreBurnTxBase(BaseModel):
    fee: int
    height: int
    txid: str


# Properties to receive on PreBurnTx creation
class PreBurnTxCreate(PreBurnTxBase):
    pass


# Properties to receive on PreBurnTx update
class PreBurnTxUpdate(PreBurnTxBase):
    status: PBTXStatus
    ticket_id: Optional[str] = None


# Properties shared by models stored in DB
class PreBurnTxInDBBase(PreBurnTxBase):
    id: int
    status: PBTXStatus
    ticket_id: Optional[str] = None

    class Config:
        orm_mode = True


# Properties to return to client
class PreBurnTx(PreBurnTxInDBBase):
    pass


# Properties stored in DB
class PreBurnTxInDB(PreBurnTxInDBBase):
    pass
