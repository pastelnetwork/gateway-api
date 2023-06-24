from typing import TYPE_CHECKING
from sqlalchemy import Column, Integer, String, DateTime, JSON
from datetime import datetime

from app.db.base_class import Base, gen_rand_id

if TYPE_CHECKING:
    from .user import User  # noqa: F401


class HistoryLog(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True, default=gen_rand_id)
    task_id = Column(Integer, index=True)
    wn_file_id = Column(String, index=True)
    wn_task_id = Column(String, index=True)
    pastel_id = Column(String, index=True)
    status_messages = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class NftHistoryLog(HistoryLog):
    pass

class CascadeHistory(HistoryLog):
    pass

class SenseHistory(HistoryLog):
    pass

class CollectionHistory(HistoryLog):
    pass