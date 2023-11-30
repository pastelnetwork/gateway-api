from typing import List
from requests import RequestException
import json
from datetime import datetime

from celery import shared_task
from celery.utils.log import get_task_logger

from .pastel_tasks import PastelAPITask, PastelAPIException, set_status_message
from app.core.status import DbStatus
from app import crud, schemas
from app.utils.walletnode import WalletNodeService, WalletnodeException
from app.utils import walletnode as wn, pasteld as psl
from app.utils.pasteld import PasteldException
from app.core.config import settings
from app.db.session import db_context
from app.utils.authentication import send_alert_email
from ..models import ApiKey
from ..utils.secret_manager import get_pastelid_pwd_from_secret_manager

logger = get_task_logger(__name__)

# NEW->STARTED->REGISTERED->DONE
#               ERROR->RESTARTED->STARTED->REGISTERED->DONE


class CollectionsAPITask(PastelAPITask):
    def on_success(self, retval, result_id, args, kwargs):
        PastelAPITask.on_success_base(args, crud.collection.get_by_result_id, crud.collection.update)

    def on_failure(self, exc, result_id, args, kwargs, einfo):
        PastelAPITask.on_failure_base(args, crud.collection.get_by_result_id, crud.collection.update)

    def get_request_form(self, task_from_db, spendable_address: str | None) -> str:
        if not spendable_address:
            spendable_address = psl.find_address_with_funds(settings.COLLECTION_REG_TICKET_PRICE)
            if not spendable_address:
                logger.error(f"Collection-{task_from_db.item_type}: No spendable address "
                             f"found for amount > {settings.COLLECTION_REG_TICKET_PRICE}. "
                             f"[Result ID: {task_from_db.result_id}]")
                send_alert_email(f"No spendable address found to pay Collection fee in the amount > "
                                 f"{settings.COLLECTION_REG_TICKET_PRICE}")
                raise PastelAPIException(f"No spendable address found for amount > "
                                         f"{settings.COLLECTION_REG_TICKET_PRICE}")
        return json.dumps(
            {
                "app_pastelid": task_from_db.pastel_id,
                "collection_item_copy_count": task_from_db.collection_item_copy_count,
                "collection_name": task_from_db.collection_name,
                "green": task_from_db.green,
                "item_type": task_from_db.item_type,
                "list_of_pastelids_of_authorized_contributors": task_from_db.authorized_pastel_ids,
                "max_collection_entries": task_from_db.max_collection_entries,
                "max_permitted_open_nsfw_score": task_from_db.max_permitted_open_nsfw_score,
                "minimum_similarity_score_to_first_entry_in_collection":
                    task_from_db.minimum_similarity_score_to_first_entry_in_collection,
                "no_of_days_to_finalize_collection": task_from_db.no_of_days_to_finalize_collection,
                "royalty": task_from_db.royalty,
                "spendable_address": spendable_address
            })

    def check_specific_conditions(self, task_from_db) -> (bool, str):
        pass


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=settings.COLLECTION_REGISTER_RETRY_BACKOFF,
             retry_backoff_max=settings.COLLECTION_REGISTER_RETRY_BACKOFF_MAX,
             max_retries=settings.COLLECTION_REGISTER_MAX_RETRIES,
             soft_time_limit=settings.COLLECTION_REGISTER_SOFT_TIME_LIMIT,
             time_limit=settings.COLLECTION_REGISTER_TIME_LIMIT,
             name='collection:register', base=CollectionsAPITask)
def register(self, result_id, user_id, api_key: ApiKey,
             item_type: str, collection_name: str, max_collection_entries: int, collection_item_copy_count: int,
             authorized_pastel_ids: List,
             max_permitted_open_nsfw_score: float, minimum_similarity_score_to_first_entry_in_collection: float,
             no_of_days_to_finalize_collection: int, royalty: float, green: bool) -> str:
    logger.info(f'Collection-{item_type}: Register collection in the Pastel Network... [Result ID: {result_id}]')

    with db_context() as session:
        task_in_db = crud.collection.get_by_result_id(session, result_id=result_id)

    if task_in_db:
        logger.warn(f'Collection-{item_type}: Task is already in the DB. Status is {task_in_db.process_status}... '
                    f'[Result ID: {result_id}]')
        return result_id

    logger.info(f'Collection-{item_type} New file - adding record to DB... [Result ID: {result_id}]')

    # can throw exception here - this called from celery task, it will retry it on specific exceptions
    height = psl.call("getblockcount", [])
    logger.info(f'Collection-{item_type}: Ticket will be created at height {height} [Result ID: {result_id}]')

    new_task = schemas.CollectionCreate(
        result_id=result_id,
        item_type=item_type,
        pastel_id=api_key.pastel_id if (api_key and api_key.pastel_id) else settings.PASTEL_ID,
        collection_name=collection_name,
        max_collection_entries=max_collection_entries,
        collection_item_copy_count=collection_item_copy_count,
        authorized_pastel_ids=authorized_pastel_ids,
        max_permitted_open_nsfw_score=max_permitted_open_nsfw_score,
        minimum_similarity_score_to_first_entry_in_collection=minimum_similarity_score_to_first_entry_in_collection,
        no_of_days_to_finalize_collection=no_of_days_to_finalize_collection,
        royalty=royalty,
        green=green,
        height=height,
        process_status=DbStatus.NEW.value,
    )
    with db_context() as session:
        crud.collection.create_with_owner(session, obj_in=new_task, owner_id=user_id)

    logger.info(f'Collection-{item_type}: New record created. process_task exiting. [Result ID: {result_id}]')
    return result_id


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=settings.PROCESS_RETRY_BACKOFF,
             retry_backoff_max=settings.PROCESS_RETRY_BACKOFF_MAX,
             max_retries=settings.PROCESS_MAX_RETRIES,
             soft_time_limit=settings.PROCESS_SOFT_TIME_LIMIT,
             time_limit=settings.PROCESS_TIME_LIMIT,
             name='collection:process', base=CollectionsAPITask)
def process(self, result_id) -> str:
    logger.info(f'Collection: Register file in the Pastel Network... [Result ID: {result_id}]')

    with db_context() as session:
        task_from_db = crud.collection.get_by_result_id(session, result_id=result_id)

    if not task_from_db:
        logger.error(f'Collection: No task found for result_id {result_id}')
        raise PastelAPIException(f'Collection: No task found for result_id {result_id}')

    if task_from_db.process_status != DbStatus.RESTARTED.value and task_from_db.process_status != DbStatus.NEW.value:
        logger.warn(f'Collection-{task_from_db.item_type}: process: '
                    f'Wrong task state - "{task_from_db.process_status}", '
                    f'Should be {DbStatus.RESTARTED.value} OR {DbStatus.NEW.value}... [Result ID: {result_id}]')
        return result_id

    funding_address = None
    # with db_context() as session:
    #     funding_address = crud.user.get_funding_address(session, owner_id=task_from_db.owner_id,
    #                                                     default_value=settings.MAIN_GATEWAY_ADDRESS)
    # if not psl.check_address_balance(funding_address, settings.MIN_TICKET_PRICE_BALANCE,
    #                                  f"Collection-{task_from_db.item_type} ticket"):
    #     raise PastelAPIException(f"No enough funds in spendable address {funding_address} "
    #                              f"to pay Collection-{task_from_db.item_type} ticket fee")

    # can throw exception here
    form = self.get_request_form(task_from_db, funding_address)

    logger.info(f'Collection-{task_from_db.item_type}: Calling WN to start collection ticket registration '
                f'[Result ID: {result_id}]')
    wn_task_id = ""
    try:
        pastel_id_pwd = get_pastelid_pwd_from_secret_manager(task_from_db.pastel_id)
        if not pastel_id_pwd:
            logger.error(f"Pastel ID {task_from_db.pastel_id} not found in secret manager")
            set_status_message(crud.collection.update, task_from_db,
                               f'No passphrase found for PastelID = {task_from_db.pastel_id}. Throwing exception')
            raise Exception(f'Collections-{task_from_db.item_type}: No passphrase found for PastelID = '
                            f'{task_from_db.pastel_id}. Throwing exception')

        wn_task_id = wn.call(True,
                             WalletNodeService.COLLECTION,
                             "register",
                             form,
                             [],
                             {
                                 'Authorization': pastel_id_pwd,
                                 'Content-Type': 'application/json'
                             },
                             "task_id", "")
    except Exception as e:
        logger.error(f'Collections-{task_from_db.item_type}: '
                     f'Error calling "WN Start" for result_id. Retrying! {result_id}: {e}')
        set_status_message(crud.collection.update, task_from_db,
                           f'Collections-{task_from_db.item_type}: Error calling "WN Start" - {e}. Retrying')
        register.retry()

    if not wn_task_id:
        logger.error(f'Collections-{task_from_db.item_type}: No wn_task_id returned from WN for result_id {result_id}')
        set_status_message(crud.collection.update, task_from_db,
                           f'Collections-{task_from_db.item_type}: No wn_task_id returned from WN. Throwing exception')
        raise Exception(f'Collections-{task_from_db.item_type}: '
                        f'No wn_task_id returned from WN for result_id {result_id}')

    logger.info(f'Collections-{task_from_db.item_type}: WN {task_from_db.item_type} register process started: '
                f'wn_task_id {wn_task_id} result_id {result_id}')

    upd = {
        "wn_task_id": wn_task_id,
        "process_status": DbStatus.STARTED.value,
        "process_status_message": "Collection ticket registration started",
        "updated_at": datetime.utcnow(),
    }
    with db_context() as session:
        crud.collection.update(session, db_obj=task_from_db, obj_in=upd)

    logger.info(f'Collections-{task_from_db.item_type}: process_task exiting for result_id {result_id}')
    return result_id
