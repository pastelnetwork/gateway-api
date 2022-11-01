from typing import List, Optional

from sqlalchemy.orm import Session
import sqlalchemy as sa

from app.crud.base import CRUDBase
from app.models.cascade import Cascade
from app.schemas.cascade import CascadeCreate, CascadeUpdate


class CRUDCascade(CRUDBase[Cascade, CascadeCreate, CascadeUpdate]):
    @staticmethod
    def create_with_owner(
            db: Session, *, obj_in: CascadeCreate, owner_id: int
    ) -> Cascade:
        db_obj = Cascade(
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

    def get_by_ticket_id(self, db: Session, *, ticket_id: str) -> Optional[Cascade]:
        return db.query(self.model).filter(Cascade.ticket_id == ticket_id).first()

    def get_by_work_id_and_name(self, db: Session, *, work_id: str, file_name: str) -> Optional[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.work_id == work_id)
            .filter(Cascade.original_file_name == file_name)
            .first()
        )

    def get_all_in_work(
            self, db: Session, *, work_id: str, skip: int = 0, limit: int = 100
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.work_id == work_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_in_work_not_started(
            self, db: Session, *, work_id: str, skip: int = 0, limit: int = 100
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.work_id == work_id)
            .filter(
                sa.and_(
                    Cascade.burn_txid.is_(None),
                    Cascade.wn_task_id.is_(None),
                ))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all_in_work_prepaid(
            self, db: Session, *, work_id: str, skip: int = 0, limit: int = 100
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.work_id == work_id)
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

    def get_all_in_work_started(
            self, db: Session, *, work_id: str, skip: int = 0, limit: int = 100
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.work_id == work_id)
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

    def get_all_started_not_finished(
            self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(
                sa.and_(
                    Cascade.task_id == 'DONE',
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

    def get_multi_by_owner(
            self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 100
    ) -> List[Cascade]:
        return (
            db.query(self.model)
            .filter(Cascade.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
            .all()
        )


cascade = CRUDCascade(Cascade)
