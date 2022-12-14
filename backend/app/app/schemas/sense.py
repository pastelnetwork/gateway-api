from typing import Optional

from .base_ticket import BaseTicketBase, BaseTicketCreate, BaseTicketUpdate, BaseTicketInDBBase, BaseTicket, BaseTicketInDB


# Shared properties
class SenseBase(BaseTicketBase):
    pass


# Properties to receive on Sense creation
class SenseCreate(BaseTicketCreate, SenseBase):
    burn_txid: Optional[str] = None


# Properties to receive on Sense update
class SenseUpdate(BaseTicketUpdate, SenseBase):
    pass


# Properties shared by models stored in DB
class SenseInDBBase(BaseTicketInDBBase, SenseBase):
    pass


# Properties to return to client
class Sense(BaseTicket, SenseInDBBase):
    pass


# Properties stored in DB
class SenseInDB(BaseTicketInDB, SenseInDBBase):
    pass
