import asyncio
import json
import logging
import traceback
from datetime import datetime

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
from app.utils.filestorage import store_file_into_local_cache
from app.utils.ipfs_tools import store_file_to_ipfs
from app.utils.authentication import send_alert_email

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
    _registration_finisher(
        crud.nft.get_all_started_not_finished,
        crud.nft.update,
        crud.nft.get_by_preburn_txid,
        wn.WalletNodeService.NFT,
        "NFT"
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
    if wn_service == wn.WalletNodeService.CASCADE or wn_service == wn.WalletNodeService.SENSE:
        verb = "action-act"
    else:    # if wn_service == wn.WalletNodeService.NFT:
        verb = "act"

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
                        act_ticket = psl.call("tickets", ['find', verb, task_from_db.reg_ticket_txid])
                        if act_ticket and 'txid' in act_ticket and act_ticket['txid']:
                            logger.info(f"Found act ticket txid from Pastel network: {act_ticket['txid']}")
                            _finalize_registration(task_from_db, act_ticket['txid'], update_task_in_db_func, wn_service)
                            break
                    act = status.split(f'Activated {service_name} Registration Ticket TXID: ', 1)
                    if len(act) == 2:
                        logger.info(f"Found act ticket txid from WalletNode: {act[2]}")
                        _finalize_registration(task_from_db, act[2], update_task_in_db_func, wn_service)
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
            elif wn_service == wn.WalletNodeService.NFT:
                log = schemas.NftHistoryLog(
                    wn_file_id=task_from_db.wn_file_id,
                    wn_task_id=task_from_db.wn_task_id,
                    task_status=task_from_db.ticket_status,
                    status_messages=str(wn_task_status),
                    retry_count=task_from_db.retry_num,
                    pastel_id=task_from_db.pastel_id,
                    nft_task_id=task_from_db.id,
                )
                crud.nft_log.create(session, obj_in=log)


def _finalize_registration(task_from_db, act_txid, update_task_in_db_func, wn_service: wn.WalletNodeService):
    logger.info(f"Finalizing registration: {task_from_db.id}")

    stored_file_ipfs_link = task_from_db.stored_file_ipfs_link
    if wn_service == wn.WalletNodeService.NFT:
        nft_dd_file_ipfs_link = task_from_db.nft_dd_file_ipfs_link
    try:
        file_bytes = asyncio.run(wn.get_file_from_pastel(reg_ticket_txid=task_from_db.reg_ticket_txid,
                                                         wn_service=wn_service))
        if file_bytes:
            cached_result_file = asyncio.run(store_file_into_local_cache(
                reg_ticket_txid=task_from_db.reg_ticket_txid,
                file_bytes=file_bytes))
            if not task_from_db.stored_file_ipfs_link:
                # store_file_into_local_cache throws exception, so if we are here, file is in local cache
                stored_file_ipfs_link = asyncio.run(store_file_to_ipfs(cached_result_file))

        if wn_service == wn.WalletNodeService.NFT:
            dd_data = asyncio.run(wn.get_nft_dd_result_from_pastel(reg_ticket_txid=task_from_db.reg_ticket_txid))
            if dd_data:
                if isinstance(dd_data, dict):
                    dd_bytes = json.dumps(dd_data).encode('utf-8')
                else:
                    dd_bytes = dd_data.encode('utf-8')
                cached_dd_file = asyncio.run(store_file_into_local_cache(
                    reg_ticket_txid=task_from_db.reg_ticket_txid,
                    file_bytes=dd_bytes,
                    extra_suffix=".dd"))
                if not task_from_db.nft_dd_file_ipfs_link:
                    # store_file_into_local_cache throws exception, so if we are here, file is in local cache
                    nft_dd_file_ipfs_link = asyncio.run(store_file_to_ipfs(cached_dd_file))

    except Exception as e:
        logger.error(f"Failed to get file from Pastel: {e}")

    upd = {
        "act_ticket_txid": act_txid,
        "ticket_status": DbStatus.DONE.value,
        "stored_file_ipfs_link": stored_file_ipfs_link,
        "updated_at": datetime.utcnow()
    }
    if wn_service == wn.WalletNodeService.NFT:
        upd["nft_dd_file_ipfs_link"] = nft_dd_file_ipfs_link

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

    _registration_re_processor(
        crud.nft.get_all_failed,
        crud.nft.update,
        _start_reprocess_nft,
        "NFT"
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


def _start_reprocess_nft(task_from_db):
    res = (
            sense.re_register_file.s(task_from_db.ticket_id) |
            sense.process.s()
    ).apply_async()
    logger.info(f"NFT Registration restarted for result {task_from_db.ticket_id} with task id {res.task_id}")


@shared_task(name="scheduled_tools:fee_pre_burner")
def fee_pre_burner():
    logger.info(f"fee_pre_burner task started")
    logger.info(f"first: release non used")
    with db_context() as session:
        all_used_or_pending = crud.preburn_tx.get_all_used_or_pending(session)
        for transaction in all_used_or_pending:
            tx = psl.call("tickets", ["find", "nft", transaction.txid])
            if tx and (isinstance(tx, dict) or isinstance(tx, list)):
                continue
            tx = psl.call("tickets", ["find", "action", transaction.txid])
            if tx and (isinstance(tx, dict) or isinstance(tx, list)):
                continue
            from_cascade = crud.cascade.get_by_preburn_txid(session, txid=transaction.txid)
            if from_cascade and from_cascade.ticket_status != 'DEAD':
                continue
            from_sense = crud.sense.get_by_preburn_txid(session, txid=transaction.txid)
            if from_sense and from_sense.ticket_status != 'DEAD':
                continue
            crud.preburn_tx.mark_non_used(session, transaction.txid)

    with db_context() as session:
        all_new = crud.preburn_tx.get_all_new(session)
        for new in all_new:
            tx = psl.call("tickets", ["find", "nft", new.txid])
            if not tx or (not isinstance(tx, dict) and not isinstance(tx, list)):
                tx = psl.call("tickets", ["find", "action", new.txid])
                if not tx or (not isinstance(tx, dict) and not isinstance(tx, list)):
                    tx = psl.call("getrawtransaction", [new.txid], True)
                    if not tx or not isinstance(tx, str):
                            # tx.status_code != 200 or (isinstance(tx, dict) and (tx.get('error') or tx.get('result') is None)):
                        crud.preburn_tx.mark_bad(session, new.txid)
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
                send_alert_email(f"Insufficient funds: balance {balance}")
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
    try:
        with db_context() as session:
            last_processed_block = crud.reg_ticket.get_last_blocknum(session)

        nft_tickets = psl.call("tickets", ['list', 'nft', 'active', last_processed_block+1], nothrow=True)
        process_nft_tickets(nft_tickets, last_processed_block)

        action_ticket = psl.call("tickets", ['list', 'action', 'active', last_processed_block+1], nothrow=True)
        process_action_tickets(action_ticket, last_processed_block)


    except Exception as e:
        logger.error(f"Error while processing cascade tickets {e}")


def get_value_from_nft_app_ticket(ticket, key, def_value) -> (str, bool):
    if key in ticket['ticket']['nft_ticket']['app_ticket']:
        return ticket['ticket']['nft_ticket']['app_ticket'][key], True
    else:
        return def_value, False


def get_value_from_nft_ticket(ticket, key, def_value) -> (str, bool):
    if key in ticket['ticket']['nft_ticket']:
        return ticket['ticket']['nft_ticket'][key], True
    else:
        return def_value, False


def get_value_from_action_api_ticket(ticket, key, def_value) -> (str, bool):
    if key in ticket['ticket']['action_ticket']['api_ticket']:
        return ticket['ticket']['action_ticket']['api_ticket'][key], True
    else:
        return def_value, False


def get_value_from_action_ticket(ticket, key, def_value) -> (str, bool):
    if key in ticket['ticket']['action_ticket']:
        return ticket['ticket']['action_ticket'][key], True
    else:
        return def_value, False


def process_nft_tickets(tickets, last_processed_block):
    if not tickets:
        logger.info(f"No new tickets found after block {last_processed_block}")
        return
    logger.info(f"Fount {len(tickets)} new tickets after block {last_processed_block}")
    for ticket in tickets:
        parsed_ticket = asyncio.run(psl.parse_registration_nft_ticket(ticket))
        if parsed_ticket:
            with db_context() as session:
                if 'txid' not in parsed_ticket:
                    continue
                reg_ticket_txid = parsed_ticket['txid']

                data_hash, found = get_value_from_nft_app_ticket(parsed_ticket, 'data_hash', '')
                if not found:
                    continue

                height = parsed_ticket['height'] if 'height' in parsed_ticket else 0

                file_name, _ = get_value_from_nft_app_ticket(parsed_ticket, 'file_name', '')
                is_public, _ = get_value_from_nft_app_ticket(parsed_ticket, 'make_publicly_accessible', False)
                author_pastel_id, _ = get_value_from_nft_ticket(parsed_ticket, 'author', '')

                crud.reg_ticket.create_new(session,
                                           reg_ticket_txid=reg_ticket_txid,
                                           data_hash=data_hash,
                                           blocknum=height,
                                           file_name=file_name,
                                           ticket_type='nft',
                                           caller_pastel_id=author_pastel_id,
                                           is_public=is_public)
    logger.info(f"process_nft_tickets done, processed {len(tickets)} tickets")


def process_action_tickets(tickets, last_processed_block):
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

                data_hash, found = get_value_from_action_api_ticket(parsed_ticket, 'data_hash', '')
                if not found:
                    continue

                height = parsed_ticket['height'] if 'height' in parsed_ticket else 0

                file_name, _ = get_value_from_action_api_ticket(parsed_ticket, 'file_name', '')
                is_public, _ = get_value_from_action_api_ticket(parsed_ticket, 'make_publicly_accessible', False)
                caller_pastel_id, _ = get_value_from_action_ticket(parsed_ticket, 'caller', '')
                ticket_type, _ = get_value_from_action_ticket(parsed_ticket, 'action_type', '')

                crud.reg_ticket.create_new(session,
                                           reg_ticket_txid=reg_ticket_txid,
                                           data_hash=data_hash,
                                           blocknum=height,
                                           file_name=file_name,
                                           ticket_type=ticket_type,
                                           caller_pastel_id=caller_pastel_id,
                                           is_public=is_public)
    logger.info(f"process_action_tickets done, processed {len(tickets)} tickets")


@shared_task(name="scheduled_tools:ticket_activator")
def ticket_activator():
    _ticket_activator(
        crud.cascade.get_all_in_registered_state,
        crud.cascade.update,
        wn.WalletNodeService.CASCADE,
        "Cascade"
    )
    _ticket_activator(
        crud.sense.get_all_in_registered_state,
        crud.sense.update,
        wn.WalletNodeService.SENSE,
        "Sense"
    )
    _ticket_activator(
        crud.nft.get_all_in_registered_state,
        crud.nft.update,
        wn.WalletNodeService.NFT,
        "NFT"
    )


def _ticket_activator(all_in_registered_state_func,
                      update_task_in_db_func,
                      service: wn.WalletNodeService,
                      service_name: str):
    logger.info(f"ticket_activator task started")
    with db_context() as session:
        tasks_from_db = all_in_registered_state_func(session)
    logger.info(f"{service_name}: Found {len(tasks_from_db)} registered, but not activated tasks")
    for task_from_db in tasks_from_db:
        if task_from_db.pastel_id is None:
            upd = {"ticket_status": DbStatus.DEAD.value, "updated_at": datetime.utcnow()}
            with db_context() as session:
                update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
            continue
        if settings.PASTEL_ID != task_from_db.pastel_id:
            logger.info(f"{service_name}: Skipping ticket {task_from_db.reg_ticket_txid}, "
                        f"caller pastel_id {task_from_db.pastel_id} is not ours")
            continue
        try:
            logger.info(f"{service_name}: Parsing registration ticket {task_from_db.reg_ticket_txid}")
            reg_ticket = parse_registration_ticket(task_from_db.reg_ticket_txid, service_name.lower())
            if not reg_ticket:
                logger.error(f"{service_name}: Error while parsing registration ticket {task_from_db.reg_ticket_txid}")
                continue
            if 'ticket' in reg_ticket and 'action_ticket' in reg_ticket['ticket'] and \
                    'blocknum' in reg_ticket['ticket']['action_ticket']:
                height = reg_ticket['ticket']['action_ticket']['blocknum']
            else:
                height = task_from_db.height

            if service == wn.WalletNodeService.NFT:
                ticket_type = 'act'
            else:
                ticket_type = 'action-act'
            logger.info(f"{service_name}: Activating registration ticket {task_from_db.reg_ticket_txid}")
            act_txid = create_activation_ticket(task_from_db, height, ticket_type)
            if act_txid:
                upd = {
                    "act_ticket_txid": act_txid,
                    "ticket_status": DbStatus.DONE.value,
                    "updated_at": datetime.utcnow(),
                    "height": height,
                }
                with db_context() as session:
                    update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
        except Exception as e:
            logger.error(f"Error while creating activation for registration ticket {task_from_db.reg_ticket_txid}: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                error_msg = e.response.text
                msg = f"The Action Registration ticket with this txid [{task_from_db.reg_ticket_txid}] is invalid"
                if msg in error_msg:
                    upd = {"ticket_status": DbStatus.DEAD.value, "updated_at": datetime.utcnow()}
                    with db_context() as session:
                        update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)


def create_activation_ticket(task_from_db, height, ticket_type):
    activation_ticket = psl.call('tickets', ['register', ticket_type,
                                             task_from_db.reg_ticket_txid,
                                             height,
                                             task_from_db.wn_fee,
                                             settings.PASTEL_ID,
                                             settings.PASTEL_ID_PASSPHRASE]
                                 )
    if activation_ticket and 'txid' in activation_ticket:
        logger.info(f"Created {ticket_type} ticket {activation_ticket['txid']}")
        return activation_ticket['txid']
    else:
        logger.error(f"Error while creating {ticket_type} ticket {activation_ticket}")
        return None


def parse_registration_ticket(reg_txid, expected_action_type):
    try:
        reg_ticket = psl.call("tickets", ['get', reg_txid])
        return asyncio.run(psl.parse_registration_action_ticket(reg_ticket, "action-reg", [expected_action_type]))
    except Exception as e:
        logger.error(f"Invalid action-reg ticket {reg_txid}")
    return None


@shared_task(name="scheduled_tools:watchdog")
def watchdog():
    logger.info(f"watchdog task started")
    logger.info(f"watchdog task ended")
