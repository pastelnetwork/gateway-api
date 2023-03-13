from typing import TYPE_CHECKING
from sqlalchemy import Column, Integer, String, Boolean

from app.db.base_class import Base, gen_rand_id

if TYPE_CHECKING:
    from .user import User  # noqa: F401


class RegTicket(Base):
    id = Column(Integer, primary_key=True, index=True, default=gen_rand_id)
    data_hash = Column(String, index=True)
    reg_ticket_txid = Column(String, index=True)
    ticket_type = Column(String, index=True)
    blocknum = Column(Integer, index=True)
    caller_pastel_id = Column(String, index=True)
    file_name = Column(String)
    is_public = Column(Boolean, default=False)
