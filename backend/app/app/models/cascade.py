from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from .base_ticket import BaseTicket


class Cascade(BaseTicket):
    burn_txid = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("user.id"))
    owner = relationship("User", back_populates="cascade_tasks")
