import logging
from datetime import datetime

from celery import shared_task

import app.utils.pasteld as psl
from app.core.config import settings
from app import crud
from app.db.session import db_context
import app.utils.walletnode as wn
from app.celery_tasks import cascade, sense

logger = logging.getLogger(__name__)


@shared_task(name="fee_pre_burner")
def fee_pre_burner():
    logger.info(f"fee_pre_burner task started")
    with db_context() as session:

        fees = []
        for size in range(1, 11):
            fee = psl.call("storagefee", ["getactionfees", size])
            c_fee = int(fee['cascadefee'] / 5)
            s_fee = int(fee['sensefee'] / 5)
            c_num = crud.preburn_tx.get_number_non_used_by_fee(session, fee=c_fee)
            s_num = crud.preburn_tx.get_number_non_used_by_fee(session, fee=s_fee)
            for dups in reversed(range(size, 11)):
                if c_num < 11-size:
                    fees.append(c_fee)
                if s_num < 11-size:
                    fees.append(s_fee)

        height = psl.call("getblockcount", [])

        for burn_amount in fees:
            balance = psl.call("getbalance", [])
            if balance < burn_amount:
                logger.error(f"Insufficient funds: balance {balance}")
                return
            burn_txid = psl.call("sendtoaddress", [settings.BURN_ADDRESS, burn_amount])
            crud.preburn_tx.create_new(session,
                                       fee=burn_amount,
                                       height=height,
                                       txid=burn_txid)


@shared_task(name="registration_finisher")
def registration_finisher():
    _registration_finisher(
        crud.cascade.get_all_started_not_finished,
        crud.cascade.update,
        crud.cascade.get_by_preburn_txid,
        wn.WalletNodeService.CASCADE,
        "Cascade"
    )
    _registration_finisher(
        crud.sense.get_all_started_not_finished,
        crud.sense.update,
        crud.sense.get_by_preburn_txid,
        wn.WalletNodeService.SENSE,
        "Sense"
    )


def _registration_finisher(
        started_not_finished_func,
        update_task_in_db_func,
        get_by_preburn_txid_func,
        wn_service: wn.WalletNodeService,
        service_name: str):
    logger.info(f"registration_finisher started")
    with db_context() as session:
        tasks_from_db = started_not_finished_func(session)
        for task_from_db in tasks_from_db:
            if task_from_db.wn_task_id:
                try:
                    wn_task_status = wn.call(False,
                                             wn_service,
                                             f'{task_from_db.wn_task_id}/history',
                                             {}, [], {}, "", "")
                except Exception as e:
                    logger.error(f"Call to WalletNode : {e}")
                    wn_task_status = []

                if not wn_task_status:
                    # check how old is the result, if height is more than 48 (2 h), then mark it as ERROR
                    height = psl.call("getblockcount", [])
                    if height - task_from_db.height > 48:
                        mark_task_in_db_as_failed(session, task_from_db, update_task_in_db_func, get_by_preburn_txid_func)
                    continue

                for step in wn_task_status:
                    status = step['status']
                    if status == 'Task Rejected':
                        # mark result as failed, and requires reprocessing
                        mark_task_in_db_as_failed(session, task_from_db, update_task_in_db_func, get_by_preburn_txid_func)
                        break
                    if not task_from_db.reg_ticket_txid:
                        reg = status.split(f'Validating {service_name} Reg TXID: ', 1)
                        if len(reg) != 2:
                            reg = status.split(f'Validated {service_name} Reg TXID: ', 1)
                        if len(reg) == 2:
                            upd = {"reg_ticket_txid": reg[1], "updated_at": datetime.utcnow()}
                            update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                            continue
                    if not task_from_db.act_ticket_txid:
                        if task_from_db.reg_ticket_txid:
                            act_ticket = psl.call("tickets", ['find', 'action-act', task_from_db.reg_ticket_txid])
                            if act_ticket and 'txid' in act_ticket and act_ticket['txid']:
                                upd = {
                                    "act_ticket_txid": act_ticket['txid'],
                                    "ticket_status": "DONE",
                                    "updated_at": datetime.utcnow(),
                                }
                                update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                                crud.preburn_tx.mark_used(session, task_from_db.burn_txid)
                                break
                        act = status.split(f'Activated {service_name} Action Ticket TXID: ', 1)
                        if len(act) == 2:
                            upd = {"act_ticket_txid": act[2], "ticket_status": "DONE", "updated_at": datetime.utcnow()}
                            update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                            crud.preburn_tx.mark_used(session, task_from_db.burn_txid)
                            break


def mark_task_in_db_as_failed(session,
                              task_from_db,
                              update_task_in_db_func,
                              get_by_preburn_txid_func):
    upd = {"ticket_status": "ERROR", "updated_at": datetime.utcnow()}
    update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
    t = get_by_preburn_txid_func(session, txid=task_from_db.burn_txid)
    if not t:
        crud.preburn_tx.mark_non_used(session, task_from_db.burn_txid)
    logger.error(f"Result {task_from_db.ticket_id} failed")


@shared_task(name="registration_re_processor")
def registration_re_processor():

    _registration_re_processor(
        crud.cascade.get_all_failed,
        crud.cascade.update,
        start_reprocess_cascade
    )

    _registration_re_processor(
        crud.sense.get_all_failed,
        crud.sense.update,
        start_reprocess_sense
    )


def _registration_re_processor(all_failed_func, update_task_in_db_func, reprocess_func):
    logger.info(f"registration_re_processor started")
    with db_context() as session:
        tasks_from_db = all_failed_func(session)
        for task_from_db in tasks_from_db:
            try:
                if task_from_db.retry_num and task_from_db.retry_num > 10:
                    upd = {"ticket_status": "DEAD", "updated_at": datetime.utcnow()}
                    update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                    logger.error(f"Result {task_from_db.ticket_id} failed 10 times, marking as DEAD")
                    continue
                if not task_from_db.ticket_status or task_from_db.ticket_status == "":
                    if (not task_from_db.reg_ticket_txid and not task_from_db.act_ticket_txid) \
                            or not task_from_db.pastel_id or not task_from_db.wn_task_id\
                            or not task_from_db.burn_txid \
                            or not task_from_db.wn_file_id:
                        clear_task_in_db(session, task_from_db, update_task_in_db_func)
                        reprocess_func(task_from_db)
                if task_from_db.ticket_status == "ERROR":
                    clear_task_in_db(session, task_from_db, update_task_in_db_func)
                    reprocess_func(task_from_db)
            except Exception as e:
                logger.error(f"Registration reprocessing failed for ticket {task_from_db.ticket_id} with error {e}")
                continue


def clear_task_in_db(session, task_from_db, update_task_in_db_func):
    if task_from_db.retry_num:
        retries = task_from_db.retry_num + 1
    else:
        retries = 1
    cleanup = {
        "wn_file_id": None,
        "wn_fee": 0,
        "burn_txid": None,
        "wn_task_id": None,
        "pastel_id": None,
        "reg_ticket_txid": None,
        "act_ticket_txid": None,
        "ticket_status": None,
        "retry_num": retries,
        "updated_at": datetime.utcnow(),
    }
    update_task_in_db_func(session, db_obj=task_from_db, obj_in=cleanup)


def start_reprocess_cascade(task_from_db):
    res = (
            cascade.re_register_file.s(task_from_db.ticket_id) |
            cascade.preburn_fee.s() |
            cascade.process.s()
    ).apply_async()
    logger.info(f"Cascade Registration restarted for result {task_from_db.ticket_id} with task id {res.task_id}")


def start_reprocess_sense(task_from_db):
    res = (
            sense.re_register_file.s(task_from_db.ticket_id) |
            sense.preburn_fee.s() |
            sense.process.s()
    ).apply_async()
    logger.info(f"Sense Registration restarted for result {task_from_db.ticket_id} with task id {res.task_id}")
