from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from datetime import datetime, timedelta

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session
import sqlalchemy as sa

from app.core.status import DbStatus
from app.db.base_class import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).

        **Parameters**

        * `model`: A SQLAlchemy model class
        * `schema`: A Pydantic model (schema) class
        """
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        return db.query(self.model).filter(self.model.id == id).first()

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 10000
    ) -> List[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)  # type: ignore
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: int) -> ModelType:
        obj = db.query(self.model).get(id)
        db.delete(obj)
        db.commit()
        return obj

    def get_multi_by_owner_and_status(
            self, db: Session, *, owner_id: int, req_status: str, skip: int = 0, limit: int = 10000
    ) -> List[ModelType]:
        query = db.query(self.model).filter(self.model.owner_id == owner_id)
        if req_status == 'SUCCESS':
            query = query.filter(self.model.process_status == DbStatus.DONE.value)
        if req_status == 'FAILED':
            query = query.filter(self.model.process_status == DbStatus.DEAD.value)
        if req_status == 'PENDING':
            query = ((query
                     .filter(self.model.process_status != DbStatus.DONE.value))
                     .filter(self.model.process_status != DbStatus.DEAD.value))
        return query.offset(skip).limit(limit).all()

    def get_all_not_finished(
            self, db: Session, *, hours_ago=12, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        twelve_hours_ago = datetime.utcnow() - timedelta(hours=hours_ago)
        return (
            db.query(self.model)
            .filter(
                sa.and_(
                    sa.or_(
                        self.model.process_status == DbStatus.UPLOADED.value,
                        self.model.process_status == DbStatus.PREBURN_FEE.value,
                        self.model.process_status == DbStatus.STARTED.value,
                    ),
                    self.model.updated_at < twelve_hours_ago
                )
            )
            .order_by(self.model.updated_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
