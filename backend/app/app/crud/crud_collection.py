from typing import List, Optional

from sqlalchemy.orm import Session
import sqlalchemy as sa

from app.crud.base import CRUDBase
from app.models.collection import Collection
from app.schemas.collection import CollectionCreate, CollectionUpdate
from app.core.status import DbStatus


class CRUDCollection(CRUDBase[Collection, CollectionCreate, CollectionUpdate]):
    @staticmethod
    def create_with_owner(
            db: Session, *, obj_in: CollectionCreate, owner_id: int
    ) -> Collection:
        db_obj = Collection(
            result_id=obj_in.result_id,
            item_type=obj_in.item_type,
            pastel_id=obj_in.pastel_id,
            collection_name=obj_in.collection_name,
            max_collection_entries=obj_in.max_collection_entries,
            collection_item_copy_count=obj_in.collection_item_copy_count,
            authorized_pastel_ids=obj_in.authorized_pastel_ids,
            max_permitted_open_nsfw_score=obj_in.max_permitted_open_nsfw_score,
            minimum_similarity_score_to_first_entry_in_collection=obj_in.minimum_similarity_score_to_first_entry_in_collection,
            no_of_days_to_finalize_collection=obj_in.no_of_days_to_finalize_collection,
            royalty=obj_in.royalty,
            green=obj_in.green,
            process_status=obj_in.process_status,
            retry_num=obj_in.retry_num,
            height=obj_in.height,
            owner_id=owner_id
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_result_id(self, db: Session, *, result_id: str) -> Optional[Collection]:
        return (
            db.query(self.model)
            .filter(Collection.result_id == result_id)
            .first())

    def get_by_result_id_and_owner(self, db: Session, *, result_id: str, owner_id) -> Optional[Collection]:
        return (
            db.query(self.model)
            .filter(Collection.owner_id == owner_id)
            .filter(Collection.result_id == result_id)
            .first())

    def get_all_in_registered_state(
            self, db: Session, *, limit: int = 100
    ) -> List[Collection]:
        return (
            db.query(self.model)
            .filter(Collection.process_status == DbStatus.REGISTERED.value)
            .order_by(self.model.updated_at)
            .limit(limit)
            .all()
        )

    def get_all_started_not_finished(
            self, db: Session, *, skip: int = 0, limit: int = 10000
    ) -> List[Collection]:
        return (
            db.query(self.model)
            .filter(
                sa.and_(
                    Collection.process_status == DbStatus.STARTED.value,
                    sa.or_(
                        Collection.reg_ticket_txid.is_(None),
                        Collection.act_ticket_txid.is_(None),
                    )
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_failed(
            self, db: Session, *, skip: int = 0, limit: int = 10000
    ) -> List[Collection]:
        return (
            db.query(self.model)
            .filter(
                sa.or_(
                    Collection.process_status == DbStatus.ERROR.value,
                    Collection.process_status == '',
                    Collection.process_status.is_(None),
                )
            )
            .order_by(Collection.updated_at)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_multi_by_owner_by_type(
            self, db: Session, *, owner_id: int, item_type: str, skip: int = 0, limit: int = 10000
    ) -> List[Collection]:
        return (
            db.query(self.model)
            .filter(Collection.owner_id == owner_id)
            .filter(Collection.item_type == item_type)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_multi_by_owner(
            self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 10000
    ) -> List[Collection]:
        return (
            db.query(self.model)
            .filter(Collection.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_reg_txid(self, db: Session, *, reg_txid: str) -> Optional[Collection]:
        return (
            db.query(self.model)
            .filter(Collection.reg_ticket_txid == reg_txid)
            .first())

    def get_by_act_txid(self, db: Session, *, act_txid: str) -> Optional[Collection]:
        return (
            db.query(self.model)
            .filter(Collection.act_ticket_txid == act_txid)
            .first())

    def get_by_reg_txid_and_owner(self, db: Session, *, reg_txid: str, owner_id: int) -> Optional[Collection]:
        return (
            db.query(self.model)
            .filter(Collection.owner_id == owner_id)
            .filter(Collection.reg_ticket_txid == reg_txid)
            .first())

    def get_by_act_txid_and_owner(self, db: Session, *, act_txid: str, owner_id: int) -> Optional[Collection]:
        return (
            db.query(self.model)
            .filter(Collection.owner_id == owner_id)
            .filter(Collection.act_ticket_txid == act_txid)
            .first())


collection = CRUDCollection(Collection)
