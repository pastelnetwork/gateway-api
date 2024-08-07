import asyncio
from datetime import datetime
import re

from celery import shared_task
from celery.utils.log import get_task_logger

from app import crud
from app.core.config import settings
from app.core.status import DbStatus
from app.db.session import db_context
from app.celery_tasks.task_lock import task_lock
from app.celery_tasks.pastel_tasks import check_preburn_tx
import app.utils.pasteld as psl
import app.utils.walletnode as wn
from app.celery_tasks.registration_helpers import finalize_registration
from app.models.preburn_tx import PBTXStatus
from app.utils.secret_manager import get_pastelid_pwd

logger = get_task_logger(__name__)


@shared_task(name="scheduled_tools:fee_pre_burner")
def fee_pre_burner():
    if settings.ACCOUNT_MANAGER_ENABLED:  # throw and exception if account manager is enabled
        raise Exception("Account manager and fee pre burner can't be enabled at the same time")

    logger.info(f"fee_pre_burner task started")
    if settings.FEE_PRE_BURNER_RELEASE_NON_USED:
        logger.info(f"release non used")
        with db_context() as session:
            all_used_or_pending = crud.preburn_tx.get_all_used_or_pending(session)
            for transaction in all_used_or_pending:
                tx = psl.call("tickets", ["find", "nft", transaction.txid], True)   # won't throw exception
                if tx and (isinstance(tx, dict) or isinstance(tx, list)):
                    if transaction.status == PBTXStatus.PENDING:
                        crud.preburn_tx.mark_used(session, transaction.txid)
                    continue
                tx = psl.call("tickets", ["find", "action", transaction.txid], True)   # won't throw exception
                if tx and (isinstance(tx, dict) or isinstance(tx, list)):
                    if transaction.status == PBTXStatus.PENDING:
                        crud.preburn_tx.mark_used(session, transaction.txid)
                    continue
                from_cascade = crud.cascade.get_by_preburn_txid(session, txid=transaction.txid)
                if from_cascade and (from_cascade.process_status != 'DEAD' and from_cascade.process_status != 'ERROR'):
                    if transaction.status == PBTXStatus.PENDING:
                        crud.preburn_tx.mark_used(session, transaction.txid)
                    continue
                from_sense = crud.sense.get_by_preburn_txid(session, txid=transaction.txid)
                if from_sense and (from_sense.process_status != 'DEAD' and from_sense.process_status != 'ERROR'):
                    if transaction.status == PBTXStatus.PENDING:
                        crud.preburn_tx.mark_used(session, transaction.txid)
                    continue
                crud.preburn_tx.mark_non_used(session, transaction.txid)

    if settings.FEE_PRE_BURNER_CHECK_NEW:
        logger.info(f"check new")
        height = psl.call("getblockcount", [], True)   # won't throw exception
        if not height or not isinstance(height, int):
            logger.error(f"Error while getting height from cNode")
            return

        with db_context() as session:
            all_new = crud.preburn_tx.get_all_new(session)
            for new in all_new:
                if new.height + 5 < height:
                    check_preburn_tx(session, new.txid)

    if settings.FEE_PRE_BURNER_ENABLED:
        logger.info(f"pre burn fees")
        fees = []
        with db_context() as session:
            logger.info(f"first: calculate missing fees")
            for size in range(1, settings.MAX_SIZE_FOR_PREBURN+1):
                fee = psl.call("storagefee", ["getactionfees", size], True)   # won't throw exception
                if not fee or not isinstance(fee, dict):
                    logger.error(f"Error while getting fee for size {size}")
                    continue
                if 'cascadefee' not in fee or 'sensefee' not in fee:
                    logger.error(f"Error while getting fee for size {size}")
                    continue
                c_fee = float(fee['cascadefee'] / 5)
                s_fee = float(fee['sensefee'] / 5)
                c_num = crud.preburn_tx.get_number_non_used_by_fee(session, fee=c_fee)
                s_num = crud.preburn_tx.get_number_non_used_by_fee(session, fee=s_fee)
                logger.info(f"For size {size} c_fee = {c_fee} s_fee = {s_fee}")
                for _ in reversed(range(size, settings.MAX_SIZE_FOR_PREBURN+1)):
                    if c_num < settings.MAX_SIZE_FOR_PREBURN-size+1:
                        fees.append(c_fee)
                    if s_num < settings.MAX_SIZE_FOR_PREBURN-size+1:
                        fees.append(s_fee)

        height = psl.call("getblockcount", [], True)   # won't throw exception
        if not height or not isinstance(height, int):
            logger.error(f"Error while getting height from cNode")
            return

        if len(fees) > 0:
            logger.info(f"second: burn missing fees")
            with db_context() as session:
                for burn_amount in fees:
                    try:
                        if not psl.check_balance(burn_amount):  # can throw exception here
                            return
                        burn_txid = psl.call("sendtoaddress", [settings.BURN_ADDRESS, burn_amount])  # can throw exception
                        if not burn_txid or not isinstance(burn_txid, str):
                            logger.error(f"Error while burning fee")
                            continue
                    except Exception as e:
                        logger.error(f"Error while burning fee {e}")
                        continue
                    crud.preburn_tx.create_new(session, fee=burn_amount, height=height, txid=burn_txid)


@shared_task(name="scheduled_tools:reg_tickets_finder", task_id="reg_tickets_finder")
@task_lock(main_key="registration_tickets_finder", timeout=5*60)
def registration_tickets_finder():
    if settings.ACCOUNT_MANAGER_ENABLED:  # throw and exception if account manager is enabled
        raise Exception("Account manager and registration ticket finder can't be enabled at the same time")

    logger.info(f"cascade_tickets_finder started")
    try:
        with db_context() as session:
            last_processed_block = crud.reg_ticket.get_last_blocknum(session)

        nft_tickets = psl.call("tickets", ['list', 'nft', 'active', last_processed_block+1],
                               nothrow=True)   # won't throw exception
        process_nft_tickets(nft_tickets, last_processed_block)

        action_ticket = psl.call("tickets", ['list', 'action', 'active', last_processed_block+1],
                                 nothrow=True)   # won't throw exception
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
    if settings.ACCOUNT_MANAGER_ENABLED:  # throw and exception if account manager is enabled
        raise Exception("Account manager and ticket activator can't be enabled at the same time")

    _ticket_activator(
        crud.cascade.get_all_in_registered_state,
        crud.cascade.update,
        'action-act',
        wn.WalletNodeService.CASCADE
    )
    _ticket_activator(
        crud.sense.get_all_in_registered_state,
        crud.sense.update,
        'action-act',
        wn.WalletNodeService.SENSE
    )
    _ticket_activator(
        crud.nft.get_all_in_registered_state,
        crud.nft.update,
        'act',
        wn.WalletNodeService.NFT
    )
    _ticket_activator(
        crud.collection.get_all_in_registered_state,
        crud.collection.update,
        'collection-act',
        wn.WalletNodeService.COLLECTION
    )


def _ticket_activator(all_in_registered_state_func,
                      update_task_in_db_func,
                      act_ticket_type,
                      service: wn.WalletNodeService):
    logger.info(f"ticket_activator task started")
    try:
        mempoolinfo = psl.call("getmempoolinfo", [])
        if mempoolinfo and "size" in mempoolinfo and mempoolinfo["size"] > 20:
            logger.info(f"{service}: mempool is too big {mempoolinfo['size']}, skipping")
            return
    except Exception as e:
        logger.error(f"{service}: Can't get mem pool info: {e}")
        return
    with db_context() as session:
        tasks_from_db = all_in_registered_state_func(session, limit=settings.REGISTRATION_RE_PROCESSOR_LIMIT)
    logger.info(f"{service}: Found {len(tasks_from_db)} registered, but not activated tasks")
    for task_from_db in tasks_from_db:
        if task_from_db.pastel_id is None:
            logger.error(f"{service}: Don't know pastel_id, marking task as DEAD. ResultID = {task_from_db.result_id}")
            upd = {"process_status": DbStatus.DEAD.value, "updated_at": datetime.utcnow(),
                   "process_status_message": f"Don't know pastel_id - {task_from_db.pastel_id}"}
            with db_context() as session:
                update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
            continue
        if not get_pastelid_pwd(task_from_db.pastel_id):
            logger.info(f"{service}: Skipping ticket {task_from_db.reg_ticket_txid}, "
                        f"caller pastel_id {task_from_db.pastel_id} is not ours")
            continue
        try:
            network_height = psl.call("getblockcount", [])   # can throw exception here

            msg = f"{service}: Check if registration ticket {task_from_db.reg_ticket_txid} is valid..."
            logger.info(msg)
            at_status = asyncio.run(psl.check_ticket_transaction(task_from_db.reg_ticket_txid, msg, 
                                                                 network_height, task_from_db.height))
            if at_status == psl.TicketTransactionStatus.NOT_FOUND:
                upd = {"process_status": DbStatus.ERROR.value, "retry_num": 0,
                       "updated_at": datetime.utcnow(),
                       "reg_ticket_txid": "", "act_ticket_txid": "",
                       "process_status_message": "existing registration ticket txid invalid and can't create new"}
                with db_context() as session:
                    update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                continue
            elif at_status == psl.TicketTransactionStatus.WAITING:
                continue

            logger.info(f"{service}: Parsing registration ticket {task_from_db.reg_ticket_txid} to find height")

            called_at_height, reg_ticket_height, msg = parse_registration_ticket(task_from_db.reg_ticket_txid, service)
            if not reg_ticket_height or reg_ticket_height == -1:
                logger.warn(
                    f"{service}: Registration ticket is not confirmed in blockchain yet. {msg}. "
                    f"Skipping for now. ResultID = {task_from_db.result_id}")
                upd = {"updated_at": datetime.utcnow(), "process_status_message": msg}
                with db_context() as session:
                    update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                continue

            logger.info(f"{service}: Check if activation ticket already exists for "
                        f"registration ticket: {task_from_db.reg_ticket_txid}")
            if task_from_db.act_ticket_txid:
                act_txid = task_from_db.act_ticket_txid
            else:
                act_txid = find_activation_ticket(task_from_db.reg_ticket_txid, act_ticket_type)
            if act_txid:
                msg = f"{service}: Activation ticket transaction {act_txid} for registration ticket " \
                      f"{task_from_db.reg_ticket_txid}"

                logger.info(f"{msg} already created. Check if it's valid...")
                at_status = asyncio.run(psl.check_ticket_transaction(act_txid, msg, network_height, reg_ticket_height))
                if at_status == psl.TicketTransactionStatus.CONFIRMED:
                    finalize_registration(task_from_db, act_txid, update_task_in_db_func, service)
                    continue
                elif at_status == psl.TicketTransactionStatus.WAITING:
                    continue

            # either activation ticket or its transaction is not found, will try to create activation ticket
            if network_height - reg_ticket_height < 10:
                logger.info(f"{service}: There are {network_height - reg_ticket_height} blocks after "
                            f"Registration ticket {task_from_db.reg_ticket_txid} was registered. "
                            f"Waiting for 10 blocks before finalizing - WN can still finish it")
                continue

            logger.info(f"{service}: Activating registration ticket {task_from_db.reg_ticket_txid}")
            result, found_value = psl.create_activation_ticket(task_from_db, called_at_height,
                                                               act_ticket_type)
            if result == psl.TicketCreateStatus.CREATED and found_value:
                # setting activation ticket txid in db, but not finalizing yet (keep in registered state)
                upd = {"act_ticket_txid": found_value, "updated_at": datetime.utcnow(),
                       "process_status_message": "new activation ticket created"}
            elif result == psl.TicketCreateStatus.ALREADY_EXIST:
                # try to find existing activation ticket
                existing_act_txid = find_activation_ticket(task_from_db.reg_ticket_txid, act_ticket_type)
                if existing_act_txid:
                    # set act_ticket in db, but keep in registered state
                    upd = {"act_ticket_txid": existing_act_txid, "updated_at": datetime.utcnow(),
                           "process_status_message": "found existing activation ticket"}
                else:
                    # something's wrong. set into BAD state
                    upd = {"process_status": DbStatus.BAD.value, "updated_at": datetime.utcnow(),
                           "process_status_message": "existing activation ticket txid invalid but can't find it"}
                    if found_value:
                        upd["act_ticket_txid"] = found_value
            elif result == psl.TicketCreateStatus.WRONG_FEE and found_value:
                upd = {"wn_fee": found_value, "updated_at": datetime.utcnow(),
                       "process_status_message": f"Storage fee mismatch. Setting it to {found_value}"}
                with db_context() as session:
                    update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
            else:
                # clear act_ticket_txid in db, but keep in registered state
                upd = {"act_ticket_txid": "", "updated_at": datetime.utcnow(),
                       "process_status_message": "existing activation ticket txid invalid and can't create new"}
            with db_context() as session:
                update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)

        except Exception as e:
            logger.error(f"Error while creating activation for registration ticket {task_from_db.reg_ticket_txid}: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                error_msg = e.response.text
                msg = f"The Action Registration ticket with this txid [{task_from_db.reg_ticket_txid}] is invalid"
                if msg in error_msg:
                    upd = {"process_status": DbStatus.DEAD.value, "updated_at": datetime.utcnow(),
                           "process_status_message": msg}
                    with db_context() as session:
                        update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                        continue
                msg = f"The storage fee [{task_from_db.wn_fee}] is not matching the storage fee ["
                if msg in error_msg:
                    matches = re.findall(r'\[(.*?)]', error_msg)
                    second_bracket_value = matches[1] if len(matches) > 1 else None
                    if second_bracket_value:
                        upd = {"wn_fee": second_bracket_value, "updated_at": datetime.utcnow(),
                               "process_status_message": f"Storage fee mismatch. Setting it to {second_bracket_value}"}
                        logger.error(f"{service}: Wrong fee for ticket ({task_from_db.wn_fee}), "
                                     f"correct fee is {second_bracket_value}")
                        with db_context() as session:
                            update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                            continue



def find_activation_ticket(txid: str, ticket_type: str) -> str | None:
    try:
        act_ticket = psl.call("tickets", ["find", ticket_type, txid])   # can throw exception here
    except Exception as e:
        logger.error(f"Exception calling pastled to find {ticket_type} ticket: {e}")
        return None
    if act_ticket and isinstance(act_ticket, dict) and 'txid' in act_ticket and act_ticket['txid']:
        logger.info(f"Found activation ticket txid from Pastel network: {act_ticket['txid']}")
        return act_ticket['txid']
    return None


def parse_registration_ticket(reg_txid, service: wn.WalletNodeService) -> (int | None, int | None, str | None):
    try:
        reg_ticket = psl.call("tickets", ['get', reg_txid])   # can throw exception here
    except psl.PasteldException as pe:
        if pe.message == 'No information available about transaction':
            err_msg = f"Registration ticket {reg_txid} not found"
        else:
            err_msg = f"Exception calling pastled to get registration ticket: {pe}"
        logger.error(err_msg)
        return None, None, err_msg
    except Exception as e:
        msg = f"Exception calling pastled to get registration ticket: {e}"
        logger.error(msg)
        return None, None, msg
    if not reg_ticket:
        msg = f"Registration ticket {reg_txid} not found"
        logger.error(msg)
        return None, None, msg

    if service == wn.WalletNodeService.CASCADE or service == wn.WalletNodeService.SENSE:
        called_at_name = 'called_at'
    elif service == wn.WalletNodeService.NFT or service == wn.WalletNodeService.COLLECTION:
        called_at_name = 'creator_height'
    else:
        logger.error(f"{service}: Unknown service")
        return None, f"Unknown service {service}"

    if ('ticket' in reg_ticket and reg_ticket['ticket'] and
            called_at_name in reg_ticket['ticket'] and reg_ticket['ticket'][called_at_name]):
        called_at_height = reg_ticket['ticket'][called_at_name]
    else:
        logger.error(f"{service}: Registration ticket {reg_txid} doesn't have {called_at_name} height. Invalid ticket?")
        return None, None, f"Registration ticket {reg_txid} doesn't have {called_at_name} height"

    if 'height' in reg_ticket and reg_ticket['height']:
        return called_at_height, reg_ticket['height'], None

    return None, None, "Error parsing registration ticket"


@shared_task(name="scheduled_tools:watchdog")
def watchdog():
    if settings.ACCOUNT_MANAGER_ENABLED:  # throw and exception if account manager is enabled
        raise Exception("Account manager and watchdog can't be enabled at the same time")

    logger.info(f"watchdog task started")
    _ticket_verificator(
        crud.cascade.get_all_in_done,
        crud.cascade.update,
        wn.WalletNodeService.CASCADE
    )
    _ticket_verificator(
        crud.sense.get_all_in_done,
        crud.sense.update,
        wn.WalletNodeService.SENSE
    )

    _abandoned_states_cleaner(
        crud.cascade.get_all_not_finished,
        crud.cascade.update,
        wn.WalletNodeService.CASCADE
    )
    _abandoned_states_cleaner(
        crud.sense.get_all_not_finished,
        crud.sense.update,
        wn.WalletNodeService.SENSE
    )
    _abandoned_states_cleaner(
        crud.nft.get_all_not_finished,
        crud.nft.update,
        wn.WalletNodeService.NFT
    )
    _abandoned_states_cleaner(
        crud.collection.get_all_not_finished,
        crud.collection.update,
        wn.WalletNodeService.COLLECTION
    )

    logger.info(f"watchdog task ended")


def _ticket_verificator(all_done_func,
                        update_task_in_db_func,
                        service: wn.WalletNodeService):
    logger.info(f"ticket_activator task started")
    with db_context() as session:
        tasks_from_db = all_done_func(session)  # get latest 100(!) tasks in DONE state
    for task_from_db in tasks_from_db:
        try:
            network_height = psl.call("getblockcount", [])   # can throw exception here

            msg = f"{service}: Activation ticket transaction {task_from_db.act_ticket_txid} " \
                  f"for registration ticket {task_from_db.reg_ticket_txid}"

            at_status = asyncio.run(psl.check_ticket_transaction(task_from_db.act_ticket_txid, msg,
                                                                 network_height, task_from_db.height))
            if at_status == psl.TicketTransactionStatus.NOT_FOUND:
                # clear activation ticket txid if it is not found in the network
                upd = {"act_ticket_txid": "", "process_status": DbStatus.REGISTERED.value,
                       "updated_at": datetime.utcnow()}
                with db_context() as session:
                    update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)

        except Exception as e:
            logger.error(f"Error while verifying registration ticket {task_from_db.reg_ticket_txid}: {e}")


def _abandoned_states_cleaner(get_all_non_finished_func,
                              update_task_in_db_func,
                              service: wn.WalletNodeService):
    logger.info(f"abandoned_states_cleaner task started")
    with db_context() as session:
        tasks_from_db = get_all_non_finished_func(session)  # get oldest 100 updated more than 12 hours ago tasks
    for task_from_db in tasks_from_db:
        try:
            done = False
            obj_in = {"process_status": DbStatus.ERROR.value, "retry_num": 0,
                      "updated_at": datetime.utcnow(), "process_status_message": "Task was abandoned, set to ERROR"}
            if task_from_db.wn_task_id:
                wn_task_status = wn.call(False,
                                         service,
                                         f'{task_from_db.wn_task_id}/history',
                                         {}, [], {},
                                         "", "")
                if wn_task_status:
                    for step in wn_task_status:
                        if step['status'] == 'Task Completed':
                            obj_in = {"process_status": DbStatus.DONE.value, "updated_at": datetime.utcnow(),
                                      "process_status_message": "Task was abandoned, but seems to be completed"}
                            done = True
                            continue
                        if step['status'] == 'Request Accepted':
                            obj_in = {"process_status": DbStatus.REGISTERED.value, "updated_at": datetime.utcnow(),
                                      "process_status_message": "Task was abandoned, but seems to be accepted"}
                            continue
                        if step['status'] == 'Request Registered':
                            obj_in = {"process_status": DbStatus.REGISTERED.value, "updated_at": datetime.utcnow(),
                                      "process_status_message": "Task was abandoned, but seems to be registered"}
                            continue
            with db_context() as session:
                update_task_in_db_func(session, db_obj=task_from_db, obj_in=obj_in)
                if done:
                    crud.user.increase_balance(session, user_id=task_from_db.owner_id, amount=task_from_db.wn_fee)

        except Exception as e:
            logger.error(f"Error while checking abandoned task {task_from_db.reg_ticket_txid}: {e}")
