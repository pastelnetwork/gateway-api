from typing import List, Optional

from sqlalchemy.orm import Session
import sqlalchemy as sa

from app.crud.base import CRUDBase
from app.models.sense import Sense
from app.schemas.sense import SenseCreate, SenseUpdate
from app.core.status import DbStatus


class CRUDSense(CRUDBase[Sense, SenseCreate, SenseUpdate]):
    @staticmethod
    def create_with_owner(
            db: Session, *, obj_in: SenseCreate, owner_id: int
    ) -> Sense:
        db_obj = Sense(
            original_file_name=obj_in.original_file_name,
            original_file_content_type=obj_in.original_file_content_type,
            original_file_local_path=obj_in.original_file_local_path,
            original_file_ipfs_link=obj_in.original_file_ipfs_link,
            make_publicly_accessible=obj_in.make_publicly_accessible,
            request_id=obj_in.request_id,
            result_id=obj_in.result_id,
            wn_file_id=obj_in.wn_file_id,
            wn_fee=obj_in.wn_fee,
            height=obj_in.height,
            collection_act_txid=obj_in.collection_act_txid,
            open_api_group_id=obj_in.open_api_group_id,
            owner_id=owner_id
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_result_id(self, db: Session, *, result_id: str) -> Optional[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.result_id == result_id)
            .first())

    def get_by_result_id_and_owner(self, db: Session, *, result_id: str, owner_id) -> Optional[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.owner_id == owner_id)
            .filter(Sense.result_id == result_id)
            .first())

    def get_by_request_id_and_name(self, db: Session, *, request_id: str, file_name: str, owner_id) -> Optional[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.owner_id == owner_id)
            .filter(Sense.request_id == request_id)
            .filter(Sense.original_file_name == file_name)
            .first()
        )

    def get_all_in_request(self, db: Session, *, request_id: str, owner_id: int, skip: int = 0, limit: int = 100)\
            -> List[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.owner_id == owner_id)
            .filter(Sense.request_id == request_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_in_request_not_started(
            self, db: Session, *, request_id: str, skip: int = 0, limit: int = 100
    ) -> List[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.request_id == request_id)
            .filter(
                sa.and_(
                    Sense.burn_txid.is_(None),
                    Sense.wn_task_id.is_(None),
                ))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_in_request_prepaid(
            self, db: Session, *, request_id: str, skip: int = 0, limit: int = 100
    ) -> List[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.request_id == request_id)
            .filter(
                sa.and_(
                    Sense.burn_txid.isnot(None),
                    Sense.wn_task_id.is_(None),
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_in_request_started(
            self, db: Session, *, request_id: str, skip: int = 0, limit: int = 100
    ) -> List[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.request_id == request_id)
            .filter(
                sa.and_(
                    Sense.burn_txid.isnot(None),
                    Sense.wn_task_id.isnot(None),
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_in_registered_state(
            self, db: Session
    ) -> List[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.process_status == DbStatus.REGISTERED.value)
            .all()
        )

    def get_all_started_not_finished(
            self, db: Session, *, skip: int = 0, limit: int = 1000
    ) -> List[Sense]:
        return (
            db.query(self.model)
            .filter(
                sa.and_(
                    Sense.process_status == DbStatus.STARTED.value,
                    sa.or_(
                        Sense.reg_ticket_txid.is_(None),
                        Sense.act_ticket_txid.is_(None),
                    )
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_failed(
            self, db: Session, *, skip: int = 0, limit: int = 1000
    ) -> List[Sense]:
        return (
            db.query(self.model)
            .filter(
                sa.or_(
                    Sense.process_status == DbStatus.ERROR.value,
                    Sense.process_status == '',
                    Sense.process_status.is_(None),
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_multi_by_owner(
            self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 100
    ) -> List[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_preburn_txid(self, db: Session, *, txid: str) -> Optional[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.burn_txid == txid)
            .first())

    def get_by_reg_txid(self, db: Session, *, reg_txid: str) -> Optional[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.reg_ticket_txid == reg_txid)
            .first())

    def get_by_act_txid(self, db: Session, *, act_txid: str) -> Optional[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.act_ticket_txid == act_txid)
            .first())


sense = CRUDSense(Sense)
