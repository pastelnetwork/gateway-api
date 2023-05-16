from typing import TYPE_CHECKING
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base_class import Base, gen_rand_id

if TYPE_CHECKING:
    from .user import User  # noqa: F401


class BaseTask(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True, default=gen_rand_id)

    original_file_name = Column(String)
    original_file_content_type = Column(String)
    original_file_local_path = Column(String)
    original_file_ipfs_link = Column(String)
    stored_file_ipfs_link = Column(String)
    stored_file_aws_link = Column(String)
    stored_file_other_links = Column(JSONB)
    make_publicly_accessible= Column(Boolean, default=False)

    work_id = Column(String, index=True)
    ticket_id = Column(String, index=True)
    wn_file_id = Column(String, index=True)
    wn_task_id = Column(String, index=True)
    wn_fee = Column(Integer)
    height = Column(Integer, index=True)
    ticket_status = Column(String, index=True)
    retry_num = Column(Integer, default=0)

    reg_ticket_txid = Column(String, index=True)
    act_ticket_txid = Column(String, index=True)
    pastel_id = Column(String, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
