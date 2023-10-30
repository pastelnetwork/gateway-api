from datetime import datetime
from enum import Enum
from typing import Optional, List, Any

from pydantic import BaseModel, Json


class BaseTaskBase(BaseModel):
    original_file_name: str
    original_file_content_type: str
    original_file_local_path: str
    request_id: str
    process_status: str
    process_status_message: Optional[str] = None
    result_id: str
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
    offer_ticket_txid: Optional[str] = None
    offer_ticket_intended_rcpt_pastel_id: Optional[str] = None
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
        from_attributes = True


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

# Life cycle of a request visible to the caller (Status):
#
# PENDING (DbStatus.NEW, DbStatus.UPLOADED, DbStatus.PREBURN_FEE, DbStatus.STARTED, DbStatus.ERROR, DbStatus.RESTARTED)
#   -> "RESULT COMPLETE. PENDING REGISTRATION" (DbStatus.STARTED and 'Request Accepted' received from WN)
#       -> "REGISTRATION COMPLETE. PENDING ACTIVATION  (DbStatus.REGISTERED)
#           -> SUCCESS (DbStatus.DONE)
#
#  ERROR
#       1) if "image" not in file.content_type - we cannot proceed at all
#       2) DbStatus.ERROR and settings.RETURN_DETAILED_WN_ERROR == True
#       3) DbStatus.ERROR and settings.RETURN_DETAILED_WN_ERROR == True
#
# FAILED:
#       1) DbStatus.DEAD


class ResultRegistrationBase(BaseModel):
    result_status: Status
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_id: Optional[str] = None
    created_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None
    status_messages: Optional[Any] = None
    retry_num: Optional[int] = None
    registration_ticket_txid: Optional[str] = None
    activation_ticket_txid: Optional[str] = None
    original_file_ipfs_link: Optional[str] = None
    stored_file_ipfs_link: Optional[str] = None
    stored_file_aws_link: Optional[str] = None
    stored_file_other_links: Optional[Json] = None
    make_publicly_accessible: Optional[bool] = None
    offer_ticket_txid: Optional[str] = None
    offer_ticket_intended_rcpt_pastel_id: Optional[str] = None
    error: Optional[Any] = None

class ResultRegistrationResult(ResultRegistrationBase):
    result_id: Optional[str]

class CollectionRegistrationResult(ResultRegistrationBase):
    collection_id: Optional[str]

class RequestResult(BaseModel):
    request_id: str
    request_status: Status
    results: List[ResultRegistrationResult]

