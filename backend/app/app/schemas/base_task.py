from datetime import datetime
from enum import Enum
from typing import Optional, List, Any

from pydantic import BaseModel, Json


class BaseTaskBase(BaseModel):
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
    pastel_id: Optional[str] = None
    original_file_ipfs_link: Optional[str] = None
    stored_file_aws_link: Optional[str] = None
    stored_file_other_links: Optional[Json] = None
    make_publicly_accessible: Optional[bool] = None
    retry_num: Optional[int] = None


class BaseTaskCreate(BaseTaskBase):
    pass


class BaseTaskUpdate(BaseTaskBase):
    updated_at: datetime = datetime.utcnow()


class BaseTaskInDBBase(BaseTaskBase):
    id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    owner_id: int

    class Config:
        orm_mode = True


class BaseTask(BaseTaskInDBBase):
    pass


# Properties stored in DB
class BaseTaskInDB(BaseTaskInDBBase):
    pass


class Status(str, Enum):
    PENDING = "PENDING"
    PENDING_REG = "RESULT COMPLETE. PENDING REGISTRATION"
    PENDING_ACT = "REGISTRATION COMPLETE. PENDING ACTIVATION"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class ResultRegistrationResult(BaseModel):
    file_name: str
    file_type: str
    result_id: str
    created_at: datetime
    last_updated_at: datetime
    result_status: Status
    status_messages: Optional[Any] = None
    retry_num: Optional[int] = None
    registration_ticket_txid: Optional[str] = None
    activation_ticket_txid: Optional[str] = None
    original_file_ipfs_link: Optional[str] = None
    stored_file_ipfs_link: Optional[str] = None
    stored_file_aws_link: Optional[str] = None
    stored_file_other_links: Optional[Json] = None
    make_publicly_accessible: Optional[bool] = None
    error: Optional[Any] = None


class RequestResult(BaseModel):
    request_id: str
    request_status: Status
    results: List[ResultRegistrationResult]
