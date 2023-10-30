from typing import Optional

from .base_task import BaseTaskBase, BaseTaskCreate, BaseTaskUpdate, BaseTaskInDBBase, BaseTask, BaseTaskInDB


# Shared properties
class SenseBase(BaseTaskBase):
    collection_act_txid: Optional[str] = None
    open_api_group_id: Optional[str] = None


# Properties to receive on Sense creation
class SenseCreate(BaseTaskCreate, SenseBase):
    burn_txid: Optional[str] = None


# Properties to receive on Sense update
class SenseUpdate(BaseTaskUpdate, SenseBase):
    pass


# Properties shared by models stored in DB
class SenseInDBBase(BaseTaskInDBBase, SenseBase):
    pass


# Properties to return to client
class Sense(BaseTask, SenseInDBBase):
    pass


# Properties stored in DB
class SenseInDB(BaseTaskInDB, SenseInDBBase):
    pass
