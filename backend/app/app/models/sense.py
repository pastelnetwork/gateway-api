from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from .base_task import BaseTask


class Sense(BaseTask):
    burn_txid = Column(String, index=True)
    collection_act_txid = Column(String)
    open_api_group_id = Column(String)
    owner_id = Column(Integer, ForeignKey("user.id"))
    owner = relationship("User", back_populates="sense_tasks")
    sense_history = relationship("SenseHistory", back_populates="sense_task")
