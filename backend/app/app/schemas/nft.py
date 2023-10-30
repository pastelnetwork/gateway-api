from typing import Optional
from pydantic import BaseModel

from .base_task import BaseTaskBase, BaseTaskCreate, BaseTaskUpdate, BaseTaskInDBBase, BaseTask, BaseTaskInDB


class ThumbnailCoordinate(BaseModel):
    bottom_right_x: Optional[float] = 120.0
    bottom_right_y: Optional[float] = 120.0
    top_left_x: Optional[float] = 0.0
    top_left_y: Optional[float] = 0.0


class NftPropertiesExternal(BaseModel):
    creator_name: Optional[str] = None
    creator_website_url: Optional[str] = None
    description: Optional[str] = None
    green: Optional[bool] = False
    issued_copies: Optional[int] = 1
    keywords: Optional[str] = None
    maximum_fee: Optional[float] = 0.0
    name: Optional[str] = None
    royalty: Optional[float] = 0.0
    series_name: Optional[str] = None
    youtube_url: Optional[str] = None


class NftPropertiesInternal(NftPropertiesExternal):
    thumbnail_coordinate: Optional[ThumbnailCoordinate]


# Shared properties
class NftBase(BaseTaskBase):
    nft_properties: Optional[NftPropertiesInternal] = None
    collection_act_txid: Optional[str] = None
    open_api_group_id: Optional[str] = None
    nft_dd_file_ipfs_link: Optional[str] = None


# Properties to receive on Nft creation
class NftCreate(BaseTaskCreate, NftBase):
    pass


# Properties to receive on Nft update
class NftUpdate(BaseTaskUpdate, NftBase):
    pass


# Properties shared by models stored in DB
class NftInDBBase(BaseTaskInDBBase, NftBase):
    pass


# Properties to return to client
class Nft(BaseTask, NftInDBBase):
    pass


# Properties stored in DB
class NftInDB(BaseTaskInDB, NftInDBBase):
    pass
