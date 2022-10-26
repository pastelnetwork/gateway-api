from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BaseTaskBase(BaseModel):
    original_file_name: str
    original_file_content_type: str
    original_file_local_path: str
    work_id: str
    task_id: str
    wn_file_id: str
    wn_fee: int
    height: int
    wn_task_id: Optional[str] = None


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
