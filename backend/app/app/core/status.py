from datetime import datetime
from enum import Enum

from app import crud, schemas
from app.db.session import db_context
from app.utils import walletnode as wn

# Internal Life cycle of a request (DbStatus):
#
# (sense, cascade)  NEW -> UPLOADED -> PREBURN_FEE -> STARTED -> DONE
# (nft)             NEW -> UPLOADED -> STARTED -> DONE
#
# the request can go into error state at any of the above states
# ERROR -> RESTARTED -> UPLOADED -> PREBURN_FEE -> STARTED -> DONE
# ERROR, BUT has reg_txid -> REGISTERED
#
# REGISTERED -> DONE
#
# ERROR -> ... -> ERROR 10 times -> DEAD


class DbStatus(str, Enum):
    NEW = "NEW"                     # just created record in DB
    UPLOADED = "UPLOADED"           # file uploaded to WN, and WN returned file_id/image_id
    PREBURN_FEE = "PREBURN_FEE"     # pre-burnt fee found in the preburn table or new one was sent and all confirmed
    STARTED = "STARTED"             # task started by WN, and WN returned task_id
    DONE = "DONE"                   # both registration and activation txid are received
    ERROR = "ERROR"                 # something went wrong, will try to re-process
    RESTARTED = "RESTARTED"         # task is scheduled to be reprocessed
    DEAD = "DEAD"                   # 10 re-processing attempts failed, will not try to re-process
    REGISTERED = "REGISTERED"       # task is registered, reg ticket txid is received
    BAD = "BAD"
    EXISTING = "EXISTING"


def add_status_to_history_log(task_from_db, wn_service, wn_task_status):
    if not wn_task_status:
        return

    if wn_service == wn.WalletNodeService.CASCADE:
        log_klass = crud.cascade_log
    elif wn_service == wn.WalletNodeService.SENSE:
        log_klass = crud.sense_log
    elif wn_service == wn.WalletNodeService.NFT:
        log_klass = crud.nft_log
    elif wn_service == wn.WalletNodeService.COLLECTION:
        log_klass = crud.collection_log
    else:
        return

    with db_context() as session:
        log = log_klass.get_by_ids(session, task_from_db.id, task_from_db.wn_file_id,
                                   task_from_db.wn_task_id, task_from_db.pastel_id)
        if not log:
            log = schemas.HistoryLogCreate(
                task_id=task_from_db.id,
                wn_file_id=task_from_db.wn_file_id,
                wn_task_id=task_from_db.wn_task_id,
                pastel_id=task_from_db.pastel_id,
                status_messages=wn_task_status,
                created_at=datetime.utcnow(),
            )
            log_klass.create(session, obj_in=log)
        else:
            upd = {
                "status_messages": wn_task_status,
                "updated_at": datetime.utcnow(),
            }
            log_klass.update(session, db_obj=log, obj_in=upd)


def get_status_from_history_log(task_from_db, wn_service):

    if wn_service == wn.WalletNodeService.CASCADE:
        log_klass = crud.cascade_log
    elif wn_service == wn.WalletNodeService.SENSE:
        log_klass = crud.sense_log
    elif wn_service == wn.WalletNodeService.NFT:
        log_klass = crud.nft_log
    elif wn_service == wn.WalletNodeService.COLLECTION:
        log_klass = crud.collection_log
    else:
        return

    with db_context() as session:
        return log_klass.get_by_ids(session, task_from_db.id, task_from_db.wn_file_id,
                                    task_from_db.wn_task_id, task_from_db.pastel_id)


class ReqStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    FAILED = "FAILED"
