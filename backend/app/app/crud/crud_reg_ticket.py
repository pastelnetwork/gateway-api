import base64
import binascii
from typing import List

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.psl_reg_ticket import RegTicket
from app.schemas.reg_ticket import RegTicketCreate, RegTicketUpdate


class CRUDRegTicket(CRUDBase[RegTicket, RegTicketCreate, RegTicketUpdate]):
    @staticmethod
    def create_new(db: Session, *,
                   data_hash: str,
                   reg_ticket_txid: str,
                   ticket_type: str,
                   blocknum: int,
                   caller_pastel_id: str,
                   file_name: str,
                   is_public: bool,
                   ) -> RegTicket:
        # noinspection PyArgumentList
        db_obj = RegTicket(
            data_hash=data_hash,
            reg_ticket_txid=reg_ticket_txid,
            ticket_type=ticket_type,
            blocknum=blocknum,
            caller_pastel_id=caller_pastel_id,
            file_name=file_name,
            is_public=is_public,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def get_by_hash(db: Session, *, data_hash_as_hex: str, ticket_type: str) -> List[RegTicket]:
        binary_hash = binascii.unhexlify(data_hash_as_hex)
        b64_hash = base64.b64encode(binary_hash).decode()
        return (db.query(RegTicket)
                .filter(RegTicket.data_hash == b64_hash)
                .filter(RegTicket.ticket_type == ticket_type)
                .all()
                )

    def get_by_reg_ticket_txid(self, db: Session, *, txid: str) -> RegTicket:
        return db.query(RegTicket).filter(RegTicket.reg_ticket_txid == txid).first()

    def get_by_reg_ticket_txid_and_type(self, db: Session, *, txid: str, ticket_type: str) -> RegTicket:
        return (db.query(RegTicket)
                .filter(RegTicket.ticket_type == ticket_type)
                .filter(RegTicket.reg_ticket_txid == txid)
                .first()
                )

    def get_last_blocknum(self, db: Session) -> int:
        last = db.query(RegTicket).order_by(RegTicket.blocknum.desc()).first()
        return last.blocknum if last else 0


reg_ticket = CRUDRegTicket(RegTicket)
