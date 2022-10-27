from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import asc
from sqlalchemy.sql.expression import func

from app.crud.base import CRUDBase
from app.models.preburn_tx import PreBurnTx, PBTXStatus
from app.schemas.preburn_tx import PreBurnTxCreate, PreBurnTxUpdate


class CRUDPreBurnTx(CRUDBase[PreBurnTx, PreBurnTxCreate, PreBurnTxUpdate]):
    def create_new(self, db: Session, *, fee: int, height: int, txid: str) -> PreBurnTx:
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

    def create_new_bound(self, db: Session, *, fee: int, height: int, txid: str, task_id: str) -> PreBurnTx:
        db_obj = PreBurnTx(
            fee=fee,
            height=height,
            txid=txid,
            status=PBTXStatus.PENDING,
            task_id=task_id,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_non_used_by_fee(self, db: Session, *, fee: int) -> Optional[PreBurnTx]:
        db_obj = db.query(PreBurnTx)\
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

    def mark_non_used(self, db: Session, db_obj: PreBurnTx) -> PreBurnTx:
        update_data = PreBurnTxUpdate(
            fee=db_obj.fee,
            height=db_obj.height,
            txid=db_obj.txid,
            status=PBTXStatus.NEW,
        )
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def mark_pending(self, db: Session, db_obj: PreBurnTx) -> PreBurnTx:
        update_data = PreBurnTxUpdate(
            fee=db_obj.fee,
            height=db_obj.height,
            txid=db_obj.txid,
            status=PBTXStatus.PENDING,
        )
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def bind_pending_to_task(self, db: Session, db_obj: PreBurnTx, *, task_id: str) -> PreBurnTx:
        update_data = PreBurnTxUpdate(
            fee=db_obj.fee,
            height=db_obj.height,
            txid=db_obj.txid,
            status=db_obj.status,
            task_id=task_id,
        )
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def get_bound_to_task(self, db: Session, *, task_id: str) -> Optional[PreBurnTx]:
        return db.query(PreBurnTx).filter(PreBurnTx.task_id == task_id).first()

    def mark_used(self, db: Session, db_obj: PreBurnTx) -> PreBurnTx:
        update_data = PreBurnTxUpdate(
            fee=db_obj.fee,
            height=db_obj.height,
            txid=db_obj.txid,
            status=PBTXStatus.USED,
        )
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def get_number_non_used_by_fee(self, db: Session, *, fee: int) -> Optional[int]:
        return db.execute(
            db.query(PreBurnTx).filter(PreBurnTx.fee == fee)
            .statement.with_only_columns([func.count()]).order_by(None)
        ).scalar()


preburn_tx = CRUDPreBurnTx(PreBurnTx)
