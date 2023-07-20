import asyncio
from datetime import datetime

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

logger = get_task_logger(__name__)


@shared_task(name="scheduled_tools:fee_pre_burner")
def fee_pre_burner():
    logger.info(f"fee_pre_burner task started")
    logger.info(f"first: release non used")
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

    height = psl.call("getblockcount", [], True)   # won't throw exception
    if not height or not isinstance(height, int):
        logger.error(f"Error while getting height from cNode")
        return

    with db_context() as session:
        all_new = crud.preburn_tx.get_all_new(session)
        for new in all_new:
            if new.height + 5 < height:
                check_preburn_tx(session, new.txid)

    with db_context() as session:
        fees = []
        logger.info(f"second: calculate fees")
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
            for dups in reversed(range(size, settings.MAX_SIZE_FOR_PREBURN+1)):
                if c_num < settings.MAX_SIZE_FOR_PREBURN-size+1:
                    fees.append(c_fee)
                if s_num < settings.MAX_SIZE_FOR_PREBURN-size+1:
                    fees.append(s_fee)

    height = psl.call("getblockcount", [], True)   # won't throw exception
    if not height or not isinstance(height, int):
        logger.error(f"Error while getting height from cNode")
        return

    logger.info(f"third: burn fees")
    with db_context() as session:
        for burn_amount in fees:
            try:
                if not psl.check_balance(burn_amount):   # can throw exception here
                    return
                burn_txid = psl.call("sendtoaddress", [settings.BURN_ADDRESS, burn_amount])   # can throw exception
            except Exception as e:
                logger.error(f"Error while burning fee {e}")
                continue
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

        nft_tickets = psl.call("tickets", ['list', 'nft', 'active', last_processed_block+1], nothrow=True)   # won't throw exception
        process_nft_tickets(nft_tickets, last_processed_block)

        action_ticket = psl.call("tickets", ['list', 'action', 'active', last_processed_block+1], nothrow=True)   # won't throw exception
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
    with db_context() as session:
        tasks_from_db = all_in_registered_state_func(session)
    logger.info(f"{service}: Found {len(tasks_from_db)} registered, but not activated tasks")
    for task_from_db in tasks_from_db:
        if task_from_db.pastel_id is None:
            logger.error(f"{service}: Don't know pastel_id, marking task as DEAD. ResultID = {task_from_db.result_id}")
            upd = {"process_status": DbStatus.DEAD.value, "updated_at": datetime.utcnow()}
            with db_context() as session:
                update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
            continue
        if settings.PASTEL_ID != task_from_db.pastel_id:
            logger.info(f"{service}: Skipping ticket {task_from_db.reg_ticket_txid}, "
                        f"caller pastel_id {task_from_db.pastel_id} is not ours")
            continue
        try:
            logger.info(f"{service}: Parsing registration ticket {task_from_db.reg_ticket_txid} to find height")
            height = find_height_in_registration_ticket(task_from_db.reg_ticket_txid, task_from_db.height, service)
            if not height:
                logger.warn(
                    f"{service}: Didn't found height in registration ticket. "
                    f"Skipping for now. ResultID = {task_from_db.result_id}")
                continue

            logger.info(f"{service}: Check if activation ticket already exists for "
                        f"registration ticket: {task_from_db.reg_ticket_txid}")
            act_txid = find_action_ticket(task_from_db.reg_ticket_txid, act_ticket_type)
            if act_txid:
                logger.info(f"{service}: Registration ticket {task_from_db.reg_ticket_txid} "
                            f"already activated: {act_txid}")
            else:
                try:
                    network_height = psl.call("getblockcount", [])   # can throw exception here
                except Exception as e:
                    logger.error(f"{service}: Can't get network height, skipping. Error: {e}")
                    continue
                if network_height - height < 5:
                    logger.info(f"{service}: There are {network_height - height} blocks after "
                                f"Registration ticket {task_from_db.reg_ticket_txid} was registered. "
                                f"Waiting for 5 blocks before finalizing - WN can still finish it")
                    continue

                logger.info(f"{service}: Activating registration ticket {task_from_db.reg_ticket_txid}")
                act_txid = create_activation_ticket(task_from_db, height, act_ticket_type)

            if act_txid:
                finalize_registration(task_from_db, act_txid, update_task_in_db_func, service)
                # upd = {
                #     "act_ticket_txid": act_txid,
                #     "process_status": DbStatus.DONE.value,
                #     "updated_at": datetime.utcnow(),
                #     "height": height,
                # }
                # with db_context() as session:
                #     update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
        except Exception as e:
            logger.error(f"Error while creating activation for registration ticket {task_from_db.reg_ticket_txid}: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                error_msg = e.response.text
                msg = f"The Action Registration ticket with this txid [{task_from_db.reg_ticket_txid}] is invalid"
                if msg in error_msg:
                    upd = {"process_status": DbStatus.DEAD.value, "updated_at": datetime.utcnow()}
                    with db_context() as session:
                        update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)


def find_action_ticket(txid: str, ticket_type: str) -> str|None:
    try:
        act_ticket = psl.call("tickets", ["find", ticket_type, txid])   # can throw exception here
    except Exception as e:
        logger.error(f"Exception calling pastled to find {ticket_type} ticket: {e}")
        return None
    if act_ticket and isinstance(act_ticket, dict) and 'txid' in act_ticket and act_ticket['txid']:
        logger.info(f"Found act ticket txid from Pastel network: {act_ticket['txid']}")
        return act_ticket['txid']
    return None


def create_activation_ticket(task_from_db, height, ticket_type):
    try:
        if not psl.check_balance(task_from_db.wn_fee + 1000):   # can throw exception here
            return
        activation_ticket = psl.call('tickets', ['register', ticket_type,
                                                 task_from_db.reg_ticket_txid,
                                                 height,
                                                 task_from_db.wn_fee,
                                                 settings.PASTEL_ID,
                                                 settings.PASTEL_ID_PASSPHRASE]
                                     )   # can throw exception here
    except Exception as e:
        logger.error(f"Exception calling pastled to create {ticket_type} ticket: {e}")
        return None
    if activation_ticket and 'txid' in activation_ticket:
        logger.info(f"Created {ticket_type} ticket {activation_ticket['txid']}")
        return activation_ticket['txid']
    else:
        logger.error(f"Error while creating {ticket_type} ticket {activation_ticket}")
        return None


def find_height_in_registration_ticket(reg_txid, db_height, service: wn.WalletNodeService):
    try:
        reg_ticket = psl.call("tickets", ['get', reg_txid])   # can throw exception here
    except Exception as e:
        logger.error(f"Exception calling pastled to get registration ticket: {e}")
        return None
    if not reg_ticket:
        logger.error(f"{service}: Registration ticket {reg_txid} not found")
        return None

    if service == wn.WalletNodeService.CASCADE or service == wn.WalletNodeService.SENSE:
        expected_action_type = 'cascade' if service == wn.WalletNodeService.CASCADE else 'sense'
        reg_ticket = asyncio.run(psl.parse_registration_action_ticket(reg_ticket, 'action-reg', [expected_action_type]))
        ticket_name = 'action_ticket'
    elif service == wn.WalletNodeService.NFT:
        reg_ticket = asyncio.run(psl.parse_registration_nft_ticket(reg_ticket))
        ticket_name = 'nft_ticket'
    elif service == wn.WalletNodeService.COLLECTION:
        ticket_name = 'collection_ticket'
    else:
        logger.error(f"{service}: Unknown service")
        return None

    if not reg_ticket:
        logger.error(f"{service}: Error while parsing registration ticket {reg_txid}")

    if 'ticket' in reg_ticket and ticket_name in reg_ticket['ticket'] and \
            'blocknum' in reg_ticket['ticket'][ticket_name]:
        return reg_ticket['ticket'][ticket_name]['blocknum']

    return db_height


@shared_task(name="scheduled_tools:watchdog")
def watchdog():
    logger.info(f"watchdog task started")
    logger.info(f"watchdog task ended")
