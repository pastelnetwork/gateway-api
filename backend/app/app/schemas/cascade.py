from .base_task import BaseTaskBase, BaseTaskCreate, BaseTaskUpdate, BaseTaskInDBBase, BaseTask, BaseTaskInDB


# Shared properties
class CascadeBase(BaseTaskBase):
    pass


# Properties to receive on Cascade creation
class CascadeCreate(BaseTaskCreate, CascadeBase):
    pass


# Properties to receive on Cascade update
class CascadeUpdate(BaseTaskUpdate, CascadeBase):
    burn_txid: int


# Properties shared by models stored in DB
class CascadeInDBBase(BaseTaskInDBBase, CascadeBase):
    pass


# Properties to return to client
class Cascade(BaseTask, CascadeInDBBase):
    pass


# Properties stored in DB
class CascadeInDB(BaseTaskInDB, CascadeInDBBase):
    pass
