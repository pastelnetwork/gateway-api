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
