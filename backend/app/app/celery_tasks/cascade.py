from requests import RequestException
import json

from celery import shared_task
from celery.utils.log import get_task_logger

from .pastel_tasks import PastelAPITask, PastelAPIException
from app.core.status import DbStatus
from app import crud, schemas
from app.utils.walletnode import WalletNodeService, WalletnodeException
from app.utils.pasteld import PasteldException
from app.core.config import settings
from ..models import ApiKey

logger = get_task_logger(__name__)


class CascadeAPITask(PastelAPITask):
    def on_success(self, retval, result_id, args, kwargs):
        PastelAPITask.on_success_base(args, crud.cascade.get_by_result_id, crud.cascade.update)

    def on_failure(self, exc, result_id, args, kwargs, einfo):
        PastelAPITask.on_failure_base(args, crud.cascade.get_by_result_id, crud.cascade.update)

    def get_request_form(self, task_from_db, funding_address: str | None = None) -> str:
        form = {
            "burn_txid": task_from_db.burn_txid,
            "app_pastelid": task_from_db.pastel_id,
            "make_publicly_accessible": task_from_db.make_publicly_accessible,
        }
        if funding_address:
            form["spendable_address"] = funding_address
        return json.dumps(form)

    def check_specific_conditions(self, task_from_db) -> (bool, str):
        if task_from_db.process_status != DbStatus.PREBURN_FEE.value:
            err_msg = f'Cascade: process_task: Wrong task state - "{task_from_db.process_status}", ' \
                      f'Should be {DbStatus.PREBURN_FEE.value}' \
                      f'... [Result ID: {task_from_db.result_id}]'
            return False, err_msg
        if not task_from_db.burn_txid:
            raise PastelAPIException(f'Cascade: No burn txid for result_id {task_from_db.result_id}')
        return True, ''


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=settings.REGISTER_FILE_RETRY_BACKOFF,
             retry_backoff_max=settings.REGISTER_FILE_RETRY_BACKOFF_MAX,
             max_retries=settings.REGISTER_FILE_MAX_RETRIES,
             soft_time_limit=settings.REGISTER_FILE_SOFT_TIME_LIMIT,
             time_limit=settings.REGISTER_FILE_TIME_LIMIT,
             name='cascade:register_file', base=CascadeAPITask)
def register_file(self, result_id, local_file, request_id, user_id, api_key: ApiKey, ipfs_hash: str,
                  make_publicly_accessible: bool, _collection_act_txid, _open_api_group_id,
                  after_activation_transfer_to_pastelid: str) -> str:
    return self.register_file_task(
        result_id, local_file, user_id, api_key,
        lambda height: schemas.CascadeCreate(
            original_file_name=local_file.name,
            original_file_content_type=local_file.type,
            original_file_local_path=local_file.path,
            original_file_ipfs_link=ipfs_hash,
            make_publicly_accessible=make_publicly_accessible,
            offer_ticket_intended_rcpt_pastel_id=after_activation_transfer_to_pastelid,
            request_id=request_id,
            result_id=result_id,
            process_status=DbStatus.NEW.value,
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
             retry_backoff=settings.PREBURN_FEE_RETRY_BACKOFF,
             retry_backoff_max=settings.PREBURN_FEE_RETRY_BACKOFF_MAX,
             max_retries=settings.PREBURN_FEE_MAX_RETRIES,
             soft_time_limit=settings.PREBURN_FEE_SOFT_TIME_LIMIT,
             time_limit=settings.PREBURN_FEE_TIME_LIMIT,
             name='cascade:preburn_fee', base=CascadeAPITask)
def preburn_fee(self, result_id) -> str:
    return self.preburn_fee_task(result_id,
                                 crud.cascade.get_by_result_id,
                                 crud.cascade.update,
                                 preburn_fee.retry,
                                 WalletNodeService.CASCADE)


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=settings.PROCESS_RETRY_BACKOFF,
             retry_backoff_max=settings.PROCESS_RETRY_BACKOFF_MAX,
             max_retries=settings.PROCESS_MAX_RETRIES,
             soft_time_limit=settings.PROCESS_SOFT_TIME_LIMIT,
             time_limit=settings.PROCESS_TIME_LIMIT,
             name='cascade:process', base=CascadeAPITask)
def process(self, result_id) -> str:
    return self.process_task(result_id,
                             crud.cascade.get_by_result_id,
                             crud.cascade.update,
                             process.retry,
                             WalletNodeService.CASCADE)


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=settings.RE_REGISTER_FILE_RETRY_BACKOFF,
             retry_backoff_max=settings.RE_REGISTER_FILE_RETRY_BACKOFF_MAX,
             max_retries=settings.RE_REGISTER_FILE_MAX_RETRIES,
             soft_time_limit=settings.RE_REGISTER_FILE_SOFT_TIME_LIMIT,
             time_limit=settings.RE_REGISTER_FILE_TIME_LIMIT,
             name='cascade:re_register_file', base=CascadeAPITask)
def re_register_file(self, result_id) -> str:
    return self.re_register_file_task(result_id,
                                      crud.cascade.get_by_result_id,
                                      crud.cascade.update,
                                      WalletNodeService.CASCADE,
                                      "upload", "file_id", "required_preburn_amount", 5)
