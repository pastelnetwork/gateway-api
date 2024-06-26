from fastapi import APIRouter, Depends, HTTPException, WebSocket, Query
from typing import List
import uuid

from sqlalchemy.orm import Session

import app.db.session as session
from app import models, crud, schemas
from app.api import deps, common
import app.utils.walletnode as wn
import app.celery_tasks.collection as collection
from app.core.config import settings
from app.models import ApiKey
from app.utils.accounts import get_total_balance_by_userid

router = APIRouter()


# Submit a Sense Collection ticket register request for the current user.
# Note: Only authenticated user with API key
@router.post("/sense", response_model=schemas.CollectionRegistrationResult, response_model_exclude_none=True, operation_id="collection_create_sense_collection")
async def create_sense_collection(
        *,
        collection_name: str = Query("", description="Collection name"),
        max_collection_entries: int = Query(1, description="Maximum number of items allowed in a collection"),
        collection_item_copy_count: int = Query(1, description="Allowed number of copies for all items in a collection"),
        list_of_pastelids_of_authorized_contributors: List[str] = Query([''], description="List of pastelids of authorized contributors"),
        max_permitted_open_nsfw_score: float = Query(0.0, description="Maximum permitted open NSFW score"),
        minimum_similarity_score_to_first_entry_in_collection: float = Query(0.0, description="Minimum similarity score to first entry in collection"),
        no_of_days_to_finalize_collection: int = Query(0, description="Number of days to finalize collection"),
        royalty: float = Query(0.0, description="Royalty percentage"),
        green: bool = Query(False, description="Green"),
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.CollectionRegistrationResult:
    return await process_collection_request(
        db,
        item_type="sense", collection_name=collection_name,
        max_collection_entries=max_collection_entries, collection_item_copy_count=collection_item_copy_count,
        list_of_pastelids_of_authorized_contributors=list_of_pastelids_of_authorized_contributors,
        max_permitted_open_nsfw_score=max_permitted_open_nsfw_score,
        minimum_similarity_score_to_first_entry_in_collection=minimum_similarity_score_to_first_entry_in_collection,
        no_of_days_to_finalize_collection=no_of_days_to_finalize_collection,
        royalty=royalty, green=green, user_id=current_user.id, api_key=api_key)


# Submit an NFT Collection ticket register request for the current user.
# Note: Only authenticated user with API key
@router.post("/nft", response_model=schemas.CollectionRegistrationResult, response_model_exclude_none=True, operation_id="collection_create_nft_collection")
async def create_nft_collection(
        *,
        collection_name: str = Query("", description="Collection name"),
        max_collection_entries: int = Query(1, description="Maximum number of items allowed in a collection"),
        collection_item_copy_count: int = Query(1, description="Allowed number of copies for all items in a collection"),
        list_of_pastelids_of_authorized_contributors: List[str] = Query([], description="List of pastelids of authorized contributors"),
        max_permitted_open_nsfw_score: float = Query(0.0, description="Maximum permitted open NSFW score. Where:"
                                                                      " 0.0 means - 0% chance of NSFW content."
                                                                      " 1.0 means - 100% chance of NSFW content"),
        minimum_similarity_score_to_first_entry_in_collection: float = Query(0.0,
                                                                             description="Minimum similarity score to first entry in collection. Where: 0.0 means - 0% similarity. And 1.0 means - 100% similarity"),
        no_of_days_to_finalize_collection: int = Query(0, description="Number of days to finalize collection"),
        royalty: float = Query(0.0, description="Royalty percentage"),
        green: bool = Query(False, description="Green"),
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.CollectionRegistrationResult:
    return await process_collection_request(
        db,
        item_type="nft", collection_name=collection_name,
        max_collection_entries=max_collection_entries, collection_item_copy_count=collection_item_copy_count,
        list_of_pastelids_of_authorized_contributors=list_of_pastelids_of_authorized_contributors,
        max_permitted_open_nsfw_score=max_permitted_open_nsfw_score,
        minimum_similarity_score_to_first_entry_in_collection=minimum_similarity_score_to_first_entry_in_collection,
        no_of_days_to_finalize_collection=no_of_days_to_finalize_collection,
        royalty=royalty, green=green, user_id=current_user.id, api_key=api_key)


async def process_collection_request(
        db: Session, *,
        item_type: str, collection_name: str, max_collection_entries: int, collection_item_copy_count: int,
        list_of_pastelids_of_authorized_contributors: List,
        max_permitted_open_nsfw_score: float, minimum_similarity_score_to_first_entry_in_collection: float,
        no_of_days_to_finalize_collection: int, royalty: float, green: bool,
        user_id: int, api_key: ApiKey,
) -> schemas.CollectionRegistrationResult:
    balances = get_total_balance_by_userid(db, user_id=user_id)
    if balances and 0 < balances["balance_limit"] < balances["total_balance"] + settings.TICKET_PRICE_COLLECTION_REG:
        raise HTTPException(status_code=400, detail=f'Balance [{balances["total_balance"]}] is over set limit '
                                                    f'[{balances["balance_limit"]}] to pay Ticket Fee '
                                                    f'{settings.TICKET_PRICE_COLLECTION_REG}. {balances}')

    if max_permitted_open_nsfw_score < 0 or max_permitted_open_nsfw_score >= 1:
        raise HTTPException(status_code=400, detail="max_permitted_open_nsfw_score must be between 0 and 1")
    if (minimum_similarity_score_to_first_entry_in_collection < 0 or
            minimum_similarity_score_to_first_entry_in_collection >= 1):
        raise HTTPException(status_code=400, detail="minimum_similarity_score_to_first_entry_in_collection "
                                                    "must be between 0 and 1")
    if royalty < 0 or royalty >= 100:
        raise HTTPException(status_code=400, detail="royalty must be between 0 and 100")
    if no_of_days_to_finalize_collection < 1 or no_of_days_to_finalize_collection > 7:
        raise HTTPException(status_code=400, detail="no_of_days_to_finalize_collection must be between 1 and 7")
    if max_collection_entries < 1:
        raise HTTPException(status_code=400, detail="max_collection_entries must be greater than 0")
    if collection_item_copy_count < 1:
        raise HTTPException(status_code=400, detail="collection_item_copy_count must be greater than 0")

    collection_id = str(uuid.uuid4())
    _ = (
        collection.register.s(collection_id, user_id, api_key,
                              item_type, collection_name, max_collection_entries, collection_item_copy_count,
                              list_of_pastelids_of_authorized_contributors,
                              max_permitted_open_nsfw_score, minimum_similarity_score_to_first_entry_in_collection,
                              no_of_days_to_finalize_collection, royalty, green) |
        collection.process.s()
    ).apply_async()

    reg_result = await common.make_pending_result(None, None, None, collection_id)
    return await result_to_collection(reg_result)


# Get all Sense Collection ticket register for the current user.
# Note: Only authenticated user with API key
@router.get("/sense/collections", response_model=List[schemas.CollectionRegistrationResult], response_model_exclude_none=True, operation_id="collection_get_all_sense_collections")
async def get_all_sense_collections(
        *,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.CollectionRegistrationResult]:
    task_results = []
    tasks_from_db = crud.collection.get_multi_by_owner_by_type(db=db, owner_id=current_user.id, item_type="sense")
    if not tasks_from_db:
        raise HTTPException(status_code=200, detail="No gateway_requests found")
    for task_from_db in tasks_from_db:
        task_result = await common.check_result_registration_status(task_from_db, wn.WalletNodeService.COLLECTION)
        task_results.append(await result_to_collection(task_result))
    return task_results


# Get an individual NFT gateway_result by its result_id.
# Note: Only authenticated user with API key
@router.get("/sense/collections/{collection_id}", response_model=schemas.CollectionRegistrationResult, response_model_exclude_none=True, operation_id="collection_get_sense_collections_from_collection_id")
async def get_sense_collections_from_collection_id(
        *,
        collection_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.CollectionRegistrationResult:
    task_from_db = crud.collection.get_by_result_id_and_owner(db=db, result_id=collection_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    if task_from_db.item_type != "sense":
        raise HTTPException(status_code=404, detail="gateway_result not found")
    return await result_to_collection(await common.check_result_registration_status(task_from_db, wn.WalletNodeService.COLLECTION))


# Get all NFT Collection ticket register for the current user.
# Note: Only authenticated user with API key
@router.get("/nft/collections", response_model=List[schemas.CollectionRegistrationResult], response_model_exclude_none=True, operation_id="collection_get_all_nft_collections")
async def get_all_nft_collections(
        *,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.CollectionRegistrationResult]:
    task_results = []
    tasks_from_db = crud.collection.get_multi_by_owner_by_type(db=db, owner_id=current_user.id, item_type="nft")
    if not tasks_from_db:
        raise HTTPException(status_code=200, detail="No gateway_requests found")
    for task_from_db in tasks_from_db:
        task_result = await common.check_result_registration_status(task_from_db, wn.WalletNodeService.COLLECTION)
        task_results.append(await result_to_collection(task_result))
    return task_results


# Get an individual NFT gateway_result by its result_id.
# Note: Only authenticated user with API key
@router.get("/nft/collections/{collection_id}", response_model=schemas.CollectionRegistrationResult, response_model_exclude_none=True, operation_id="collection_get_nft_collections_from_collection_id")
async def get_nft_collections_from_collection_id(
        *,
        collection_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.CollectionRegistrationResult:
    task_from_db = crud.collection.get_by_result_id_and_owner(db=db, result_id=collection_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    if task_from_db.item_type != "nft":
        raise HTTPException(status_code=404, detail="gateway_result not found")
    return await result_to_collection(await common.check_result_registration_status(task_from_db, wn.WalletNodeService.COLLECTION))


async def result_to_collection(result):
    coll = schemas.CollectionRegistrationResult(**result.dict())
    coll.collection_id = result.result_id
    return coll


@router.websocket("/status/collection")
async def result_status(
        websocket: WebSocket,
        collection_id: str = Query(default=None),
        api_key: str = Query(default=None),
        db: Session = Depends(session.get_db_session),
):
    await websocket.accept()

    await deps.APIKeyAuth.get_api_key_for_sense(db, api_key)
    current_user = await deps.APIKeyAuth.get_user_by_apikey(db, api_key)

    tasks_in_db = [crud.collection.get_by_result_id_and_owner(db=db, result_id=collection_id, owner_id=current_user.id)]
    await common.process_websocket_for_result(websocket, tasks_in_db, wn.WalletNodeService.COLLECTION)
