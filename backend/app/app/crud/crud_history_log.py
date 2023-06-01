from app.crud.base import CRUDBase
from app.models.history_log import CascadeHistory, SenseHistory, NftHistory
from app.schemas.history_log import CascadeHistoryLog, CascadeHistoryLogUpdate
from app.schemas.history_log import SenseHistoryLog, SenseHistoryLogUpdate
from app.schemas.history_log import NftHistoryLog, NftHistoryLogUpdate


class CRUDCascadeHistoryLog(CRUDBase[CascadeHistory, CascadeHistoryLog, CascadeHistoryLogUpdate]):
    pass


class CRUDSenseHistoryLog(CRUDBase[SenseHistory, SenseHistoryLog, SenseHistoryLogUpdate]):
    pass


class CRUDNftHistoryLog(CRUDBase[NftHistory, NftHistoryLog, NftHistoryLogUpdate]):
    pass


cascade_log = CRUDCascadeHistoryLog(CascadeHistory)
sense_log = CRUDSenseHistoryLog(SenseHistory)
nft_log = CRUDNftHistoryLog(NftHistory)
