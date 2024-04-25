from typing import TYPE_CHECKING
from sqlalchemy import Column, String, DateTime
from datetime import datetime

from app.db.base_class import Base
from app.db.base_class import gen_rand_id
from app.core.security import get_random_string

if TYPE_CHECKING:
    from .api_key import ApiKey  # noqa: F401


class Client(Base):
    id = Column(String, primary_key=True, index=True, default=get_random_string(32))
    hashed_secret = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
