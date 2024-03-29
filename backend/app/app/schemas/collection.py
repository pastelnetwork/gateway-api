from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# Shared properties
class CollectionBase(BaseModel):
    result_id: str
    item_type: str
    pastel_id: str
    collection_name: str
    max_collection_entries: int
    collection_item_copy_count: int
    authorized_pastel_ids: List[str]
    max_permitted_open_nsfw_score: float
    minimum_similarity_score_to_first_entry_in_collection: float
    no_of_days_to_finalize_collection: int
    royalty: float
    green: bool
    height: int
    process_status: str
    process_status_message: Optional[str] = None
    retry_num: Optional[int] = None
    spendable_address: Optional[str] = None
    wn_task_id: Optional[str] = None
    reg_ticket_txid: Optional[str] = None
    act_ticket_txid: Optional[str] = None


# Properties to receive on Nft creation
class CollectionCreate(CollectionBase):
    pass


# Properties to receive on Nft update
class CollectionUpdate(CollectionBase):
    pass


# Properties shared by models stored in DB
class CollectionInDBBase(CollectionBase):
    id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    owner_id: int

    class Config:
        from_attributes = True


# Properties to return to client
class Collection(CollectionInDBBase):
    pass


# Properties stored in DB
class CollectionInDB(CollectionInDBBase):
    pass
