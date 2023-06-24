from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSON

from .base_task import BaseTask


class Nft(BaseTask):
    nft_properties = Column(JSON)
    collection_act_txid = Column(String)
    open_api_group_id = Column(String)
    nft_dd_file_ipfs_link = Column(String)
    owner_id = Column(Integer, ForeignKey("user.id"))
    owner = relationship("User", back_populates="nft_tasks")
