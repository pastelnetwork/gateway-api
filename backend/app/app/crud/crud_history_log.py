from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import asc
from sqlalchemy.sql.expression import func
import sqlalchemy as sa

from app.crud.base import CRUDBase
from app.models.history_log import CascadeHistory, SenseHistory
from app.schemas.history_log import CascadeHistoryLog, CascadeHistoryLogUpdate
from app.schemas.history_log import SenseHistoryLog, SenseHistoryLogUpdate


class CRUDCascadeHistoryLog(CRUDBase[CascadeHistory, CascadeHistoryLog, CascadeHistoryLogUpdate]):
    pass


class CRUDSenseHistoryLog(CRUDBase[SenseHistory, SenseHistoryLog, SenseHistoryLogUpdate]):
    pass


cascade_log = CRUDCascadeHistoryLog(CascadeHistory)
sense_log = CRUDSenseHistoryLog(SenseHistory)
