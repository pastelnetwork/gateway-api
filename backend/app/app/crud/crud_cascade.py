from typing import List, Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.cascade import Cascade
from app.schemas.cascade import CascadeCreate, CascadeUpdate


class CRUDCascade(CRUDBase[Cascade, CascadeCreate, CascadeUpdate]):
    def create_with_owner(
            self, db: Session, *, obj_in: CascadeCreate, owner_id: int
    ) -> Cascade:
        db_obj = Cascade(
            work_id=obj_in.work_id,
            task_id=obj_in.task_id,
            wn_task_id=obj_in.wn_task_id,
            height=obj_in.height,
            owner_id=owner_id
        )

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

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
