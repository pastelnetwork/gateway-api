import enum
from sqlalchemy import Column, Integer, String, Enum

from app.db.base_class import Base


class PBTXStatus(enum.Enum):
    NEW = 1
    PENDING = 2
    USED = 3
    BAD = 4


class PreBurnTx(Base):
    id = Column(Integer, primary_key=True, index=True)
    fee = Column(Integer, index=True)
    height = Column(Integer, index=True)
    txid = Column(String)
    status = Column(Enum(PBTXStatus), default=PBTXStatus.NEW)
    result_id = Column(String)
