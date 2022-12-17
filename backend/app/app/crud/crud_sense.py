from typing import List, Optional

from sqlalchemy.orm import Session
import sqlalchemy as sa

from app.crud.base import CRUDBase
from app.models.sense import Sense
from app.schemas.sense import SenseCreate, SenseUpdate


class CRUDSense(CRUDBase[Sense, SenseCreate, SenseUpdate]):
    @staticmethod
    def create_with_owner(
            db: Session, *, obj_in: SenseCreate, owner_id: int
    ) -> Sense:
        db_obj = Sense(
            original_file_name=obj_in.original_file_name,
            original_file_content_type=obj_in.original_file_content_type,
            original_file_local_path=obj_in.original_file_local_path,
            work_id=obj_in.work_id,
            ticket_id=obj_in.ticket_id,
            wn_file_id=obj_in.wn_file_id,
            wn_fee=obj_in.wn_fee,
            height=obj_in.height,
            owner_id=owner_id
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_ticket_id(self, db: Session, *, ticket_id: str) -> Optional[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.ticket_id == ticket_id)
            .first())

    def get_by_work_id_and_name(self, db: Session, *, work_id: str, file_name: str) -> Optional[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.work_id == work_id)
            .filter(Sense.original_file_name == file_name)
            .first()
        )

    def get_all_in_work(
            self, db: Session, *, work_id: str, skip: int = 0, limit: int = 100
    ) -> List[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.work_id == work_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_in_work_not_started(
            self, db: Session, *, work_id: str, skip: int = 0, limit: int = 100
    ) -> List[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.work_id == work_id)
            .filter(
                sa.and_(
                    Sense.burn_txid.is_(None),
                    Sense.wn_task_id.is_(None),
                ))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_in_work_prepaid(
            self, db: Session, *, work_id: str, skip: int = 0, limit: int = 100
    ) -> List[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.work_id == work_id)
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

    def get_all_in_work_started(
            self, db: Session, *, work_id: str, skip: int = 0, limit: int = 100
    ) -> List[Sense]:
        return (
            db.query(self.model)
            .filter(Sense.work_id == work_id)
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

    def get_all_started_not_finished(
            self, db: Session, *, skip: int = 0, limit: int = 1000
    ) -> List[Sense]:
        return (
            db.query(self.model)
            .filter(
                sa.and_(
                    Sense.ticket_status == 'STARTED',
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
                    Sense.ticket_status == 'ERROR',
                    Sense.ticket_status.is_(None),
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


sense = CRUDSense(Sense)
