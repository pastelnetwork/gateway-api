from fastapi import APIRouter, Depends, HTTPException, UploadFile, WebSocket, Query

from typing import List
from sqlalchemy.orm import Session
from datetime import datetime

import app.celery_tasks.cascade as cascade
import app.db.session as session
from app.api import deps, common
from app import models, crud, schemas
import app.utils.walletnode as wn

router = APIRouter()


# Submit a Cascade OpenAPI gateway_request for the current user
# Note: Only authenticated user with API key
@router.post("/", response_model=schemas.RequestResult, response_model_exclude_none=True)
async def process_request(
        *,
        files: List[UploadFile],
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.RequestResult:
    return await common.process_request(worker=cascade, files=files, user_id=current_user.id)


# Get all Cascade OpenAPI gateway_requests for the current user
# Note: Only authenticated user with API key
@router.get("/gateway_requests", response_model=List[schemas.RequestResult], response_model_exclude_none=True)
async def get_all_requests(
        *,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.RequestResult]:
    """
    Return the status of the submitted request
    """
    tasks_in_db = crud.cascade.get_multi_by_owner(db=db, owner_id=current_user.id)
    if not tasks_in_db:
        raise HTTPException(status_code=404, detail="No gateway_requests found")
    return await common.parse_users_requests(tasks_in_db, wn.WalletNodeService.CASCADE)


# Get an individual Cascade gateway_request by its gateway_request_id
# Note: Only authenticated user with API key
@router.get("/gateway_requests/{gateway_request_id}", response_model=schemas.RequestResult, response_model_exclude_none=True)
async def get_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.RequestResult:
    """
    Return the status of the submitted Work
    """
    results_in_request = crud.cascade.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not results_in_request:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")
    return await common.parse_user_request(results_in_request, gateway_request_id, wn.WalletNodeService.CASCADE)


# Get all Cascade gateway_results for the current user
# Note: Only authenticated user with API key
@router.get("/gateway_results", response_model=List[schemas.ResultRegistrationResult], response_model_exclude_none=True)
async def get_results(
        *,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.ResultRegistrationResult]:
    results_results = []
    results = crud.cascade.get_multi_by_owner(db=db, owner_id=current_user.id)
    if not results:
        raise HTTPException(status_code=404, detail="No gateway_requests found")
    for result in results:
        result_result = await common.check_result_registration_status(result, wn.WalletNodeService.CASCADE)
        results_results.append(result_result)
    return results_results


# Get an individual Cascade gateway_result by its result_id
# Note: Only authenticated user with API key
@router.get("/gateway_results/{gateway_result_id}",
            response_model=schemas.ResultRegistrationResult, response_model_exclude_none=True)
async def get_ticket(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.ResultRegistrationResult:
    result = crud.cascade.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    return await common.check_result_registration_status(result, wn.WalletNodeService.CASCADE)


# Get ALL underlying Cascade stored_files from the corresponding gateway_request_id
# Note: Only authenticated user with API key
@router.get("/all_files_from_request/{gateway_request_id}")
async def get_all_files_from_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    # TODO: Implement
    raise HTTPException(status_code=501, detail="Not implemented yet")


# Get the underlying Cascade stored_file from the corresponding gateway_result_id
# Note: Only authenticated user with API key
@router.get("/stored_file/{gateway_result_id}")
async def get_stored_file(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    result = crud.cascade.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    file_bytes = await common.search_file(result=result, service=wn.WalletNodeService.CASCADE)
    return await common.stream_file(file_bytes=file_bytes,
                                    original_file_name=f"{result.original_file_name}")


# Get the underlying Cascade stored_file from the corresponding Cascade Registration Ticket Transaction ID
# Only succeeds if:
# 1) the user owns the Cascade file (authenticated user with API key)
#    - in the context of OpanAPI it means that file was registered by that instance of OpenAPI with its PastelID
# 2) or the make_publicly_accessible flag is set to True for that Cascade operation.
@router.get("/stored_file_from_registration_ticket/{registration_ticket_txid}")
async def get_file_from_reg_txid(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    result = crud.cascade.get_by_reg_txid_and_owner(db=db, owner_id=current_user.id, reg_txid=registration_ticket_txid)
    if not result:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    file_bytes = await common.search_file(result=result, service=wn.WalletNodeService.CASCADE)
    return await common.stream_file(file_bytes=file_bytes,
                                    original_file_name=f"{result.original_file_name}")


@router.get("/stored_file_from_activation_ticket/{activation_ticket_txid}")
async def get_file_from_act_txid(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    result = crud.cascade.get_by_act_txid_and_owner(db=db, owner_id=current_user.id, act_txid=activation_ticket_txid)
    if not result:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    file_bytes = await common.search_file(result=result, service=wn.WalletNodeService.CASCADE)
    return await common.stream_file(file_bytes=file_bytes,
                                    original_file_name=f"{result.original_file_name}")


# Get the Pastel Cascade ticket from the blockchain corresponding to a particular gateway_request_id
# Note: Only authenticated user with API key
@router.get("/pastel_ticket/{gateway_result_id}")
async def get_pastel_ticket(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    # TODO: Implement
    raise HTTPException(status_code=501, detail="Not implemented yet")


# Get the Pastel Cascade ticket from the blockchain from a Cascade Registration Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/pastel_ticket_from_registration_ticket/{registration_ticket_txid}")
async def get_pastel_ticket_from_reg_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
):
    # TODO: Implement
    raise HTTPException(status_code=501, detail="Not implemented yet")


# Get the set of Pastel Cascade tickets from the blockchain corresponding to a particular stored_file_sha256_hash.
# Contains pastel_block_number and pastel_id in case there are multiple results for the same stored_file_sha256_hash
# Note: Available to any user
@router.get("/pastel_ticket_from_stored_file_hash/{stored_file_sha256_hash}")
async def get_pastel_ticket_data_from_stored_file_hash(
        *,
        stored_file_sha256_hash: str,
        db: Session = Depends(session.get_db_session),
):
    # TODO: Implement
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.websocket("/status/request")
async def request_status(
        websocket: WebSocket,
        gateway_request_id: str = Query(default=None),
        api_key: str = Query(default=None),
        db: Session = Depends(session.get_db_session),
):
    await websocket.accept()

    await deps.APIKeyAuth.get_api_key_for_cascade(db, api_key)
    current_user = await deps.APIKeyAuth.get_user_by_apikey(db, api_key)

    results = crud.cascade.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not results:
        raise HTTPException(status_code=404, detail="No gateway_result or gateway_request found")

    await common.process_websocket_for_result(websocket, results, wn.WalletNodeService.CASCADE, gateway_request_id)


@router.websocket("/status/result")
async def status_of_result(
        websocket: WebSocket,
        gateway_result_id: str = Query(default=None),
        api_key: str = Query(default=None),
        db: Session = Depends(session.get_db_session),
):
    await websocket.accept()

    await deps.APIKeyAuth.get_api_key_for_cascade(db, api_key)
    current_user = await deps.APIKeyAuth.get_user_by_apikey(db, api_key)

    results = [crud.cascade.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)]
    if not results or not results[0]:
        raise HTTPException(status_code=404, detail="gateway_result not found")

    await common.process_websocket_for_result(websocket, results, wn.WalletNodeService.CASCADE)


@router.get("/result/transfer_pastel_ticket")
async def transfer_pastel_ticket_to_another_pastelid(
        *,
        gateway_result_id: str = Query(),
        pastel_id: str = Query(),
        db: Session = Depends(session.get_db_session),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    result = crud.cascade.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="gateway_result not found")

    offer_ticket = await common.create_offer_ticket(result, pastel_id, wn.WalletNodeService.CASCADE)

    if offer_ticket and 'txid' in offer_ticket and offer_ticket['txid']:
        upd = {"offer_ticket_txid": offer_ticket['txid'],
               "offer_ticket_intended_rcpt_pastel_id": pastel_id,
               "updated_at": datetime.utcnow()}
        crud.cascade.update(db=db, db_obj=result, obj_in=upd)

    return offer_ticket
