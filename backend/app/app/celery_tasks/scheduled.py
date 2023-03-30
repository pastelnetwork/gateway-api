import asyncio
import logging
import traceback
from datetime import datetime

import ipfshttpclient
from celery import shared_task

import app.utils.pasteld as psl
from app.core.config import settings
from app.core.status import DbStatus
from app import crud
from app import schemas
from app.db.session import db_context
import app.utils.walletnode as wn
from app.celery_tasks import cascade, sense
from app.celery_tasks.task_lock import task_lock
from app.models.preburn_tx import PBTXStatus

logger = logging.getLogger(__name__)


@shared_task(name="registration_helpers:registration_finisher")
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
    logger.info(f"{service_name} registration_finisher started")
    with db_context() as session:
        # get all tasks with status "STARTED"
        tasks_from_db = started_not_finished_func(session)
    logger.info(f"{service_name}: Found {len(tasks_from_db)} non finished tasks")
    #
    # TODO: Add finishing logic for tasks stuck with statuses:
    #  "NEW"
    #  "RESTARTED"
    #  "UPLOADED"
    #  "PREBURN_FEE"
    #
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
                logger.error(f"No result from WalletNode: wn_task_id - {task_from_db.wn_task_id}, "
                             f"ResultId - {task_from_db.ticket_id}")
                # check how old is the result, if height is more than 48 (2 h), then mark it as ERROR
                height = psl.call("getblockcount", [])
                if height - task_from_db.height > 48:
                    logger.error(f"Task is too old - it was created {height - task_from_db.height} blocks ago:"
                                 f"wn_task_id - {task_from_db.wn_task_id}, ResultId - {task_from_db.ticket_id}")
                    with db_context() as session:
                        _mark_task_in_db_as_failed(session, task_from_db, update_task_in_db_func,
                                                   get_by_preburn_txid_func)
                continue

            add_status_to_history_log(task_from_db, wn_service, wn_task_status)

            for step in wn_task_status:
                status = step['status']
                logger.info(f"Task status: {status}")
                if status == 'Task Rejected':
                    logger.error(f"Task Rejected: wn_task_id - {task_from_db.wn_task_id}, "
                                 f"ResultId - {task_from_db.ticket_id}")
                    if 'details' in step and step['details']:
                        if 'fields' in step['details'] and step['details']['fields']:
                            if 'error_detail' in step['details']['fields'] and step['details']['fields']['error_detail']:
                                if 'duplicate burnTXID' in step['details']['fields']['error_detail']:
                                    logger.error(f"Task Rejected because of duplicate burnTXID: "
                                                 f"wn_task_id - {task_from_db.wn_task_id}, "
                                                 f"ResultId - {task_from_db.ticket_id}")
                                    with db_context() as session:
                                        crud.preburn_tx.mark_used(session, task_from_db.burn_txid)
                    # mark result as failed, and requires reprocessing
                    with db_context() as session:
                        _mark_task_in_db_as_failed(session, task_from_db, update_task_in_db_func,
                                                   get_by_preburn_txid_func)
                    break
                if not task_from_db.reg_ticket_txid:
                    reg = status.split(f'Validating {service_name} Reg TXID: ', 1)
                    if len(reg) != 2:
                        reg = status.split(f'Validated {service_name} Reg TXID: ', 1)
                    if len(reg) == 2:
                        logger.info(f"Found reg ticket txid: {reg[1]}")
                        upd = {"reg_ticket_txid": reg[1], "updated_at": datetime.utcnow()}
                        with db_context() as session:
                            update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                        continue
                if not task_from_db.act_ticket_txid:
                    if task_from_db.reg_ticket_txid:
                        act_ticket = psl.call("tickets", ['find', 'action-act', task_from_db.reg_ticket_txid])
                        if act_ticket and 'txid' in act_ticket and act_ticket['txid']:
                            logger.info(f"Found act ticket txid from Pastel network: {act_ticket['txid']}")
                            _finalize_registration(task_from_db, act_ticket['txid'], update_task_in_db_func)
                            break
                    act = status.split(f'Activated {service_name} Action Ticket TXID: ', 1)
                    if len(act) == 2:
                        logger.info(f"Found act ticket txid from WalletNode: {act[2]}")
                        _finalize_registration(task_from_db, act[2], update_task_in_db_func)
                        break


def add_status_to_history_log(task_from_db, wn_service, wn_task_status):
    if wn_task_status:
        with db_context() as session:
            if wn_service == wn.WalletNodeService.CASCADE:
                log = schemas.CascadeHistoryLog(
                    wn_file_id=task_from_db.wn_file_id,
                    wn_task_id=task_from_db.wn_task_id,
                    task_status=task_from_db.ticket_status,
                    status_messages=str(wn_task_status),
                    retry_count=task_from_db.retry_num,
                    pastel_id=task_from_db.pastel_id,
                    cascade_task_id=task_from_db.id,
                )
                crud.cascade_log.create(session, obj_in=log)
            elif wn_service == wn.WalletNodeService.SENSE:
                log = schemas.SenseHistoryLog(
                    wn_file_id=task_from_db.wn_file_id,
                    wn_task_id=task_from_db.wn_task_id,
                    task_status=task_from_db.ticket_status,
                    status_messages=str(wn_task_status),
                    retry_count=task_from_db.retry_num,
                    pastel_id=task_from_db.pastel_id,
                    sense_task_id=task_from_db.id,
                )
                crud.sense_log.create(session, obj_in=log)


def _finalize_registration(task_from_db, act_txid, update_task_in_db_func):
    logger.info(f"Finalizing registration: {task_from_db.id}")
    upd = {
        "act_ticket_txid": act_txid,
        "ticket_status": DbStatus.DONE.value,
        "updated_at": datetime.utcnow()
    }
    with db_context() as session:
        update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
        crud.preburn_tx.mark_used(session, task_from_db.burn_txid)


def _mark_task_in_db_as_failed(session,
                               task_from_db,
                               update_task_in_db_func,
                               get_by_preburn_txid_func):
    logger.info(f"Marking task as failed: {task_from_db.id}")
    upd = {"ticket_status": DbStatus.ERROR.value, "updated_at": datetime.utcnow()}
    update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
    t = get_by_preburn_txid_func(session, txid=task_from_db.burn_txid)
    if not t:
        crud.preburn_tx.mark_non_used(session, task_from_db.burn_txid)
    logger.error(f"Result {task_from_db.ticket_id} failed")


@shared_task(name="registration_helpers:registration_re_processor")
def registration_re_processor():

    _registration_re_processor(
        crud.cascade.get_all_failed,
        crud.cascade.update,
        _start_reprocess_cascade,
        "Cascade"
    )

    _registration_re_processor(
        crud.sense.get_all_failed,
        crud.sense.update,
        _start_reprocess_sense,
        "Sense"
    )


def _registration_re_processor(all_failed_func, update_task_in_db_func, reprocess_func, service_name: str):
    logger.info(f"{service_name} registration_re_processor started")
    with db_context() as session:
        tasks_from_db = all_failed_func(session)
    logger.info(f"{service_name}: Found {len(tasks_from_db)} failed tasks")
    for task_from_db in tasks_from_db:
        try:
            if task_from_db.retry_num and task_from_db.retry_num > 10:
                logger.error(f"Result {task_from_db.ticket_id} failed 10 times, marking as DEAD")
                upd = {"ticket_status": DbStatus.DEAD.value, "updated_at": datetime.utcnow()}
                with db_context() as session:
                    crud.preburn_tx.mark_non_used(session, task_from_db.burn_txid)
                    update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                continue
            if not task_from_db.ticket_status or task_from_db.ticket_status == "":
                logger.debug(f"Task status is empty, check if other data is empty too: {task_from_db.ticket_id}")
                if (not task_from_db.reg_ticket_txid and not task_from_db.act_ticket_txid) \
                        or not task_from_db.pastel_id or not task_from_db.wn_task_id\
                        or not task_from_db.burn_txid \
                        or not task_from_db.wn_file_id:
                    logger.debug(f"Task status is empty, clearing and reprocessing: {task_from_db.ticket_id}")
                    _clear_task_in_db(task_from_db, update_task_in_db_func)
                    # clear_task_in_db sets task's status to RESTARTED
                    reprocess_func(task_from_db)
                    continue
                else:
                    logger.debug(f"Task status is empty, but other data is not empty, "
                                 f"marking as {DbStatus.STARTED.value}: {task_from_db.id}")
                    upd = {"ticket_status": DbStatus.STARTED.value, "updated_at": datetime.utcnow()}
                    with db_context() as session:
                        update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)

            if task_from_db.ticket_status == DbStatus.ERROR.value:
                if task_from_db.reg_ticket_txid or task_from_db.act_ticket_txid:
                    logger.debug(f"Task status is {DbStatus.ERROR.value}, "
                                 f"but reg_ticket_txid [{task_from_db.reg_ticket_txid}] or "
                                 f"act_ticket_txid is not empty [{task_from_db.act_ticket_txid}], "
                                 f"marking as {DbStatus.REGISTERED.value}: {task_from_db.ticket_id}")
                    upd = {"ticket_status": DbStatus.REGISTERED.value, "updated_at": datetime.utcnow()}
                    with db_context() as session:
                        update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                    continue
                logger.debug(f"Task status is {DbStatus.ERROR.value}, "
                             f"clearing and reprocessing: {task_from_db.ticket_id}")
                _clear_task_in_db(task_from_db, update_task_in_db_func)
                # clear_task_in_db sets task's status to RESTARTED
                reprocess_func(task_from_db)
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Registration reprocessing failed for ticket {task_from_db.ticket_id} with error {e}")
            continue


def _clear_task_in_db(task_from_db, update_task_in_db_func):
    logger.info(f"Clearing task: {task_from_db.ticket_id}")
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
        "ticket_status": DbStatus.RESTARTED.value,
        "retry_num": retries,
        "updated_at": datetime.utcnow()
    }
    with db_context() as session:
        if task_from_db.burn_txid:
            crud.preburn_tx.mark_non_used(session, task_from_db.burn_txid)
        update_task_in_db_func(session, db_obj=task_from_db, obj_in=cleanup)


def _start_reprocess_cascade(task_from_db):
    res = (
            cascade.re_register_file.s(task_from_db.ticket_id) |
            cascade.preburn_fee.s() |
            cascade.process.s()
    ).apply_async()
    logger.info(f"Cascade Registration restarted for result {task_from_db.ticket_id} with task id {res.task_id}")


def _start_reprocess_sense(task_from_db):
    res = (
            sense.re_register_file.s(task_from_db.ticket_id) |
            sense.preburn_fee.s() |
            sense.process.s()
    ).apply_async()
    logger.info(f"Sense Registration restarted for result {task_from_db.ticket_id} with task id {res.task_id}")


@shared_task(name="scheduled_tools:fee_pre_burner")
def fee_pre_burner():
    logger.info(f"fee_pre_burner task started")
    logger.info(f"first: release non used")
    with db_context() as session:
        all_used = crud.preburn_tx.get_all_used(session)
        for used in all_used:
            if used.status != PBTXStatus.USED:
                continue
            tx = psl.call("tickets", ["find", "nft", used.txid])
            if tx and (isinstance(tx, dict) or isinstance(tx, list)):
                continue
            tx = psl.call("tickets", ["find", "action", used.txid])
            if tx and (isinstance(tx, dict) or isinstance(tx, list)):
                continue
            from_cascade = crud.cascade.get_by_preburn_txid(session, txid=used.txid)
            if from_cascade and from_cascade.ticket_status != 'DEAD':
                continue
            from_sense = crud.sense.get_by_preburn_txid(session, txid=used.txid)
            if from_sense and from_sense.ticket_status != 'DEAD':
                continue
            crud.preburn_tx.mark_non_used(session, used.txid)

    with db_context() as session:
        all_new = crud.preburn_tx.get_all_new(session)
        for new in all_new:
            tx = psl.call("tickets", ["find", "nft", new.txid])
            if not tx or (not isinstance(tx, dict) and not isinstance(tx, list)):
                tx = psl.call("tickets", ["find", "action", new.txid])
                if not tx or (not isinstance(tx, dict) and not isinstance(tx, list)):
                    continue
            crud.preburn_tx.mark_used(session, new.txid)

    with db_context() as session:
        fees = []
        logger.info(f"second: calculate fees")
        for size in range(1, 11):
            fee = psl.call("storagefee", ["getactionfees", size])
            c_fee = int(fee['cascadefee'] / 5)
            s_fee = int(fee['sensefee'] / 5)
            c_num = crud.preburn_tx.get_number_non_used_by_fee(session, fee=c_fee)
            s_num = crud.preburn_tx.get_number_non_used_by_fee(session, fee=s_fee)
            logger.debug(f"For size {size} c_fee = {c_fee} s_fee = {s_fee}")
            for dups in reversed(range(size, 11)):
                if c_num < 11-size:
                    fees.append(c_fee)
                if s_num < 11-size:
                    fees.append(s_fee)

    height = psl.call("getblockcount", [])

    logger.info(f"third: burn fees")
    with db_context() as session:
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


@shared_task(name="scheduled_tools:reg_tickets_finder", task_id="reg_tickets_finder")
@task_lock(main_key="registration_tickets_finder", timeout=5*60)
def registration_tickets_finder():
    logger.info(f"cascade_tickets_finder started")
    tickets = []
    try:
        with db_context() as session:
            last_processed_block = crud.reg_ticket.get_last_blocknum(session)
            tickets = psl.call("tickets", ['list', 'action', 'active', last_processed_block+1], nothrow=True)
        if not tickets:
            logger.info(f"No new tickets found after block {last_processed_block}")
            return
        logger.info(f"Fount {len(tickets)} new tickets after block {last_processed_block}")
        for ticket in tickets:
            parsed_ticket = asyncio.run(psl.parse_registration_action_ticket(ticket,
                                                                             "action-reg",
                                                                             ["cascade", "sense"]))
            if parsed_ticket:
                with db_context() as session:
                    if 'txid' not in parsed_ticket:
                        continue
                    reg_ticket_txid = parsed_ticket['txid']
                    if 'data_hash' not in parsed_ticket['ticket']['action_ticket']['api_ticket']:
                        continue
                    data_hash = parsed_ticket['ticket']['action_ticket']['api_ticket']['data_hash']

                    height = parsed_ticket['height'] if 'height' in parsed_ticket else 0

                    file_name = parsed_ticket['ticket']['action_ticket']['api_ticket']['file_name'] \
                        if 'file_name' in parsed_ticket['ticket']['action_ticket']['api_ticket'] else ''

                    is_public = parsed_ticket['ticket']['action_ticket']['api_ticket']['make_publicly_accessible'] \
                        if 'make_publicly_accessible' \
                           in parsed_ticket['ticket']['action_ticket']['api_ticket'] else False

                    ticket_type = parsed_ticket['ticket']['action_ticket']['action_type'] \
                        if 'action_type' in parsed_ticket['ticket']['action_ticket'] else ''

                    caller_pastel_id = parsed_ticket['ticket']['action_ticket']['caller'] \
                        if 'caller' in parsed_ticket['ticket']['action_ticket'] else ''

                    crud.reg_ticket.create_new(session,
                                               reg_ticket_txid=reg_ticket_txid,
                                               data_hash=data_hash,
                                               blocknum=height,
                                               file_name=file_name,
                                               ticket_type=ticket_type,
                                               caller_pastel_id=caller_pastel_id,
                                               is_public=is_public)

    except Exception as e:
        logger.error(f"Error while processing cascade tickets {e}")

    logger.info(f"cascade_tickets_finder done, processed {len(tickets)} tickets")
