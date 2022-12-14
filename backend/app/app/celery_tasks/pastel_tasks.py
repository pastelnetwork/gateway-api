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
    def get_ticket_id_from_args(args) -> str:
        if args:
            if len(args) == 1:      # preburn_fee, process, re_register_file
                return args[0]
            elif len(args) == 4:    # register_file
                return args[2]
        raise Exception("Invalid args")

    @staticmethod
    def update_ticket_status(ticket_id, status, get_by_ticket_id_func, update_func):
        with db_context() as session:
            ticket = get_by_ticket_id_func(session, ticket_id=ticket_id)
            if not ticket:
                raise Exception("Ticket not found")
            upd = {"ticket_status": status, "updated_at": datetime.utcnow()}
            update_func(session, db_obj=ticket, obj_in=upd)

    @staticmethod
    def on_success_base(args, get_by_ticket_id_func, update_func):
        ticket_id = PastelAPITask.get_ticket_id_from_args(args)
        PastelAPITask.update_ticket_status(ticket_id, "SUCCESS", get_by_ticket_id_func, update_func)

    @staticmethod
    def on_failure_base(args, get_by_ticket_id_func, update_func):
        ticket_id = PastelAPITask.get_ticket_id_from_args(args)
        PastelAPITask.update_ticket_status(ticket_id, "FAILURE", get_by_ticket_id_func, update_func)

    # def on_retry(self, exc, task_id, args, kwargs, einfo):
    #     print(f'{task_id} retrying: {exc}')

    def register_file_task(self, local_file, work_id, ticket_id, user_id,
                           create_klass,
                           get_by_ticket_id_func,
                           create_with_owner_func,
                           retry_func,
                           celery_task_id,
                           service: wn.WalletNodeService,
                           service_name: str):
        self.message = f'{service_name}: Starting file registration... [Ticket ID: {ticket_id}]'

        with db_context() as session:
            task = get_by_ticket_id_func(session, ticket_id=ticket_id)

        if task:
            self.message = f'{service_name}: Ticket is already in the DB... [Ticket ID: {ticket_id}]'
            return ticket_id

        self.message = f'{service_name}: New file - calling WN... [Ticket ID: {ticket_id}]'
        data = local_file.read()
        wn_file_id, fee = wn.call(True,
                                  service,
                                  'upload',
                                  {},
                                  [('file', (local_file.name, data, local_file.type))],
                                  {},
                                  "file_id", "estimated_fee")

        if not wn_file_id:
            self.message = f'{service_name}: Upload call failed for file {local_file.name}, retrying...'
            retry_func()
        if fee <= 0:
            self.message = f'{service_name}: Wrong WN Fee {fee} for file {local_file.name}, retrying...'
            retry_func()

        height = psl.call("getblockcount", [])
        self.message = f'{service_name}: New file - adding ticket to DB... [Ticket ID: {ticket_id}]'
        with db_context() as session:
            new_task = create_klass(
                original_file_name=local_file.name,
                original_file_content_type=local_file.type,
                original_file_local_path=local_file.path,
                work_id=work_id,
                ticket_status=celery_task_id,
                ticket_id=ticket_id,
                wn_file_id=wn_file_id,
                wn_fee=fee,
                height=height,
            )
            create_with_owner_func(session, obj_in=new_task, owner_id=user_id)

        return ticket_id

    def preburn_fee_task(self, ticket_id,
                         get_by_ticket_id_func,
                         update_func,
                         retry_func,
                         celery_task_id,
                         service: wn.WalletNodeService,
                         service_name: str) -> str:
        self.message = f'{service_name}: Searching for pre-burn tx for registration... [Ticket ID: {ticket_id}]'

        with db_context() as session:
            task = get_by_ticket_id_func(session, ticket_id=ticket_id)

        if not task:
            raise PastelAPIException(f'{service_name}: No task found for ticket_id {ticket_id}')

        if task.ticket_status == "STARTED":
            self.message = f'{service_name}: Registration (preburn_fee) already started... [Ticket ID: {ticket_id}]'
            return ticket_id

        burn_amount = task.wn_fee / 5
        height = psl.call("getblockcount", [])

        if task.burn_txid:
            self.message = f'{service_name}: Pre-burn tx [{task.burn_txid}] already associated with ticket...' \
                           f' [Ticket ID: {ticket_id}]'
            return ticket_id

        with db_context() as session:
            burn_tx = crud.preburn_tx.get_bound_to_ticket(session, ticket_id=ticket_id)
            if not burn_tx:
                burn_tx = crud.preburn_tx.get_non_used_by_fee(session, fee=burn_amount)
                if not burn_tx:
                    self.message = f'{service_name}: No pre-burn tx, calling sendtoaddress... [Ticket ID: {ticket_id}]'
                    burn_txid = psl.call("sendtoaddress", [settings.BURN_ADDRESS, burn_amount])
                    burn_tx = crud.preburn_tx.create_new_bound(session,
                                                               fee=burn_amount,
                                                               height=height,
                                                               txid=burn_txid,
                                                               ticket_id=ticket_id)
                else:
                    burn_tx = crud.preburn_tx.bind_pending_to_ticket(session, burn_tx,
                                                                     ticket_id=ticket_id)
            if burn_tx.height > height - 5:
                self.message = f'{service_name}: Pre-burn tx [{task.burn_txid}] not confirmed yet, retrying...' \
                               f' [Ticket ID: {ticket_id}]'
                retry_func()

            upd = {
                "burn_txid": burn_tx.txid,
                "ticket_status": celery_task_id,
                "updated_at": datetime.utcnow(),
            }
            update_func(session, db_obj=task, obj_in=upd)

        return ticket_id

    def process_task(self, ticket_id,
                     get_by_ticket_id_func,
                     update_func,
                     retry_func,
                     celery_task_id,
                     service: wn.WalletNodeService,
                     service_name: str) -> str:
        self.message = f'{service_name}: Register file in the Pastel Network... [Ticket ID: {ticket_id}]'

        with db_context() as session:
            task = get_by_ticket_id_func(session, ticket_id=ticket_id)

        if not task:
            raise PastelAPIException(f'{service_name}: No task found for ticket_id {ticket_id}')

        if task.wn_fee == 0:
            raise PastelAPIException(f'{service_name}: Wrong WN Fee for ticket_id {ticket_id}')

        if not task.wn_file_id:
            raise PastelAPIException(f'{service_name}: Wrong WN file ID for ticket_id {ticket_id}')

        if task.ticket_status == "STARTED":
            self.message = f'{service_name}: File registration (process) already started... [Ticket ID: {ticket_id}]'
            return ticket_id

        if not task.burn_txid:
            raise PastelAPIException(f'{service_name}: No burn txid for ticket_id {ticket_id}')

        task_ipfs_link = task.ipfs_link

        if not task.wn_task_id:
            self.message = f'{service_name}: Calling "WN Start"... [Ticket ID: {ticket_id}]'
            burn_txid = task.burn_txid
            wn_file_id = task.wn_file_id
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
                raise Exception(f'{service_name}: No wn_task_id returned from WN for ticket_id {ticket_id}')

            upd = {
                "wn_task_id": wn_task_id,
                "pastel_id": settings.PASTEL_ID,
                "ticket_status": celery_task_id,
                "updated_at": datetime.utcnow(),
            }
            with db_context() as session:
                update_func(session, db_obj=task, obj_in=upd)
                crud.preburn_tx.mark_used(session, task.burn_txid)
        else:
            self.message = f'{service_name}: "WN Start" already called... [Ticket ID: {ticket_id}; ' \
                           f'WN Task ID: {task.wn_task_id}]'

        if not task_ipfs_link:
            with db_context() as session:
                task = get_by_ticket_id_func(session, ticket_id=ticket_id)

                self.message = f'{service_name}: Storing file into IPFS... [Ticket ID: {ticket_id}]'

                ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
                res = ipfs_client.add(task.original_file_local_path)
                ipfs_link = res["Hash"]

                if ipfs_link:
                    self.message = f'{service_name}: Updating DB with IPFS link... [Ticket ID: {ticket_id}; ' \
                                   f'IPFS Link: https://ipfs.io/ipfs/{ipfs_link}]'
                    upd = {"ipfs_link": ipfs_link, "updated_at": datetime.utcnow()}
                    update_func(session, db_obj=task, obj_in=upd)

        return ticket_id

    def re_register_file_task(self, ticket_id,
                              get_by_ticket_id_func,
                              update_func,
                              retry_func,
                              celery_task_id,
                              service: wn.WalletNodeService,
                              service_name: str) -> str:
        self.message = f'{service_name}: Starting file re-registration... [Ticket ID: {ticket_id}]'

        with db_context() as session:
            task = get_by_ticket_id_func(session, ticket_id=ticket_id)

        if not task:
            raise PastelAPIException(f'{service_name}: No cascade ticket found for ticket_id {ticket_id}')

        if task.ticket_status == "STARTED":
            self.message = f'{service_name}: File registration (re_register_file) already started...' \
                           f' [Ticket ID: {ticket_id}]'
            return ticket_id

        self.message = f'{service_name}: New File - calling WN... [Ticket ID: {ticket_id}]'

        path = Path(task.original_file_local_path)
        if not path.is_file():
            if task.ipfs_link:
                self.message = f'{service_name}: File not found locally, downloading from IPFS... ' \
                               f'[Ticket ID: {ticket_id}]'
                ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
                ipfs_client.get(task.ipfs_link, path.parent)
                new_path = path.parent / task.ipfs_link
                new_path.rename(path)
            else:
                raise PastelAPIException(f'{service_name}: File not found locally and no IPFS link for '
                                         f'ticket_id {ticket_id}')

        data = open(path, 'rb')

        wn_file_id, fee = wn.call(True,
                                  service,
                                  'upload',
                                  {},
                                  [('file', (task.original_file_name, data, task.original_file_content_type))],
                                  {},
                                  "file_id", "estimated_fee")

        with db_context() as session:
            upd = {
                "wn_file_id": wn_file_id,
                "wn_fee": fee,
                "ticket_status": celery_task_id,
                "updated_at": datetime.utcnow(),
            }
            update_func(session, db_obj=task, obj_in=upd)

        return ticket_id


class CascadeAPITask(PastelAPITask):
    def on_success(self, retval, task_id, args, kwargs):
        PastelAPITask.on_success_base(args, crud.cascade.get_by_ticket_id, crud.cascade.update)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        PastelAPITask.on_failure_base(args, crud.cascade.get_by_ticket_id, crud.cascade.update)


def get_celery_task_info(celery_task_id):
    """
    return task info for the given celery_task_id
    """
    task_result = AsyncResult(celery_task_id)
    result = {
        "celery_task_id": celery_task_id,
        "celery_task_status": task_result.status,
        "celery_task_state": task_result.state,
        "celery_task_result": str(task_result.result)
    }
    return result


# Exception for Cascade tasks
class PastelAPIException(Exception):
    def __init__(self, message):
        self.message = message or "PastelAPIException"
        super().__init__(self.message)
