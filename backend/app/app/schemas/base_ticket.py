from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, Json


class BaseTicketBase(BaseModel):
    original_file_name: str
    original_file_content_type: str
    original_file_local_path: str
    work_id: str
    ticket_status: str
    ticket_id: str
    wn_file_id: str
    wn_fee: int
    height: int
    wn_task_id: Optional[str] = None
    reg_ticket_txid: Optional[str] = None
    act_ticket_txid: Optional[str] = None
    ipfs_link: Optional[str] = None
    aws_link: Optional[str] = None
    other_links: Optional[Json] = None


class BaseTicketCreate(BaseTicketBase):
    pass


class BaseTicketUpdate(BaseTicketBase):
    updated_at: datetime = datetime.utcnow()


class BaseTicketInDBBase(BaseTicketBase):
    id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    owner_id: int

    class Config:
        orm_mode = True


class BaseTicket(BaseTicketInDBBase):
    pass


# Properties stored in DB
class BaseTicketInDB(BaseTicketInDBBase):
    pass


class TicketRegistrationResult(BaseModel):
    file: str
    ticket_id: str
    status: str
    reg_ticket_txid: Optional[str] = None
    act_ticket_txid: Optional[str] = None
    ipfs_link: Optional[str] = None
    aws_link: Optional[str] = None
    other_links: Optional[Json] = None
    error: Optional[Any] = None


class WorkResult(BaseModel):
    work_id: str
    tickets: List[TicketRegistrationResult]
