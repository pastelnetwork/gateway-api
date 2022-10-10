from typing import TYPE_CHECKING
from datetime import datetime#, timedelta

from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User  # noqa: F401


class ApiKey(Base):
    id = Column(Integer, primary_key=True, index=True)
    api_key = Column(String, index=True)
    can_nft = Column(Boolean, default=False)
    can_sense = Column(Boolean, default=False)
    can_cascade = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("user.id"))
    owner = relationship("User", back_populates="api_keys")