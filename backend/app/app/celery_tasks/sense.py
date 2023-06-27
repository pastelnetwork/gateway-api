from requests import RequestException
import json

from celery import shared_task
from celery.utils.log import get_task_logger

from app.core.status import DbStatus
from .pastel_tasks import PastelAPITask, PastelAPIException
from app import crud, schemas
from app.utils.walletnode import WalletNodeService, WalletnodeException
from app.utils.pasteld import PasteldException
from app.core.config import settings

logger = get_task_logger(__name__)


class SenseAPITask(PastelAPITask):
    def on_success(self, retval, result_id, args, kwargs):
        PastelAPITask.on_success_base(args, crud.sense.get_by_result_id, crud.sense.update)

    def on_failure(self, exc, result_id, args, kwargs, einfo):
        PastelAPITask.on_failure_base(args, crud.sense.get_by_result_id, crud.sense.update)

    def get_request_form(self, task_from_db) -> str:
        return json.dumps(
            {
                "burn_txid": task_from_db.burn_txid,
                "app_pastelid": settings.PASTEL_ID,
                "collection_act_txid": task_from_db.collection_act_txid,
                "open_api_group_id": task_from_db.open_api_group_id,
            })

    def check_specific_conditions(self, task_from_db) -> (bool, str):
        if task_from_db.process_status != DbStatus.PREBURN_FEE.value:
            err_msg = f'Sense: process_task: Wrong task state - "{task_from_db.process_status}", ' \
                      f'Should be {DbStatus.PREBURN_FEE.value}' \
                      f'... [Result ID: {task_from_db.result_id}]'
            return False, err_msg
        if not task_from_db.burn_txid:
            raise PastelAPIException(f'Sense: No burn txid for result_id {task_from_db.result_id}')
        return True, ''


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=5,
             name='sense:register_file', base=SenseAPITask)
def register_file(self, result_id, local_file, request_id, user_id, ipfs_hash: str,
                  make_publicly_accessible: bool, collection_act_txid: str, open_api_group_id: str,
                  after_activation_transfer_to_pastelid) -> str:
    return self.register_file_task(
        result_id, local_file, user_id,
        lambda height: schemas.SenseCreate(
            original_file_name=local_file.name,
            original_file_content_type=local_file.type,
            original_file_local_path=local_file.path,
            original_file_ipfs_link=ipfs_hash,
            make_publicly_accessible=make_publicly_accessible,
            offer_ticket_intended_rcpt_pastel_id=after_activation_transfer_to_pastelid,
            collection_act_txid=collection_act_txid,
            open_api_group_id=open_api_group_id,
            request_id=request_id,
            result_id=result_id,
            process_status=DbStatus.NEW.value,
            wn_file_id='',
            wn_fee=0,
            height=height,
        ),
        crud.sense.get_by_result_id,
        crud.sense.create_with_owner,
        crud.sense.update,
        register_file.retry,
        WalletNodeService.SENSE,
        "upload", "image_id", "required_preburn_amount", 5)


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             default_retry_delay=300, retry_backoff=150, max_retries=10,
             name='sense:preburn_fee', base=SenseAPITask)
def preburn_fee(self, result_id) -> str:
    return self.preburn_fee_task(result_id,
                                 crud.sense.get_by_result_id,
                                 crud.sense.update,
                                 preburn_fee.retry,
                                 WalletNodeService.SENSE)


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=10,
             name='sense:process', base=SenseAPITask)
def process(self, result_id) -> str:
    return self.process_task(result_id,
                             crud.sense.get_by_result_id,
                             crud.sense.update,
                             process.retry,
                             WalletNodeService.SENSE)


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=5,
             name='sense:re_register_file', base=SenseAPITask)
def re_register_file(self, result_id) -> str:
    return self.re_register_file_task(result_id,
                                      crud.sense.get_by_result_id,
                                      crud.sense.update,
                                      WalletNodeService.SENSE,
                                      "upload", "image_id", "required_preburn_amount", 5)
