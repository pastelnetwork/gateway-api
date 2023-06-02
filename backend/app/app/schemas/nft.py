from typing import Optional
from pydantic import BaseModel

from .base_task import BaseTaskBase, BaseTaskCreate, BaseTaskUpdate, BaseTaskInDBBase, BaseTask, BaseTaskInDB


class ThumbnailCoordinate(BaseModel):
    bottom_right_x: Optional[float]
    bottom_right_y: Optional[float]
    top_left_x: Optional[float]
    top_left_y: Optional[float]


class NftPropertiesExternal(BaseModel):
    creator_name: Optional[str]
    creator_website_url: Optional[str]
    description: Optional[str]
    green: Optional[bool]
    issued_copies: Optional[int]
    keywords: Optional[str]
    maximum_fee: Optional[float]
    name: Optional[str]
    royalty: Optional[float] = 0.0
    series_name: Optional[str]
    youtube_url: Optional[str]


class NftPropertiesInternal(NftPropertiesExternal):
    thumbnail_coordinate: Optional[ThumbnailCoordinate]


# Shared properties
class NftBase(BaseTaskBase):
    nft_properties: Optional[NftPropertiesInternal]
    collection_act_txid: Optional[str]
    open_api_group_id: Optional[str]
    nft_dd_file_ipfs_link: Optional[str]


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
class SenseInDB(BaseTaskInDB, NftInDBBase):
    pass
