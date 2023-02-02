from celery import shared_task
from requests import RequestException

from .pastel_tasks import PastelAPITask
from app import crud, schemas
from app.utils.walletnode import WalletNodeService, WalletnodeException
from app.utils.pasteld import PasteldException


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=5,
             name='sense:register_file', base=PastelAPITask)
def register_file(self, local_file, work_id, ticket_id, user_id) -> str:
    return self.register_file_task(
        local_file, work_id, ticket_id, user_id,
        schemas.SenseCreate,
        crud.sense.get_by_result_id,
        crud.sense.create_with_owner,
        register_file.retry,
        WalletNodeService.SENSE,
        "Sense")


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             default_retry_delay=300, retry_backoff=150, max_retries=10,
             name='sense:preburn_fee', base=PastelAPITask)
def preburn_fee(self, ticket_id) -> str:
    return self.preburn_fee_task(ticket_id,
                                 crud.sense.get_by_result_id,
                                 crud.sense.update,
                                 preburn_fee.retry,
                                 "Sense")


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=10,
             name='sense:process', base=PastelAPITask)
def process(self, ticket_id) -> str:
    return self.process_task(ticket_id,
                             crud.sense.get_by_result_id,
                             crud.sense.update,
                             WalletNodeService.SENSE,
                             "Sense")


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=5,
             name='sense:re_register_file', base=PastelAPITask)
def re_register_file(self, ticket_id) -> str:
    return self.re_register_file_task(ticket_id,
                                      crud.sense.get_by_result_id,
                                      crud.sense.update,
                                      WalletNodeService.SENSE,
                                      "Sense")
