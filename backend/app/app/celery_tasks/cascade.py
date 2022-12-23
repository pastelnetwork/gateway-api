from celery import shared_task
from requests import RequestException

from .pastel_tasks import CascadeAPITask
from app import crud, schemas
from app.utils.walletnode import WalletNodeService, WalletnodeException
from app.utils.pasteld import PasteldException


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=5,
             name='cascade:register_file', base=CascadeAPITask)
def register_file(self, local_file, work_id, ticket_id, user_id) -> str:
    return self.register_file_task(
        local_file, work_id, ticket_id, user_id,
        schemas.CascadeCreate,
        crud.cascade.get_by_ticket_id,
        crud.cascade.create_with_owner,
        register_file.retry,
        WalletNodeService.CASCADE,
        "Cascade")


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             default_retry_delay=300, retry_backoff=150, max_retries=10,
             name='cascade:preburn_fee', base=CascadeAPITask)
def preburn_fee(self, ticket_id) -> str:
    return self.preburn_fee_task(ticket_id,
                                 crud.cascade.get_by_ticket_id,
                                 crud.cascade.update,
                                 preburn_fee.retry,
                                 "Cascade")


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=10,
             name='cascade:process', base=CascadeAPITask)
def process(self, ticket_id) -> str:
    return self.process_task(ticket_id,
                             crud.cascade.get_by_ticket_id,
                             crud.cascade.update,
                             WalletNodeService.CASCADE,
                             "Cascade")


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=5,
             name='cascade:re_register_file', base=CascadeAPITask)
def re_register_file(self, ticket_id) -> str:
    return self.re_register_file_task(ticket_id,
                                      crud.cascade.get_by_ticket_id,
                                      crud.cascade.update,
                                      WalletNodeService.CASCADE,
                                      "Cascade")
