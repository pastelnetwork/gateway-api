from typing import TYPE_CHECKING
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base_class import Base, gen_rand_id

if TYPE_CHECKING:
    from .user import User  # noqa: F401


class HistoryLog(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True, default=gen_rand_id)

    created_at = Column(DateTime, default=datetime.utcnow)

    wn_file_id = Column(String, index=True)
    wn_task_id = Column(String, index=True)
    task_status = Column(String)
    status_messages = Column(String)
    retry_number = Column(Integer, default=0)
    pastel_id = Column(String, index=True)


class CascadeHistory(HistoryLog):
    cascade_task_id = Column(Integer, ForeignKey("cascade.id"))
    cascade_task = relationship("Cascade", back_populates="cascade_history")


class SenseHistory(HistoryLog):
    sense_task_id = Column(Integer, ForeignKey("sense.id"))
    sense_task = relationship("Sense", back_populates="sense_history")


class NftHistory(HistoryLog):
    nft_task_id = Column(Integer, ForeignKey("nft.id"))
    nft_task = relationship("Nft", back_populates="nft_history")


class CollectionHistory(HistoryLog):
    collection_task_id = Column(Integer, ForeignKey("collection.id"))
    collection_task = relationship("Collection", back_populates="collection_history")
