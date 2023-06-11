from celery import shared_task
from requests import RequestException
import json

from app.core.status import DbStatus
from .pastel_tasks import PastelAPITask, PastelAPIException
from app import crud, schemas
from app.utils.walletnode import WalletNodeService, WalletnodeException
from app.utils.pasteld import PasteldException
from app.core.config import settings


class CascadeAPITask(PastelAPITask):
    def on_success(self, retval, result_id, args, kwargs):
        PastelAPITask.on_success_base(args, crud.cascade.get_by_result_id, crud.cascade.update)

    def on_failure(self, exc, result_id, args, kwargs, einfo):
        PastelAPITask.on_failure_base(args, crud.cascade.get_by_result_id, crud.cascade.update)

    def get_request_form(self, task_from_db) -> str:
        return json.dumps(
            {
                "burn_txid": task_from_db.burn_txid,
                "app_pastelid": settings.PASTEL_ID,
                "make_publicly_accessible": task_from_db.make_publicly_accessible,
            })

    def check_specific_conditions(self, task_from_db) -> (bool, str):
        if task_from_db.ticket_status != DbStatus.PREBURN_FEE.value:
            err_msg = f'Cascade: process_task: Wrong task state - "{task_from_db.ticket_status}", ' \
                      f'Should be {DbStatus.PREBURN_FEE.value}' \
                      f'... [Result ID: {task_from_db.ticket_id}]'
            return False, err_msg
        if not task_from_db.burn_txid:
            raise PastelAPIException(f'Cascade: No burn txid for result_id {task_from_db.ticket_id}')
        return True, ''

@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=5,
             name='cascade:register_file', base=CascadeAPITask)
def register_file(self, result_id, local_file, request_id, user_id, ipfs_hash, make_publicly_accessible) -> str:
    return self.register_file_task(
        result_id, local_file, user_id,
        lambda height: schemas.CascadeCreate(
            original_file_name=local_file.name,
            original_file_content_type=local_file.type,
            original_file_local_path=local_file.path,
            original_file_ipfs_link=ipfs_hash,
            make_publicly_accessible=make_publicly_accessible,
            work_id=request_id,
            ticket_id=result_id,
            ticket_status=DbStatus.NEW.value,
            wn_file_id='',
            wn_fee=0,
            height=height,
        ),
        crud.cascade.get_by_result_id,
        crud.cascade.create_with_owner,
        crud.cascade.update,
        register_file.retry,
        WalletNodeService.CASCADE,
        "upload", "file_id", "required_preburn_amount", 5)


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             default_retry_delay=300, retry_backoff=150, max_retries=10,
             name='cascade:preburn_fee', base=CascadeAPITask)
def preburn_fee(self, result_id) -> str:
    return self.preburn_fee_task(result_id,
                                 crud.cascade.get_by_result_id,
                                 crud.cascade.update,
                                 preburn_fee.retry,
                                 WalletNodeService.CASCADE)


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=10,
             name='cascade:process', base=CascadeAPITask)
def process(self, ticket_id) -> str:
    return self.process_task(ticket_id,
                             crud.cascade.get_by_result_id,
                             crud.cascade.update,
                             process.retry,
                             WalletNodeService.CASCADE)


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=5,
             name='cascade:re_register_file', base=CascadeAPITask)
def re_register_file(self, result_id) -> str:
    return self.re_register_file_task(result_id,
                                      crud.cascade.get_by_result_id,
                                      crud.cascade.update,
                                      WalletNodeService.CASCADE,
                                      "upload", "file_id", "required_preburn_amount", 5)
