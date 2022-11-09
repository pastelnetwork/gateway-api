from typing import Optional

from .base_ticket import BaseTicketBase, BaseTicketCreate, BaseTicketUpdate, BaseTicketInDBBase, BaseTicket, BaseTicketInDB


# Shared properties
class CascadeBase(BaseTicketBase):
    pass


# Properties to receive on Cascade creation
class CascadeCreate(BaseTicketCreate, CascadeBase):
    burn_txid: Optional[str] = None


# Properties to receive on Cascade update
class CascadeUpdate(BaseTicketUpdate, CascadeBase):
    pass


# Properties shared by models stored in DB
class CascadeInDBBase(BaseTicketInDBBase, CascadeBase):
    pass


# Properties to return to client
class Cascade(BaseTicket, CascadeInDBBase):
    pass


# Properties stored in DB
class CascadeInDB(BaseTicketInDB, CascadeInDBBase):
    pass
