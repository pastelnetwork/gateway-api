import abc
import asyncio
from datetime import datetime

from celery.result import AsyncResult
import celery
from celery.utils.log import get_task_logger

from app import crud
from app.db.session import db_context
from app.utils import walletnode as wn, pasteld as psl
from app.core.config import settings
from app.core.status import DbStatus
from app.utils.ipfs_tools import search_file_locally_or_in_ipfs, store_file_to_ipfs

logger = get_task_logger(__name__)


class PastelAPITask(celery.Task):
    def run(self, *args, **kwargs):
        pass

    @staticmethod
    def get_result_id_from_args(args) -> str:
        if args:
            if len(args) > 0:      # preburn_fee, process, re_register_file, register_file
                return args[0]
        raise Exception("Invalid args")

    @staticmethod
    def update_task_in_db_status_func(result_id, status, get_task_from_db_by_task_id_func, update_task_in_db_func):
        with db_context() as session:
            task_from_db = get_task_from_db_by_task_id_func(session, result_id=result_id)
            if task_from_db:
                upd = {"process_status": status, "updated_at": datetime.utcnow()}
                update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)

    @staticmethod
    def on_success_base(args, get_task_from_db_by_task_id_func, update_task_in_db_func):
        pass

    @staticmethod
    def on_failure_base(args, get_task_from_db_by_task_id_func, update_task_in_db_func):
        logger.error(f'Error in task: {args}')
        result_id = PastelAPITask.get_result_id_from_args(args)
        PastelAPITask.update_task_in_db_status_func(result_id,
                                                    DbStatus.ERROR.value,
                                                    get_task_from_db_by_task_id_func,
                                                    update_task_in_db_func)

    # def on_retry(self, exc, task_id, args, kwargs, einfo):
    #     print(f'{task_id} retrying: {exc}')

    def register_file_task(self,
                           result_id, local_file, user_id,
                           create_klass_lambda,
                           get_task_from_db_by_task_id_func,
                           create_with_owner_func,
                           update_task_in_db_func,
                           retry_func,
                           service: wn.WalletNodeService,
                           upload_cmd, id_field_name, fee_field_name, fee_multiplier=1):
        logger.info(f'{service}: Starting file registration... [Result ID: {result_id}]')

        with db_context() as session:
            task_in_db = get_task_from_db_by_task_id_func(session, result_id=result_id)

        if task_in_db and task_in_db.process_status != DbStatus.NEW.value:
            logger.info(f'{service}: Task is already in the DB. Status is {task_in_db.process_status}... '
                        f'[Result ID: {result_id}]')
            return result_id

        wn_file_id = ''
        returned_fee = 0
        if not task_in_db:
            # can throw exception here - this is celery task, it will retry it on specific exceptions
            height = psl.call("getblockcount", [])
            logger.info(f'{service}: New file - adding record to DB... [Result ID: {result_id}]')
            logger.info(f'{service}: Ticket will be created at height {height} [Result ID: {result_id}]')
            with db_context() as session:
                new_task = create_klass_lambda(height)
                task_in_db = create_with_owner_func(session, obj_in=new_task, owner_id=user_id)
            logger.info(f'{service}: New record created... [Result ID: {result_id}]')

        logger.info(f'{service}: New file - calling WN Upload... [Result ID: {result_id}]')
        data = local_file.read()

        try:
            wn_file_id, returned_fee = wn.call(True,
                                              service,
                                              upload_cmd,
                                              {},
                                              [('file', (local_file.name, data, local_file.type))],
                                              {},
                                              id_field_name, fee_field_name)
        except Exception as e:
            logger.warn(f'{service}: Upload call failed for file {local_file.name} - {e}. Retrying...')
            set_status_message(task_in_db, f'Upload call failed for file {local_file.name} - {e}')
            retry_func()

        if not wn_file_id:
            logger.warn(f'{service}: Upload call failed for file {local_file.name} - "wn_file_id" is empty. '
                        f'retrying...')
            set_status_message(task_in_db, f'Upload call failed for file {local_file.name} - "wn_file_id" is empty. Retrying')
            retry_func()
        if returned_fee <= 0:
            logger.warn(f'{service}: Wrong WN Fee {returned_fee} for file {local_file.name}, retrying...')
            set_status_message(task_in_db, f'Wrong WN Fee {returned_fee} for file {local_file.name}. Retrying')
            retry_func()

        total_fee = returned_fee*fee_multiplier

        logger.info(f'{service}: File was registered with WalletNode with\n:'
                    f'\twn_file_id = {wn_file_id} and fee = {total_fee}. [Result ID: {result_id}]')
        upd = {
            "process_status": DbStatus.UPLOADED.value,
            "process_status_message": "File was uploaded to WN.",
            "wn_file_id": wn_file_id,
            "wn_fee": total_fee,
        }
        with db_context() as session:
            update_task_in_db_func(session, db_obj=task_in_db, obj_in=upd)

        logger.info(f'{service}: File uploaded to WN. Exiting... [Result ID: {result_id}]')
        return result_id

    def preburn_fee_task(self,
                         result_id,
                         get_task_from_db_by_task_id_func,
                         update_task_in_db_func,
                         retry_func,
                         service: wn.WalletNodeService) -> str:
        if service == wn.WalletNodeService.NFT:
            return result_id

        logger.info(f'{service}: Searching for pre-burn tx for registration... [Result ID: {result_id}]')

        with db_context() as session:
            task_from_db = get_task_from_db_by_task_id_func(session, result_id=result_id)

        if not task_from_db:
            logger.error(f'{service}: No task found for result_id {result_id}')
            raise PastelAPIException(f'{service}: No task found for result_id {result_id}')

        if task_from_db.process_status != DbStatus.UPLOADED.value:
            logger.warn(f'{service}: preburn_fee_task: Wrong task state - "{task_from_db.process_status}", '
                        f'Should be {DbStatus.UPLOADED.value}'
                        f' ... [Result ID: {result_id}]')
            return result_id

        if not psl.check_balance(task_from_db.wn_fee):   # can throw exception here
            set_status_message(task_from_db, f'Not enough balance to pay for pre-burn fee. Retrying')
            retry_func()

        preburn_fee = task_from_db.wn_fee/5
        # can throw exception here - this is celery task, it will retry it on specific exceptions
        height = psl.call("getblockcount", [])

        if task_from_db.burn_txid:
            logger.warn(f'{service}: Pre-burn tx [{task_from_db.burn_txid}] already associated with result...'
                        f' [Result ID: {result_id}]')
            return result_id

        with db_context() as session:
            burn_tx = crud.preburn_tx.get_bound_to_result(session, result_id=result_id)
            if burn_tx:
                logger.info(f'{service}: Found burn tx [{burn_tx.txid}] already '
                            f'bound to the task [Result ID: {result_id}]')
            else:
                logger.info(f'{service}: Searching burn tx in preburn table... [Result ID: {result_id}]')
                have_pending = 0
                while True:
                    burn_tx = crud.preburn_tx.get_non_used_by_fee(session, fee=preburn_fee)
                    if not burn_tx:
                        break
                    if burn_tx.height + 5 > height:
                        logger.info(f'{service}: Found burn tx [{burn_tx.txid}] in preburn table, but it is '
                                    f'not confirmed yet. Skipping... [Result ID: {result_id}]')
                        have_pending += 1
                        continue
                    if check_preburn_tx(session, burn_tx.txid):
                        logger.info(f'{service}: Found burn tx in [{burn_tx.txid}] preburn table... '
                                    f'[Result ID: {result_id}]')
                        break

                if not burn_tx:
                    if have_pending > 0:
                        logger.info(f'{service}: Found {have_pending} pre-burn txs in preburn table, but they are '
                                    f'not confirmed yet. Retrying... [Result ID: {result_id}]')
                        upd = {
                            "process_status_message": f'Found {have_pending} pre-burn txs in preburn table, '
                                                      f'but they are not confirmed yet. Retrying',\
                            "updated_at": datetime.utcnow(), }
                        update_task_in_db_func(session, db_obj=task_in_db, obj_in=upd)
                        retry_func()

                    logger.info(f'{service}: No pre-burn tx, calling sendtoaddress... [Result ID: {result_id}]')
                    # can throw exception here - this is celery task, it will retry it on specific exceptions
                    burn_txid = psl.call("sendtoaddress", [settings.BURN_ADDRESS, preburn_fee])
                    burn_tx = crud.preburn_tx.create_new_bound(session,
                                                               fee=preburn_fee,
                                                               height=height,
                                                               txid=burn_txid,
                                                               result_id=result_id)
                else:
                    logger.info(f'{service}: Found pre-burn tx [{burn_tx.txid}], '
                                f'bounding it to the task [Result ID: {result_id}]')
                    burn_tx = crud.preburn_tx.bind_pending_to_result(session, burn_tx,
                                                                     result_id=result_id)
            if burn_tx.height + 5 > height:
                logger.info(f'{service}: Pre-burn tx [{burn_tx.txid}] not confirmed yet, '
                            f'retrying... [Result ID: {result_id}]')
                upd = {"process_status_message": f'Pre-burn tx [{burn_tx.txid}] not confirmed yet. Retrying',
                       "updated_at": datetime.utcnow(),}
                update_task_in_db_func(session, db_obj=task_in_db, obj_in=upd)
                retry_func()

            logger.info(f'{service}: Have confirmed burn tx [{burn_tx.txid}], for the task [Result ID: {result_id}]')
            upd = {
                "burn_txid": burn_tx.txid,
                "process_status": DbStatus.PREBURN_FEE.value,
                "process_status_message": "Found valid and confirmed pre-burn transaction",
                "updated_at": datetime.utcnow(),
            }
            update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)

        logger.info(f'{service}: Found pre-burn tx for registration. Exiting... [Result ID: {result_id}]')
        return result_id

    @abc.abstractmethod
    def get_request_form(self, task_from_db) -> str:
        return ""

    @abc.abstractmethod
    def check_specific_conditions(self, task_from_db) -> bool:
        return False

    def process_task(self,
                     result_id,
                     get_task_from_db_by_task_id_func,
                     update_task_in_db_func,
                     retry_func,
                     service: wn.WalletNodeService) -> str:
        logger.info(f'{service}: Register file in the Pastel Network... [Result ID: {result_id}]')

        with db_context() as session:
            task_from_db = get_task_from_db_by_task_id_func(session, result_id=result_id)

        if not task_from_db:
            logger.error(f'{service}: No task found for result_id {result_id}')
            raise PastelAPIException(f'{service}: No task found for result_id {result_id}')

        if task_from_db.wn_fee == 0:
            logger.error(f'{service}: Wrong WN Fee for result_id {result_id}')
            set_status_message(task_from_db, f'Wrong WN Fee. Throwing exception')
            raise PastelAPIException(f'{service}: Wrong WN Fee for result_id {result_id}')

        if not task_from_db.wn_file_id:
            logger.error(f'{service}: Wrong WN file ID for result_id {result_id}')
            set_status_message(task_from_db, f'Wrong WN file ID. Throwing exception')
            raise PastelAPIException(f'{service}: Wrong WN file ID for result_id {result_id}')

        if not psl.check_balance(task_from_db.wn_fee):   # can throw exception here
            set_status_message(task_from_db, f'Not enough balance to pay WN Fee. Retrying')
            retry_func()

        ok, err_msg = self.check_specific_conditions(task_from_db)
        if not ok:
            logger.info(err_msg)
            set_status_message(task_from_db, err_msg)
            return result_id

        original_file_ipfs_link = task_from_db.original_file_ipfs_link

        wn_task_id = None
        if not task_from_db.wn_task_id:
            logger.info(f'{service}: Calling "WN Start"... [Result ID: {result_id}]')

            form = self.get_request_form(task_from_db)   # can throw exception here

            if service == wn.WalletNodeService.NFT:
                cmd = 'register'
            else:
                cmd = f'start/{task_from_db.wn_file_id}'

            try:
                wn_task_id = wn.call(True,
                                     service,
                                     cmd,
                                     form,
                                     [],
                                     {
                                         'Authorization': settings.PASTEL_ID_PASSPHRASE,
                                         'Content-Type': 'application/json'
                                     },
                                     "task_id", "")
            except Exception as e:
                logger.error(f'{service}: Error calling "WN Start" for result_id {result_id}: {e}')
                set_status_message(task_from_db, f'Error calling "WN Start" - {e}. Retrying')
                retry_func()

            if not wn_task_id:
                logger.error(f'{service}: No wn_task_id returned from WN for result_id {result_id}')
                set_status_message(task_from_db, f'No wn_task_id returned from WN. Throwing exception')
                raise Exception(f'{service}: No wn_task_id returned from WN for result_id {result_id}')

            logger.info(f'{service}: WN register process started: wn_task_id {wn_task_id} result_id {result_id}')

            upd = {
                "wn_task_id": wn_task_id,
                "pastel_id": settings.PASTEL_ID,
                "process_status": DbStatus.STARTED.value,
                "process_status_message": "WN register process started",
                "updated_at": datetime.utcnow(),
            }
            with db_context() as session:
                update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
        else:
            logger.info(f'{service}: "WN Start" already called... [Result ID: {result_id}; '
                        f'WN Task ID: {task_from_db.wn_task_id}]')

        if not original_file_ipfs_link:
            with db_context() as session:
                task_from_db = get_task_from_db_by_task_id_func(session, result_id=result_id)

                logger.info(f'{service}: Storing file into IPFS... [Result ID: {result_id}]')

                original_file_ipfs_link = asyncio.run(store_file_to_ipfs(task_from_db.original_file_local_path))

                if original_file_ipfs_link:
                    logger.info(f'{service}: Updating DB with IPFS link... '
                                f'[Result ID: {result_id}; IPFS Link: https://ipfs.io/ipfs/{original_file_ipfs_link}]')
                    upd = {"original_file_ipfs_link": original_file_ipfs_link, "updated_at": datetime.utcnow()}
                    update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)

        logger.info(f'{service}: process_task exiting for result_id {result_id}')
        return result_id

    def re_register_file_task(self,
                              result_id,
                              get_task_from_db_by_task_id_func,
                              update_task_in_db_func,
                              service: wn.WalletNodeService,
                              upload_cmd, id_field_name, fee_field_name, fee_multiplier=1) -> str:
        logger.info(f'{service}: Starting file re-registration... [Result ID: {result_id}]')

        with db_context() as session:
            task_from_db = get_task_from_db_by_task_id_func(session, result_id=result_id)

        if not task_from_db:
            logger.error(f'{service}: No task found for result_id {result_id}')
            raise PastelAPIException(f'{service}: No task found for result_id {result_id}')

        if task_from_db.process_status != DbStatus.RESTARTED.value:
            logger.info(f'{service}: re_register_file_task: Wrong task state - "{task_from_db.process_status}", '
                        f'Should be {DbStatus.RESTARTED.value}'
                        f' ... [Result ID: {result_id}]')
            return result_id

        logger.info(f'{service}: Searching for file locally at {task_from_db.original_file_local_path}; or'
                     f' in IPFS at {task_from_db.original_file_ipfs_link}... [Result ID: {result_id}]')

        data = asyncio.run(search_file_locally_or_in_ipfs(task_from_db.original_file_local_path,
                                                          task_from_db.original_file_ipfs_link, True))
        if not data:
            logger.error(f'{service}: File not found locally or in IPFS... [Result ID: {result_id}]')
            # marking task as DEAD
            with db_context() as session:
                upd = {
                    "process_status": DbStatus.DEAD.value,
                    "process_status_message": "File not found locally or in IPFS",
                    "updated_at": datetime.utcnow()
                }
                update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
            return result_id

        logger.info(f'{service}: Re-uploading file - calling WN... [Result ID: {result_id}]')
        try:
            wn_file_id, returned_fee = wn.call(True,
                                              service,
                                              upload_cmd,
                                              {},
                                              [('file',
                                                (task_from_db.original_file_name,
                                                 data,
                                                 task_from_db.original_file_content_type))],
                                              {},
                                              id_field_name, fee_field_name)
        except Exception as e:
            logger.error(f'{service}: Error calling "WN Start" for result_id {result_id}: {e}')
            set_status_message(task_from_db, f'Error calling "WN Start" - {e}. Throwing exception')
            raise e

        if not wn_file_id:
            logger.error(f'{service}: Upload call failed for file '
                        f'{task_from_db.original_file_name} - "wn_file_id" is empty. Retrying...')
            set_status_message(task_from_db, f'Upload call failed for file {task_from_db.original_file_name}. Throwing exception')
            raise PastelAPIException(f'{service}: Upload call failed for file {task_from_db.original_file_name}')
        if returned_fee <= 0:
            logger.error(f'{service}: Wrong WN Fee {returned_fee} for file {task_from_db.original_file_name},'
                        f' retrying...')
            set_status_message(task_from_db, f'Wrong WN Fee {returned_fee} for file {task_from_db.original_file_name}. Throwing exception')
            raise PastelAPIException(f'{service}: Wrong WN Fee {returned_fee} for file '
                                     f'{task_from_db.original_file_name}')

        total_fee = returned_fee*fee_multiplier

        with db_context() as session:
            upd = {
                "wn_file_id": wn_file_id,
                "wn_fee": total_fee,
                "process_status": DbStatus.UPLOADED.value,
                "process_status_message": "File re-uploaded successfully",
                "updated_at": datetime.utcnow(),
            }
            update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)

        logger.info(f'{service}: File re-registration started. Exiting... [Result ID: {result_id}]')
        return result_id


def get_celery_task_info(celery_task_id):
    """
    return task info for the given celery_task_id
    """
    celery_task_result = AsyncResult(celery_task_id)
    result = {
        "celery_task_id": celery_task_id,
        "celery_task_status": celery_task_result.status,
        "celery_task_state": celery_task_result.state,
        "celery_task_result": str(celery_task_result.result)
    }
    return result


# Exception for Cascade and Sense tasks
class PastelAPIException(Exception):
    def __init__(self, message):
        self.message = message or "PastelAPIException"
        super().__init__(self.message)


def check_preburn_tx(session, txid: str):
    try:
        tx = psl.call("tickets", ["find", "nft", txid])   # can throw exception here
        if not tx or (not isinstance(tx, dict) and not isinstance(tx, list)):
            tx = psl.call("tickets", ["find", "action", txid])   # can throw exception here
            if not tx or (not isinstance(tx, dict) and not isinstance(tx, list)):
                tx = psl.call("getrawtransaction", [txid], True)   # WON'T throw exception here
                if not tx \
                        or ("status_code" in tx and tx.status_code != 200) \
                        or (isinstance(tx, dict) and (tx.get('error') or tx.get('result') is None)):
                    logger.info(f"Transaction {txid} is in the table but is not in the blockchain, marking as BAD")
                    crud.preburn_tx.mark_bad(session, txid)
                    return False    # tx is not used by any reg ticket, BUT it is not in the blockchain
                else:
                    return True    # tx is not used by any reg ticket, and it is in the blockchain
        logger.info(f"Transaction {txid} is already used, marking as USED")
        crud.preburn_tx.mark_used(session, txid)
    except Exception as e:
        logger.error(f"Error checking transaction {txid} in the blockchain: {e}")
    return False    # tx is used by some reg ticket

def set_status_message(task_in_db, message: str):
    upd = {
        "process_status_message": message,
        "updated_at": datetime.utcnow(),
    }
    with db_context() as session:
        update_task_in_db_func(session, db_obj=task_in_db, obj_in=upd)