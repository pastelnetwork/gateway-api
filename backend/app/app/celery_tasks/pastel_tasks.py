import json
from datetime import datetime
from pathlib import Path

import ipfshttpclient as ipfshttpclient
from celery.result import AsyncResult
import celery

from app import crud
from app.db.session import db_context
from app.utils import walletnode as wn, pasteld as psl
from app.core.config import settings


class PastelAPITask(celery.Task):
    def run(self, *args, **kwargs):
        pass

    @staticmethod
    def get_result_id_from_args(args) -> str:
        if args:
            if len(args) == 1:      # preburn_fee, process, re_register_file
                return args[0]
            elif len(args) == 4:    # register_file
                return args[2]
        raise Exception("Invalid args")

    @staticmethod
    def update_task_in_db_status_func(result_id, status, get_task_from_db_by_task_id_func, update_task_in_db_func):
        with db_context() as session:
            task_from_db = get_task_from_db_by_task_id_func(session, result_id=result_id)
            if task_from_db:
                upd = {"ticket_status": status, "updated_at": datetime.utcnow()}
                update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)

    @staticmethod
    def on_success_base(args, get_task_from_db_by_task_id_func, update_task_in_db_func):
        pass

    @staticmethod
    def on_failure_base(args, get_task_from_db_by_task_id_func, update_task_in_db_func):
        result_id = PastelAPITask.get_result_id_from_args(args)
        PastelAPITask.update_task_in_db_status_func(result_id,
                                                    "ERROR",
                                                    get_task_from_db_by_task_id_func,
                                                    update_task_in_db_func)

    # def on_retry(self, exc, task_id, args, kwargs, einfo):
    #     print(f'{task_id} retrying: {exc}')

    def register_file_task(self,
                           local_file, request_id, result_id, user_id,
                           create_klass,
                           get_task_from_db_by_task_id_func,
                           create_with_owner_func,
                           retry_func,
                           service: wn.WalletNodeService,
                           service_name: str):
        self.message = f'{service_name}: Starting file registration... [Result ID: {result_id}]'

        with db_context() as session:
            task = get_task_from_db_by_task_id_func(session, result_id=result_id)

        if task:
            self.message = f'{service_name}: Result is already in the DB... [Result ID: {result_id}]'
            return result_id

        self.message = f'{service_name}: New file - calling WN... [Result ID: {result_id}]'
        data = local_file.read()
        id_field_name = "image_id" if service == wn.WalletNodeService.SENSE else "file_id"
        wn_file_id, fee = wn.call(True,
                                  service,
                                  'upload',
                                  {},
                                  [('file', (local_file.name, data, local_file.type))],
                                  {},
                                  id_field_name, "estimated_fee")

        if not wn_file_id:
            self.message = f'{service_name}: Upload call failed for file {local_file.name}, retrying...'
            retry_func()
        if fee <= 0:
            self.message = f'{service_name}: Wrong WN Fee {fee} for file {local_file.name}, retrying...'
            retry_func()

        height = psl.call("getblockcount", [])
        self.message = f'{service_name}: New file - adding record to DB... [Result ID: {result_id}]'
        with db_context() as session:
            new_task = create_klass(
                original_file_name=local_file.name,
                original_file_content_type=local_file.type,
                original_file_local_path=local_file.path,
                work_id=request_id,
                ticket_id=result_id,
                ticket_status='UPLOADED',
                wn_file_id=wn_file_id,
                wn_fee=fee,
                height=height,
            )
            create_with_owner_func(session, obj_in=new_task, owner_id=user_id)

        return result_id

    def preburn_fee_task(self,
                         result_id,
                         get_task_from_db_by_task_id_func,
                         update_task_in_db_func,
                         retry_func,
                         service_name: str) -> str:
        self.message = f'{service_name}: Searching for pre-burn tx for registration... [Result ID: {result_id}]'

        with db_context() as session:
            task_from_db = get_task_from_db_by_task_id_func(session, result_id=result_id)

        if not task_from_db:
            raise PastelAPIException(f'{service_name}: No task found for result_id {result_id}')

        if task_from_db.ticket_status == 'PREBURN_FEE' or \
                task_from_db.ticket_status == 'STARTED':
            self.message = f'{service_name}: Registration (preburn_fee) already started... [Result ID: {result_id}]'
            return result_id

        burn_amount = task_from_db.wn_fee / 5
        height = psl.call("getblockcount", [])

        if task_from_db.burn_txid:
            self.message = f'{service_name}: Pre-burn tx [{task_from_db.burn_txid}] already associated with result...' \
                           f' [Result ID: {result_id}]'
            return result_id

        with db_context() as session:
            burn_tx = crud.preburn_tx.get_bound_to_result(session, result_id=result_id)
            if not burn_tx:
                burn_tx = crud.preburn_tx.get_non_used_by_fee(session, fee=burn_amount)
                if not burn_tx:
                    self.message = f'{service_name}: No pre-burn tx, calling sendtoaddress... [Result ID: {result_id}]'
                    burn_txid = psl.call("sendtoaddress", [settings.BURN_ADDRESS, burn_amount])
                    burn_tx = crud.preburn_tx.create_new_bound(session,
                                                               fee=burn_amount,
                                                               height=height,
                                                               txid=burn_txid,
                                                               result_id=result_id)
                else:
                    burn_tx = crud.preburn_tx.bind_pending_to_result(session, burn_tx,
                                                                     result_id=result_id)
            if burn_tx.height > height - 5:
                self.message = f'{service_name}: Pre-burn tx [{task_from_db.burn_txid}] not confirmed yet, retrying...' \
                               f' [Result ID: {result_id}]'
                retry_func()

            upd = {
                "burn_txid": burn_tx.txid,
                "ticket_status": 'PREBURN_FEE',
                "updated_at": datetime.utcnow(),
            }
            update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)

        return result_id

    def process_task(self,
                     result_id,
                     get_task_from_db_by_task_id_func,
                     update_task_in_db_func,
                     service: wn.WalletNodeService,
                     service_name: str) -> str:
        self.message = f'{service_name}: Register file in the Pastel Network... [Result ID: {result_id}]'

        with db_context() as session:
            task_from_db = get_task_from_db_by_task_id_func(session, result_id=result_id)

        if not task_from_db:
            raise PastelAPIException(f'{service_name}: No task found for result_id {result_id}')

        if task_from_db.wn_fee == 0:
            raise PastelAPIException(f'{service_name}: Wrong WN Fee for result_id {result_id}')

        if not task_from_db.wn_file_id:
            raise PastelAPIException(f'{service_name}: Wrong WN file ID for result_id {result_id}')

        if task_from_db.ticket_status == 'STARTED':
            self.message = f'{service_name}: File registration (process) already started... [Result ID: {result_id}]'
            return result_id

        if not task_from_db.burn_txid:
            raise PastelAPIException(f'{service_name}: No burn txid for result_id {result_id}')

        task_ipfs_link = task_from_db.ipfs_link

        if not task_from_db.wn_task_id:
            self.message = f'{service_name}: Calling "WN Start"... [Result ID: {result_id}]'
            burn_txid = task_from_db.burn_txid
            wn_file_id = task_from_db.wn_file_id
            wn_task_id = wn.call(True,
                                 service,
                                 f'start/{wn_file_id}',
                                 json.dumps({"burn_txid": burn_txid, "app_pastelid": settings.PASTEL_ID, }),
                                 [],
                                 {
                                     'app_pastelid_passphrase': settings.PASSPHRASE,
                                     'Content-Type': 'application/json'
                                 },
                                 "task_id", "")

            if not wn_task_id:
                raise Exception(f'{service_name}: No wn_task_id returned from WN for result_id {result_id}')

            upd = {
                "wn_task_id": wn_task_id,
                "pastel_id": settings.PASTEL_ID,
                "ticket_status": 'STARTED',
                "updated_at": datetime.utcnow(),
            }
            with db_context() as session:
                update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                crud.preburn_tx.mark_used(session, task_from_db.burn_txid)
        else:
            self.message = f'{service_name}: "WN Start" already called... [Result ID: {result_id}; ' \
                           f'WN Task ID: {task_from_db.wn_task_id}]'

        if not task_ipfs_link:
            with db_context() as session:
                task_from_db = get_task_from_db_by_task_id_func(session, result_id=result_id)

                self.message = f'{service_name}: Storing file into IPFS... [Result ID: {result_id}]'

                try:
                    ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
                    res = ipfs_client.add(task_from_db.original_file_local_path)
                    ipfs_link = res["Hash"]
                except Exception as e:
                    self.message = f'{service_name}: Error while storing file into IPFS... [Result ID: {result_id}]'

                if ipfs_link:
                    self.message = f'{service_name}: Updating DB with IPFS link... [Result ID: {result_id}; ' \
                                   f'IPFS Link: https://ipfs.io/ipfs/{ipfs_link}]'
                    upd = {"ipfs_link": ipfs_link, "updated_at": datetime.utcnow()}
                    update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)

        return result_id

    def re_register_file_task(self,
                              result_id,
                              get_task_from_db_by_task_id_func,
                              update_task_in_db_func,
                              service: wn.WalletNodeService,
                              service_name: str) -> str:
        self.message = f'{service_name}: Starting file re-registration... [Result ID: {result_id}]'

        with db_context() as session:
            task_from_db = get_task_from_db_by_task_id_func(session, result_id=result_id)

        if not task_from_db:
            raise PastelAPIException(f'{service_name}: No cascade result found for result_id {result_id}')

        if task_from_db.ticket_status == 'UPLOADED' or \
                task_from_db.ticket_status == 'PREBURN_FEE' or \
                task_from_db.ticket_status == 'STARTED':
            self.message = f'{service_name}: File registration (re_register_file) already started...' \
                           f' [Result ID: {result_id}]'
            return result_id

        self.message = f'{service_name}: New File - calling WN... [Result ID: {result_id}]'

        path = Path(task_from_db.original_file_local_path)
        if not path.is_file():
            if task_from_db.ipfs_link:
                try:
                    self.message = f'{service_name}: File not found locally, downloading from IPFS... ' \
                                   f'[Result ID: {result_id}]'
                    ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
                    ipfs_client.get(task_from_db.ipfs_link, path.parent)
                except Exception as e:
                    raise PastelAPIException(f'{service_name}: File not found locally and nor in IPFS: {e}')
                new_path = path.parent / task_from_db.ipfs_link
                new_path.rename(path)
            else:
                raise PastelAPIException(f'{service_name}: File not found locally and no IPFS link for '
                                         f'result_id {result_id}')

        data = open(path, 'rb')

        id_field_name = "image_id" if service == wn.WalletNodeService.SENSE else "file_id"
        wn_file_id, fee = wn.call(True,
                                  service,
                                  'upload',
                                  {},
                                  [('file',
                                    (task_from_db.original_file_name, data, task_from_db.original_file_content_type))],
                                  {},
                                  id_field_name, "estimated_fee")

        with db_context() as session:
            upd = {
                "wn_file_id": wn_file_id,
                "wn_fee": fee,
                "ticket_status": 'UPLOADED',
                "updated_at": datetime.utcnow(),
            }
            update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)

        return result_id


class CascadeAPITask(PastelAPITask):
    def on_success(self, retval, result_id, args, kwargs):
        PastelAPITask.on_success_base(args, crud.cascade.get_by_result_id, crud.cascade.update)

    def on_failure(self, exc, result_id, args, kwargs, einfo):
        PastelAPITask.on_failure_base(args, crud.cascade.get_by_result_id, crud.cascade.update)


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


# Exception for Cascade tasks
class PastelAPIException(Exception):
    def __init__(self, message):
        self.message = message or "PastelAPIException"
        super().__init__(self.message)
