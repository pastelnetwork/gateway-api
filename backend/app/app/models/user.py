from typing import TYPE_CHECKING
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base_class import Base
from app.db.base_class import gen_rand_id

if TYPE_CHECKING:
    from .api_key import ApiKey  # noqa: F401


class User(Base):
    id = Column(Integer, primary_key=True, index=True, default=gen_rand_id)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean, default=False)
    api_keys = relationship("ApiKey", back_populates="owner")
    cascade_tasks = relationship("Cascade", back_populates="owner")
    sense_tasks = relationship("Sense", back_populates="owner")
    nft_tasks = relationship("Nft", back_populates="owner")
    collection_tasks = relationship("Collection", back_populates="owner")
    pastel_ids = relationship("ClaimedPastelId", back_populates="owner")
    funding_address = Column(String, unique=True, index=True, nullable=True)


class ClaimedPastelId(Base):
    id = Column(Integer, primary_key=True, index=True, default=gen_rand_id)
    pastel_id = Column(String, unique=True, index=True, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("user.id"))
    owner = relationship("User", back_populates="pastel_ids")



