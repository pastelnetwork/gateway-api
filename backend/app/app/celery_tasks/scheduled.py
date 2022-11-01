import logging

from celery import shared_task

import app.utils.pasteld as psl
from app.core.config import settings
from app import crud
from app.db.session import db_context
import app.utils.walletnode as wn

logger = logging.getLogger(__name__)


@shared_task(name="preburn_fee")
def preburn_fee():
    logger.info(f"preburn_fee task started")
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
        tasks = crud.cascade.get_all_started_not_finished(session)
        for task in tasks:
            if task.wn_task_id:
                wn_task_status = wn.call(False,
                                         f'{task.wn_task_id}/history',
                                         {},
                                         [],
                                         {},
                                         "", "")
                for step in wn_task_status:
                    status = step['status']
                    if status == 'Task Rejected':
                        # mark ticket as failed, and requires reprocessing
                        upd = {"ticket_status": "ERROR"}
                        crud.cascade.update(session, db_obj=task, obj_in=upd)
                        break
                    reg = status.split('Validated Cascade Reg TXID: ', 1)
                    if len(reg) == 2:
                        upd = {"reg_ticket_txid": reg[1]}
                        crud.cascade.update(session, db_obj=task, obj_in=upd)
                    act = status.split('Activated Cascade Action Ticket TXID: ', 1)
                    if len(act) == 2:
                        upd = {"act_ticket_txid": act[2], "ticket_status": "DONE"}
                        crud.cascade.update(session, db_obj=task, obj_in=upd)
                        break
                    elif task.reg_ticket_txid:
                        act_ticket = psl.call("tickets", ['find', 'action-act', task.reg_ticket_txid])
                        if act_ticket and act_ticket['txid']:
                            upd = {"act_ticket_txid": act_ticket['txid'], "ticket_status": "DONE"}
                            crud.cascade.update(session, db_obj=task, obj_in=upd)
                        break
