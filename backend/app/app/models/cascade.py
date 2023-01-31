from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from .base_ticket import BaseTicket


class Cascade(BaseTicket):
    offer_ticket_txid = Column(String, index=True)
    offer_ticket_intended_rcpt_pastel_id = Column(String, index=True)
    burn_txid = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("user.id"))
    owner = relationship("User", back_populates="cascade_tasks")
