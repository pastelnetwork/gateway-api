from typing import TYPE_CHECKING
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean, and_, func
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
    make_publicly_accessible = Column(Boolean, default=False)
    offer_ticket_txid = Column(String, index=True)
    offer_ticket_intended_rcpt_pastel_id = Column(String, index=True)

    request_id = Column(String, index=True)
    result_id = Column(String, index=True)
    wn_file_id = Column(String, index=True)
    wn_task_id = Column(String, index=True)
    wn_fee = Column(Integer)
    height = Column(Integer, index=True)
    process_status = Column(String, index=True)
    process_status_message = Column(String)
    retry_num = Column(Integer, default=0)

    reg_ticket_txid = Column(String, index=True)
    act_ticket_txid = Column(String, index=True)
    pastel_id = Column(String, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    def get_all_pending_fee_sum(self, db):
        return (db.query(BaseTask)
                .filter(and_(self.process_status != 'DONE',
                             self.process_status == 'DEAD')
                        )
                .with_entities(func.sum(self.wn_fee))
                .scalar()
                )
