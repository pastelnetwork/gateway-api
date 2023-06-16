from typing import Optional

from .base_task import BaseTaskBase, BaseTaskCreate, BaseTaskUpdate, BaseTaskInDBBase, BaseTask, BaseTaskInDB


# Shared properties
class CascadeBase(BaseTaskBase):
    offer_ticket_txid: Optional[str]
    offer_ticket_intended_rcpt_pastel_id: Optional[str]


# Properties to receive on Cascade creation
class CascadeCreate(BaseTaskCreate, CascadeBase):
    burn_txid: Optional[str] = None


# Properties to receive on Cascade update
class CascadeUpdate(BaseTaskUpdate, CascadeBase):
    pass


# Properties shared by models stored in DB
class CascadeInDBBase(BaseTaskInDBBase, CascadeBase):
    pass


# Properties to return to client
class Cascade(BaseTask, CascadeInDBBase):
    pass


# Properties stored in DB
class CascadeInDB(BaseTaskInDB, CascadeInDBBase):
    pass
