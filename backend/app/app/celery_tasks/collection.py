from typing import List

from celery import shared_task
from celery.utils.log import get_task_logger

from requests import RequestException
import json
from datetime import datetime

from app.core.status import DbStatus
from .pastel_tasks import PastelAPITask, PastelAPIException
from app import crud, schemas
from app.utils.walletnode import WalletNodeService, WalletnodeException
from app.utils import walletnode as wn, pasteld as psl
from app.utils.pasteld import PasteldException
from app.core.config import settings
from app.db.session import db_context
from app.utils.authentication import send_alert_email

logger = get_task_logger(__name__)

COLLECTION_TICKET_FEE = 1000


# NEW->STARTED->REGISTERED->DONE
#               ERROR->RESTARTED->STARTED->REGISTERED->DONE

class CollectionsAPITask(PastelAPITask):
    def on_success(self, retval, result_id, args, kwargs):
        PastelAPITask.on_success_base(args, crud.collection.get_by_result_id, crud.collection.update)

    def on_failure(self, exc, result_id, args, kwargs, einfo):
        PastelAPITask.on_failure_base(args, crud.collection.get_by_result_id, crud.collection.update)

    def get_request_form(self, task_from_db) -> str:
        address_list = psl.call("listaddressamounts", [])
        spendable_address = None
        if address_list:
            for spendable_address, value in address_list.items():
                if value > COLLECTION_TICKET_FEE:
                    break

        if not spendable_address:
            logger.error(f"Collection-{task_from_db.item_type}: No spendable address "
                         f"found for amount > {COLLECTION_TICKET_FEE}. [Result ID: {task_from_db.result_id}]")
            send_alert_email(f"No spendable address found to pay Collection fee in the amount > {COLLECTION_TICKET_FEE}")
            raise PastelAPIException(f"No spendable address found for amount > {COLLECTION_TICKET_FEE}")

        return json.dumps(
            {
                "app_pastelid": settings.PASTEL_ID,
                "collection_item_copy_count": task_from_db.collection_item_copy_count,
                "collection_name": task_from_db.collection_name,
                "green": task_from_db.green,
                "item_type": task_from_db.item_type,
                "list_of_pastelids_of_authorized_contributors": task_from_db.authorized_pastel_ids,
                "max_collection_entries": task_from_db.max_collection_entries,
                "max_permitted_open_nsfw_score": task_from_db.max_permitted_open_nsfw_score,
                "minimum_similarity_score_to_first_entry_in_collection": task_from_db.minimum_similarity_score_to_first_entry_in_collection,
                "no_of_days_to_finalize_collection": task_from_db.no_of_days_to_finalize_collection,
                "royalty": task_from_db.royalty,
                "spendable_address": spendable_address
            })

    def check_specific_conditions(self, task_from_db) -> (bool, str):
        pass

@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=5,
             name='collection:register', base=CollectionsAPITask)
def register(self, result_id, user_id,
             item_type: str, collection_name: str, max_collection_entries: int, collection_item_copy_count: int,
             authorized_pastel_ids: List,
             max_permitted_open_nsfw_score: float, minimum_similarity_score_to_first_entry_in_collection: float,
             no_of_days_to_finalize_collection: int, royalty: float, green: bool) -> str:
    logger.debug(f'Collection-{item_type}: Register collection in the Pastel Network... [Result ID: {result_id}]')

    with db_context() as session:
        task_in_db = crud.collection.get_by_result_id(session, result_id=result_id)

    if task_in_db:
        logger.warn(f'Collection-{item_type}: Task is already in the DB. Status is {task_in_db.process_status}... '
                    f'[Result ID: {result_id}]')
        return result_id

    logger.info(f'Collection-{item_type} New file - adding record to DB... [Result ID: {result_id}]')

    height = psl.call("getblockcount", [])
    logger.debug(f'Collection-{item_type}: Ticket will be created at height {height} [Result ID: {result_id}]')

    new_task = schemas.CollectionCreate(
        result_id=result_id,
        item_type=item_type,
        pastel_id=settings.PASTEL_ID,
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

    logger.debug(f'Collection-{item_type}: New record created. process_task exiting. [Result ID: {result_id}]')
    return result_id

@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=5,
             name='collection:process', base=CollectionsAPITask)
def process(self, result_id) -> str:
    logger.debug(f'Collection: Register file in the Pastel Network... [Result ID: {result_id}]')

    with db_context() as session:
        task_from_db = crud.collection.get_by_result_id(session, result_id=result_id)

    if not task_from_db:
        logger.error(f'Collection: No task found for result_id {result_id}')
        raise PastelAPIException(f'Collection: No task found for result_id {result_id}')

    if task_from_db.process_status != DbStatus.RESTARTED.value and task_from_db.process_status != DbStatus.NEW.value:
        logger.warn(f'Collection-{task_from_db.item_type}: process: Wrong task state - "{task_from_db.process_status}", '
                    f'Should be {DbStatus.RESTARTED.value} OR {DbStatus.NEW.value}... [Result ID: {result_id}]')
        return result_id

    form = self.get_request_form(task_from_db)

    logger.info(f'Collection-{task_from_db.item_type}: Calling WN to start collection ticket registration [Result ID: {result_id}]')
    wn_task_id = ""
    try:
        wn_task_id = wn.call(True,
                             WalletNodeService.COLLECTION,
                             'register',
                             form,
                             [],
                             {
                                 'Authorization': settings.PASTEL_ID_PASSPHRASE,
                                 'Content-Type': 'application/json'
                             },
                             "task_id", "")
    except Exception as e:
        logger.error(f'Collections-{task_from_db.item_type}: Error calling "WN Start" for result_id. Retrying! {result_id}: {e}')
        register.retry()

    if not wn_task_id:
        logger.error(f'Collections-{task_from_db.item_type}: No wn_task_id returned from WN for result_id {result_id}')
        raise Exception(f'Collections-{task_from_db.item_type}: No wn_task_id returned from WN for result_id {result_id}')

    logger.info(f'Collections-{task_from_db.item_type}: WN {task_from_db.item_type} register process started: '
                f'wn_task_id {wn_task_id} result_id {result_id}')

    upd = {
        "wn_task_id": wn_task_id,
        "process_status": DbStatus.STARTED.value,
        "updated_at": datetime.utcnow(),
    }
    with db_context() as session:
        crud.collection.update(session, db_obj=task_from_db, obj_in=upd)

    logger.debug(f'Collections-{task_from_db.item_type}: process_task exiting for result_id {result_id}')
    return result_id

