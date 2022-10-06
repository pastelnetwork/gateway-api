from typing import TYPE_CHECKING
import random
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .api_key import ApiKey  # noqa: F401


def gen_rand_id():
    return random.getrandbits(31)


class User(Base):
    id = Column(Integer, primary_key=True, index=True, default=gen_rand_id)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean, default=False)
    api_keys = relationship("ApiKey", back_populates="owner")
