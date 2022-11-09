import json

import ipfshttpclient as ipfshttpclient
from celery import shared_task

import app.utils.walletnode as wn
import app.utils.pasteld as psl
from app.core.config import settings
from app import crud, schemas
from app.db.session import db_context
from app.utils.filestorage import LocalFile
from .base import PastelTask


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, max_retries=5,
             name='cascade:register_image')
def register_image(self, local_file, work_id, ticket_id, user_id) -> str:
    self.message = f'Starting image registration... [Ticket ID: {ticket_id}]'

    with db_context() as session:
        cascade_task = crud.cascade.get_by_ticket_id(session, ticket_id=ticket_id)

    if not cascade_task:
        self.message = f'New image - calling WN... [Ticket ID: {ticket_id}]'
        data = local_file.read()
        wn_file_id, fee = wn.call(True,
                                  'upload',
                                  {},
                                  [('file', (local_file.name, data, local_file.type))],
                                  {},
                                  "file_id", "estimated_fee")

        height = psl.call("getblockcount", [])
        self.message = f'New image - adding image ticket to DB... [Ticket ID: {ticket_id}]'
        with db_context() as session:
            new_cascade_task = schemas.CascadeCreate(
                original_file_name=local_file.name,
                original_file_content_type=local_file.type,
                original_file_local_path=local_file.path,
                work_id=work_id,
                ticket_status=register_image.request.id,
                ticket_id=ticket_id,
                wn_file_id=wn_file_id,
                wn_fee=fee,
                height=height,
            )
            crud.cascade.create_with_owner(session, obj_in=new_cascade_task, owner_id=user_id)
    else:
        self.message = f'Image ticket is already in the DB... [Ticket ID: {ticket_id}]'

    return ticket_id


@shared_task(bind=True, autoretry_for=(Exception,),
             default_retry_delay=300, retry_backoff=150, max_retries=10,
             name='cascade:preburn_fee')
def preburn_fee(self, ticket_id) -> str:
    self.message = f'Searching for pre-burn tx for image registration... [Ticket ID: {ticket_id}]'

    with db_context() as session:
        cascade_task = crud.cascade.get_by_ticket_id(session, ticket_id=ticket_id)

    if not cascade_task:
        raise CascadeException(f'No cascade task found for ticket_id {ticket_id}')

    burn_amount = cascade_task.wn_fee / 5
    height = psl.call("getblockcount", [])

    if not cascade_task.burn_txid:
        with db_context() as session:
            burn_tx = crud.preburn_tx.get_bound_to_ticket(session, ticket_id=ticket_id)
            if not burn_tx:
                burn_tx = crud.preburn_tx.get_non_used_by_fee(session, fee=burn_amount)
                if not burn_tx:
                    self.message = f'No pre-burn tx, calling sendtoaddress... [Ticket ID: {ticket_id}]'
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
                self.message = f'Pre-burn tx [{cascade_task.burn_txid}] not confirmed yet, retrying...' \
                               f' [Ticket ID: {ticket_id}]'
                preburn_fee.retry()

            upd = {"burn_txid": burn_tx.txid, "ticket_status": preburn_fee.request.id}
            crud.cascade.update(session, db_obj=cascade_task, obj_in=upd)
    else:
        self.message = f'Pre-burn tx [{cascade_task.burn_txid}] already associated with image ticket...' \
                       f' [Ticket ID: {ticket_id}]'

    return ticket_id


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, max_retries=10,
             name='cascade:process', base=PastelTask)
def process(self, ticket_id) -> str:
    self.message = f'Register image in the Pastel Network... [Ticket ID: {ticket_id}]'

    with db_context() as session:
        cascade_task = crud.cascade.get_by_ticket_id(session, ticket_id=ticket_id)

    if not cascade_task:
        raise CascadeException(f'No cascade task found for ticket_id {ticket_id}')

    if not cascade_task.burn_txid:
        raise CascadeException(f'No burn txid for cascade ticket_id {ticket_id}')

    if not cascade_task.wn_task_id:
        self.message = f'Calling "WN Start"... [Ticket ID: {ticket_id}]'
        burn_txid = cascade_task.burn_txid
        wn_file_id = cascade_task.wn_file_id
        wn_task_id = wn.call(True,
                             f'start/{wn_file_id}',
                             json.dumps({
                                 "burn_txid": burn_txid,
                                 "app_pastelid": settings.PASTEL_ID,
                             }),
                             [],
                             {
                                 'app_pastelid_passphrase': settings.PASSPHRASE,
                                 'Content-Type': 'application/json'
                             },
                             "task_id", "")

        # TODO: check if wn_task_id is not empty!!

        with db_context() as session:
            upd = {
                "wn_task_id": wn_task_id,
                "ticket_status": process.request.id,
                "pastel_id": settings.PASTEL_ID,
            }
            crud.cascade.update(session, db_obj=cascade_task, obj_in=upd)
            crud.preburn_tx.mark_used(session, cascade_task.burn_txid)
    else:
        self.message = f'"WN Start" already called... [Ticket ID: {ticket_id}; WN Task ID: {cascade_task.wn_task_id}]'

    if not cascade_task.ipfs_link:
        self.message = f'Storing image into IPFS... [Ticket ID: {ticket_id}]'

        ipfs_client = ipfshttpclient.connect()
        res = ipfs_client.add(cascade_task.original_file_local_path)
        ipfs_link = res["Hash"]

        if ipfs_link:
            self.message = f'Updating DB with IPFS link... [Ticket ID: {ticket_id}; ' \
                           f'IPFS Link: https://ipfs.io/ipfs/{ipfs_link}]'
            with db_context() as session:
                upd = {"ipfs_link": ipfs_link}
                crud.cascade.update(session, db_obj=cascade_task, obj_in=upd)

    return ticket_id


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, max_retries=5,
             name='cascade:re_register_image')
def re_register_image(self, ticket_id) -> str:
    self.message = f'Starting image re-registration... [Ticket ID: {ticket_id}]'

    with db_context() as session:
        cascade_task = crud.cascade.get_by_ticket_id(session, ticket_id=ticket_id)

    if not cascade_task:
        raise CascadeException(f'No cascade ticket found for ticket_id {ticket_id}')
    else:
        self.message = f'New image - calling WN... [Ticket ID: {ticket_id}]'
        data = LocalFile.read_file(cascade_task.original_file_local_path)
        wn_file_id, fee = wn.call(True,
                                  'upload',
                                  {},
                                  [('file', (cascade_task.original_file_name, data,
                                             cascade_task.original_file_content_type))],
                                  {},
                                  "file_id", "estimated_fee")

        with db_context() as session:
            upd = {
                "wn_file_id": wn_file_id,
                "wn_fee": fee,
                "ticket_status": re_register_image.request.id,
            }
            crud.cascade.update(session, db_obj=cascade_task, obj_in=upd)

    return ticket_id


@shared_task(bind=True, utoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5},
             name='sense:sense_process')
def sense_process(self):
    return ""


# Exception for Cascade tasks
class CascadeException(Exception):
    def __init__(self, message):
        self.message = message or "CascadeException"
        super().__init__(self.message)
