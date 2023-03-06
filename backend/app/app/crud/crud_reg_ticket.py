from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.security import create_api_key
from app.crud.base import CRUDBase
from app.models.psl_reg_ticket import RegTicket
from app.schemas.reg_ticket import RegTicketCreate, RegTicketUpdate


class CRUDRegTicket(CRUDBase[RegTicket, RegTicketCreate, RegTicketUpdate]):
    def get_by_hash(self, db: Session, *, data_hash: str) -> Optional[RegTicket]:
        return db.query(RegTicket).filter(RegTicket.data_hash == data_hash).first()

    def get_last_blocknum(self, db: Session) -> int:
        last = db.query(RegTicket).order_by(RegTicket.blocknum.desc()).first()
        return last.blocknum if last else 0


reg_ticket = CRUDRegTicket(RegTicket)
