from app.crud.base import CRUDBase
from app.models.history_log import CascadeHistory, SenseHistory, NftHistoryLog, CollectionHistory
from app.schemas.history_log import HistoryLogCreate, HistoryLogUpdate

from app.db.base_class import Base
from sqlalchemy.orm import Session
from typing import Optional, TypeVar
from pydantic import BaseModel

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class CRUDHistoryLog(CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType]):
    def get_by_ids(self, db: Session,
                   task_id: int,
                   wn_file_id: str, wn_task_id: str, pastel_id: str) -> Optional[ModelType]:
        return (
            db.query(self.model)
            .filter(self.model.task_id == task_id)
            .filter(self.model.wn_file_id == wn_file_id)
            .filter(self.model.wn_task_id == wn_task_id)
            .filter(self.model.pastel_id == pastel_id)
            .first())

class CRUDCascadeLog(CRUDHistoryLog[CascadeHistory, HistoryLogCreate, HistoryLogUpdate]):
    pass

class CRUDSenseLog(CRUDHistoryLog[SenseHistory, HistoryLogCreate, HistoryLogUpdate]):
    pass

class CRUDNftLog(CRUDHistoryLog[NftHistoryLog, HistoryLogCreate, HistoryLogUpdate]):
    pass

class CRUDCollectionLog(CRUDBase[CollectionHistory, HistoryLogCreate, HistoryLogUpdate]):
    pass

cascade_log = CRUDCascadeLog(CascadeHistory)
sense_log = CRUDSenseLog(SenseHistory)
nft_log = CRUDNftLog(NftHistoryLog)
collection_log = CRUDCollectionLog(CollectionHistory)
