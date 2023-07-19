from typing import TYPE_CHECKING
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, ARRAY, Float
from sqlalchemy.orm import relationship

from app.db.base_class import Base, gen_rand_id

if TYPE_CHECKING:
    from .user import User  # noqa: F401


class Collection(Base):
    id = Column(Integer, primary_key=True, index=True, default=gen_rand_id)
    result_id = Column(String, index=True)
    item_type = Column(String, index=True)
    pastel_id = Column(String, index=True)
    collection_name = Column(String, index=True)
    max_collection_entries = Column(Integer, index=True)
    collection_item_copy_count = Column(Integer, index=True)
    authorized_pastel_ids = Column(ARRAY(String), index=True)
    max_permitted_open_nsfw_score = Column(Float, index=True)
    minimum_similarity_score_to_first_entry_in_collection = Column(Float, index=True)
    no_of_days_to_finalize_collection = Column(Integer, index=True)
    royalty = Column(Float, index=True)
    green = Column(Boolean, default=False)
    height = Column(Integer, index=True)
    process_status = Column(String, index=True)
    process_status_message = Column(String)
    spendable_address = Column(String, index=True)
    retry_num = Column(Integer, default=0)
    wn_task_id = Column(String, index=True)
    reg_ticket_txid = Column(String, index=True)
    act_ticket_txid = Column(String, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    owner_id = Column(Integer, ForeignKey("user.id"))
    owner = relationship("User", back_populates="collection_tasks")
