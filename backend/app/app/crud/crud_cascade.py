from typing import List, Optional

from sqlalchemy.orm import Session
import sqlalchemy as sa

from app.crud.base import CRUDBase
from app.models.cascade import Cascade
from app.schemas.cascade import CascadeCreate, CascadeUpdate
from app.core.status import DbStatus


class CRUDCascade(CRUDBase[Cascade, CascadeCreate, CascadeUpdate]):
    @staticmethod
    def create_with_owner(
            db: Session, *, obj_in: CascadeCreate, owner_id: int
    ) -> Cascade:
        # noinspection PyArgumentList
        db_obj = Cascade(
            original_file_name=obj_in.original_file_name,
            original_file_content_type=obj_in.original_file_content_type,
            original_file_local_path=obj_in.original_file_local_path,
            original_file_ipfs_link=obj_in.original_file_ipfs_link,
            make_publicly_accessible=obj_in.make_publicly_accessible,
            offer_ticket_intended_rcpt_pastel_id=obj_in.offer_ticket_intended_rcpt_pastel_id,
            request_id=obj_in.request_id,
            result_id=obj_in.result_id,
            wn_file_id=obj_in.wn_file_id,
            wn_fee=obj_in.wn_fee,
            height=obj_in.height,
            owner_id=owner_id
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_result_id(self, db: Session, *, result_id: str) -> Optional[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.result_id == result_id)
            .first())

    def get_by_result_id_and_owner(self, db: Session, *, result_id: str, owner_id) -> Optional[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.owner_id == owner_id)
            .filter(Cascade.result_id == result_id)
            .first())

    def get_by_request_id_and_name(self, db: Session, *, request_id: str, file_name: str, owner_id) -> Optional[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.owner_id == owner_id)
            .filter(Cascade.request_id == request_id)
            .filter(Cascade.original_file_name == file_name)
            .first()
        )

    def get_all_in_request(self, db: Session, *, request_id: str, owner_id: int, skip: int = 0, limit: int = 10000) \
            -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.owner_id == owner_id)
            .filter(Cascade.request_id == request_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_in_request_not_started(
            self, db: Session, *, request_id: str, skip: int = 0, limit: int = 10000
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.request_id == request_id)
            .filter(
                sa.and_(
                    Cascade.burn_txid.is_(None),
                    Cascade.wn_task_id.is_(None),
                ))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_in_request_prepaid(
            self, db: Session, *, request_id: str, skip: int = 0, limit: int = 10000
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.request_id == request_id)
            .filter(
                sa.and_(
                    Cascade.burn_txid.isnot(None),
                    Cascade.wn_task_id.is_(None),
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_in_request_started(
            self, db: Session, *, request_id: str, skip: int = 0, limit: int = 10000
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.request_id == request_id)
            .filter(
                sa.and_(
                    Cascade.burn_txid.isnot(None),
                    Cascade.wn_task_id.isnot(None),
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_in_done(
            self, db: Session, *, limit: int = 100
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(self.model.process_status == DbStatus.DONE.value)
            .order_by(self.model.updated_at.desc())
            .limit(limit)
            .all()
        )

    def get_all_in_registered_state(
            self, db: Session, *, limit: int = 100
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.process_status == DbStatus.REGISTERED.value)
            .order_by(self.model.updated_at)
            .limit(limit)
            .all()
        )

    def get_all_started_not_finished(
            self, db: Session, *, skip: int = 0, limit: int = 10000
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(
                sa.and_(
                    Cascade.process_status == DbStatus.STARTED.value,
                    sa.or_(
                        Cascade.reg_ticket_txid.is_(None),
                        Cascade.act_ticket_txid.is_(None),
                    )
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_failed(
            self, db: Session, *, skip: int = 0, limit: int = 10000
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(
                sa.or_(
                    Cascade.process_status == DbStatus.ERROR.value,
                    Cascade.process_status == '',
                    Cascade.process_status.is_(None),
                )
            )
            .order_by(Cascade.updated_at)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_multi_by_owner(
            self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 10000
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_preburn_txid(self, db: Session, *, txid: str) -> Optional[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.burn_txid == txid)
            .first())

    def get_by_reg_txid_and_owner(self, db: Session, *, reg_txid: str, owner_id: int) -> Optional[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.owner_id == owner_id)
            .filter(Cascade.reg_ticket_txid == reg_txid)
            .first())

    def get_by_act_txid_and_owner(self, db: Session, *, act_txid: str, owner_id: int) -> Optional[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.owner_id == owner_id)
            .filter(Cascade.act_ticket_txid == act_txid)
            .first())


cascade = CRUDCascade(Cascade)
