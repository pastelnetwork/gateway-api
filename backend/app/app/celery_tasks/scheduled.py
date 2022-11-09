import logging

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
                wn_task_status = wn.call(False,
                                         f'{ticket.wn_task_id}/history',
                                         {},
                                         [],
                                         {},
                                         "", "")
                for step in wn_task_status:
                    status = step['status']
                    if status == 'Task Rejected':
                        # mark ticket as failed, and requires reprocessing
                        upd = {"ticket_status": "ERROR"}
                        crud.cascade.update(session, db_obj=ticket, obj_in=upd)
                        crud.preburn_tx.mark_unused(session, ticket.preburn_txid)
                        break
                    reg = status.split('Validated Cascade Reg TXID: ', 1)
                    if len(reg) == 2:
                        upd = {"reg_ticket_txid": reg[1]}
                        crud.cascade.update(session, db_obj=ticket, obj_in=upd)
                    act = status.split('Activated Cascade Action Ticket TXID: ', 1)
                    if len(act) == 2:
                        upd = {"act_ticket_txid": act[2], "ticket_status": "DONE"}
                        crud.cascade.update(session, db_obj=ticket, obj_in=upd)
                        crud.preburn_tx.mark_used(session, ticket.preburn_txid)
                        break
                    elif ticket.reg_ticket_txid:
                        act_ticket = psl.call("tickets", ['find', 'action-act', ticket.reg_ticket_txid])
                        if act_ticket and act_ticket['txid']:
                            upd = {"act_ticket_txid": act_ticket['txid'], "ticket_status": "DONE"}
                            crud.cascade.update(session, db_obj=ticket, obj_in=upd)
                            crud.preburn_tx.mark_used(session, ticket.preburn_txid)
                        break


@shared_task(name="registration_re_processor")
def registration_re_processor():
    logger.info(f"registration_finisher started")
    with db_context() as session:
        tickets = crud.cascade.get_all_failed(session)
        for ticket in tickets:
            if ticket.retry_num > 10:
                upd = {"ticket_status": "DEAD"}
                crud.cascade.update(session, db_obj=ticket, obj_in=upd)
                logger.error(f"Ticket {ticket.id} failed 10 times, marking as DEAD")
                continue
            if ticket.ticket_status == "ERROR":
                cleanup = {
                    "wn_file_id": None,
                    "wn_fee": 0,
                    "burn_txid": None,
                    "wn_task_id": None,
                    "pastel_id": None,
                    "reg_ticket_txid": None,
                    "act_ticket_txid": None,
                    "ticket_status": None,
                    "retry_num": ticket.retry_num + 1,
                }
                crud.cascade.update(session, db_obj=ticket, obj_in=cleanup)

                # reprocess ticket
                res = (
                        cascade.re_register_image.s(ticket.ticket_id) |
                        cascade.preburn_fee.s() |
                        cascade.process.s()
                ).apply_async()
                logger.info(f"Registration restarted for ticket {ticket.ticket_id} with task id {res.task_id}")
