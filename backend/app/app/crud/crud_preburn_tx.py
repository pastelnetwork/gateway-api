from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import asc
from sqlalchemy.sql.expression import func
import sqlalchemy as sa

from app.crud.base import CRUDBase
from app.models.preburn_tx import PreBurnTx, PBTXStatus
from app.schemas.preburn_tx import PreBurnTxCreate, PreBurnTxUpdate


class CRUDPreBurnTx(CRUDBase[PreBurnTx, PreBurnTxCreate, PreBurnTxUpdate]):
    @staticmethod
    def create_new(db: Session, *, fee: int, height: int, txid: str) -> PreBurnTx:
        db_obj = PreBurnTx(
            fee=fee,
            height=height,
            txid=txid,
            status=PBTXStatus.NEW,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def create_new_bound(db: Session, *, fee: int, height: int, txid: str, result_id: str) -> PreBurnTx:
        db_obj = PreBurnTx(
            fee=fee,
            height=height,
            txid=txid,
            status=PBTXStatus.PENDING,
            ticket_id=result_id,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_non_used_by_fee(self, db: Session, *, fee: int) -> Optional[PreBurnTx]:
        db_obj = db.query(self.model)\
            .filter(PreBurnTx.fee == fee)\
            .filter(PreBurnTx.status == PBTXStatus.NEW)\
            .order_by(asc(PreBurnTx.height)) \
            .with_for_update() \
            .first()
        if not db_obj:
            return
        db_obj.status = PBTXStatus.PENDING
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def change_status(self, db: Session, preburn_txid: str, status: PBTXStatus):
        db_obj = db.query(self.model).filter(PreBurnTx.txid == preburn_txid).first()
        if db_obj:
            update_data = {"status": status}
            super().update(db, db_obj=db_obj, obj_in=update_data)

    def mark_used(self, db: Session, preburn_txid: str):
        self.change_status(db, preburn_txid, PBTXStatus.USED)

    def mark_non_used(self, db: Session, preburn_txid: str):
        db_obj = db.query(self.model).filter(PreBurnTx.txid == preburn_txid).first()
        if db_obj:
            update_data = {"status": PBTXStatus.NEW, "ticket_id": None}
            super().update(db, db_obj=db_obj, obj_in=update_data)

    def mark_pending(self, db: Session, preburn_txid: str):
        self.change_status(db, preburn_txid, PBTXStatus.PENDING)

    def bind_pending_to_result(self, db: Session, db_obj: PreBurnTx, *, result_id: str) -> PreBurnTx:
        update_data = PreBurnTxUpdate(
            fee=db_obj.fee,
            height=db_obj.height,
            txid=db_obj.txid,
            status=db_obj.status,
            ticket_id=result_id,
        )
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def get_bound_to_result(self, db: Session, *, result_id: str) -> Optional[PreBurnTx]:
        return (
            db.query(self.model)
            .filter(
                sa.and_(
                    PreBurnTx.ticket_id == result_id,
                    PreBurnTx.status != "USED"
                )
            )
            .first())

    def get_number_non_used_by_fee(self, db: Session, *, fee: int) -> Optional[int]:
        return db.execute(
            db.query(self.model).filter(PreBurnTx.fee == fee)
            .filter(PreBurnTx.status == PBTXStatus.NEW)
            .statement.with_only_columns([func.count()]).order_by(None)
        ).scalar()

    def get_all_used(self, db: Session) -> list[PreBurnTx]:
        return db.query(self.model).filter(PreBurnTx.status == PBTXStatus.USED).all()


preburn_tx = CRUDPreBurnTx(PreBurnTx)
