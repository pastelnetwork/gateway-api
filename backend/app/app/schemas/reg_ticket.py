from typing import Optional

from pydantic import BaseModel


# Shared properties
class RegTicketBase(BaseModel):
    data_hash: str
    reg_ticket_txid: str
    ticket_type: str
    blocknum: int
    caller_pastel_id: str
    file_name: str
    is_public: bool


# Properties to receive on RegTicket creation
class RegTicketCreate(RegTicketBase):
    pass


class RegTicketUpdate(RegTicketBase):
    pass


# Properties shared by models stored in DB
class RegTicketInDBBase(RegTicketBase):
    id: Optional[int] = None

    class Config:
        from_attributes = True


# Properties to return to client
class RegTicket(RegTicketInDBBase):
    pass


# Properties stored in DB
class RegTicketInDB(RegTicketInDBBase):
    pass
