import logging
from datetime import datetime

from celery import shared_task

import app.utils.pasteld as psl
from app.core.config import settings
from app import crud
from app.db.session import db_context
import app.utils.walletnode as wn
from app.celery_tasks import cascade

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
    logger.info(f"registration_finisher started")
    with db_context() as session:
        tickets = crud.cascade.get_all_started_not_finished(session)
        for ticket in tickets:
            if ticket.wn_task_id:
                try:
                    wn_task_status = wn.call(False,
                                             f'{ticket.wn_task_id}/history',
                                             {},
                                             [],
                                             {},
                                             "", "")
                except Exception as e:
                    logger.error(f"Call to WalletNode : {e}")
                    wn_task_status = []

                if not wn_task_status:
                    # check how old is the ticket, if height is more than 24 (1 h), then mark it as ERROR
                    height = psl.call("getblockcount", [])
                    if height - ticket.height > 24:
                        upd = {"ticket_status": "ERROR", "updated_at": datetime.utcnow()}
                        crud.cascade.update(session, db_obj=ticket, obj_in=upd)
                        crud.preburn_tx.mark_non_used(session, ticket.burn_txid)
                        logger.error(f"Ticket {ticket.ticket_id} failed")
                    continue

                for step in wn_task_status:
                    status = step['status']
                    if status == 'Task Rejected':
                        # mark ticket as failed, and requires reprocessing
                        upd = {"ticket_status": "ERROR", "updated_at": datetime.utcnow()}
                        crud.cascade.update(session, db_obj=ticket, obj_in=upd)
                        crud.preburn_tx.mark_non_used(session, ticket.burn_txid)
                        logger.error(f"Ticket {ticket.ticket_id} failed")
                        break
                    reg = status.split('Validating Cascade Reg TXID: ', 1)
                    if len(reg) == 2:
                        upd = {"reg_ticket_txid": reg[1], "updated_at": datetime.utcnow()}
                        crud.cascade.update(session, db_obj=ticket, obj_in=upd)
                    reg = status.split('Validated Cascade Reg TXID: ', 1)
                    if len(reg) == 2:
                        upd = {"reg_ticket_txid": reg[1], "updated_at": datetime.utcnow()}
                        crud.cascade.update(session, db_obj=ticket, obj_in=upd)
                    act = status.split('Activated Cascade Action Ticket TXID: ', 1)
                    if len(act) == 2:
                        upd = {"act_ticket_txid": act[2], "ticket_status": "DONE", "updated_at": datetime.utcnow()}
                        crud.cascade.update(session, db_obj=ticket, obj_in=upd)
                        crud.preburn_tx.mark_used(session, ticket.burn_txid)
                        break
                    elif ticket.reg_ticket_txid:
                        act_ticket = psl.call("tickets", ['find', 'action-act', ticket.reg_ticket_txid])
                        if act_ticket and act_ticket['txid']:
                            upd = {
                                "act_ticket_txid": act_ticket['txid'],
                                "ticket_status": "DONE",
                                "updated_at": datetime.utcnow(),
                            }
                            crud.cascade.update(session, db_obj=ticket, obj_in=upd)
                            crud.preburn_tx.mark_used(session, ticket.burn_txid)
                        break


@shared_task(name="registration_re_processor")
def registration_re_processor():
    logger.info(f"registration_finisher started")
    with db_context() as session:
        tickets = crud.cascade.get_all_failed(session)
        for ticket in tickets:
            try:
                if ticket.retry_num and ticket.retry_num > 10:
                    upd = {"ticket_status": "DEAD", "updated_at": datetime.utcnow()}
                    crud.cascade.update(session, db_obj=ticket, obj_in=upd)
                    logger.error(f"Ticket {ticket.id} failed 10 times, marking as DEAD")
                    continue
                if not ticket.ticket_status or ticket.ticket_status == "":
                    if (not ticket.reg_ticket_txid and not ticket.act_ticket_txid) \
                            or not ticket.pastel_id or not ticket.wn_task_id\
                            or not ticket.burn_txid \
                            or not ticket.wn_file_id:
                        start_reprocess(session, ticket)
                if ticket.ticket_status == "ERROR":
                    start_reprocess(session, ticket)
            except Exception as e:
                logger.error(f"Registration reprocessing failed for ticket {ticket.ticket_id} with error {e}")
                continue


def start_reprocess(session, ticket):
    if ticket.retry_num:
        retries = ticket.retry_num + 1
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
    crud.cascade.update(session, db_obj=ticket, obj_in=cleanup)
    # reprocess ticket
    res = (
            cascade.re_register_image.s(ticket.ticket_id) |
            cascade.preburn_fee.s() |
            cascade.process.s()
    ).apply_async()
    logger.info(f"Registration restarted for ticket {ticket.ticket_id} with task id {res.task_id}")
