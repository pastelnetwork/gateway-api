from typing import TYPE_CHECKING
from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.db.base_class import gen_rand_id


if TYPE_CHECKING:
    from .user import User  # noqa: F401


class Cascade(Base):
    id = Column(Integer, primary_key=True, index=True, default=gen_rand_id)
    work_id = Column(Integer, index=True)
    task_id = Column(String)
    wn_task_id = Column(String, default=gen_rand_id)
    height = Column(Integer, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("user.id"))
    owner = relationship("User", back_populates="cascade")
