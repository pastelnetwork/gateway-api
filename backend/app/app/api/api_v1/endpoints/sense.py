from fastapi import APIRouter, Depends, HTTPException, UploadFile, WebSocket, Query

from typing import List
from sqlalchemy.orm import Session

import app.celery_tasks.sense as sense
import app.db.session as session
from app import models, crud, schemas
from app.api import deps, common
import app.utils.walletnode as wn

router = APIRouter()


# Submit a Sense OpenAPI gateway_request for the current user.
# Note: Only authenticated user with API key
@router.post("/", response_model=schemas.RequestResult, response_model_exclude_none=True)
async def process_request(
        *,
        files: List[UploadFile],
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.RequestResult:
    return await common.process_request(worker=sense, files=files, user_id=current_user.id)


# Get all Sense OpenAPI gateway_requests for the current user.
# Note: Only authenticated user with API key
@router.get("/gateway_requests", response_model=List[schemas.RequestResult], response_model_exclude_none=True)
async def get_all_requests(
        *,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.RequestResult]:
    """
    Return the status of the submitted Work
    """
    tasks = crud.sense.get_multi_by_owner(db=db, owner_id=current_user.id)
    if not tasks:
        raise HTTPException(status_code=404, detail="No gateway_requests found")
    return await common.parse_users_requests(tasks, wn.WalletNodeService.SENSE)


# Get an individual Sense gateway_request by its gateway_request_id.
# Note: Only authenticated user with API key
@router.get("/gateway_requests/{gateway_request_id}", response_model=schemas.RequestResult, response_model_exclude_none=True)
async def get_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.RequestResult:
    """
    Return the status of the submitted Work
    """
    results_in_request = crud.sense.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not results_in_request:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")
    return await common.parse_user_request(results_in_request, gateway_request_id, wn.WalletNodeService.SENSE)


# Get all Sense gateway_results for the current user.
# Note: Only authenticated user with API key
@router.get("/gateway_results", response_model=List[schemas.ResultRegistrationResult], response_model_exclude_none=True)
async def get_results(
        *,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.ResultRegistrationResult]:
    results_results = []
    results = crud.sense.get_multi_by_owner(db=db, owner_id=current_user.id)
    if not results:
        raise HTTPException(status_code=404, detail="No gateway_requests found")
    for result in results:
        result_result = await common.check_result_registration_status(result, wn.WalletNodeService.SENSE)
        results_results.append(result_result)
    return results_results


# Get an individual Sense gateway_result by its result_id.
# Note: Only authenticated user with API key
@router.get("/gateway_results/{gateway_result_id}",
            response_model=schemas.ResultRegistrationResult, response_model_exclude_none=True)
async def get_ticket(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.ResultRegistrationResult:
    result = crud.sense.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    return await common.check_result_registration_status(result, wn.WalletNodeService.SENSE)


# Get the set of underlying Sense raw_outputs_files from the corresponding gateway_request_id.
# Note: Only authenticated user with API key
@router.get("/all_raw_output_files_from_request/{gateway_request_id}")
async def get_all_raw_output_files_from_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    # TODO: Implement
    raise HTTPException(status_code=501, detail="Not implemented yet")


# Get the set of underlying Sense parsed_outputs_files from the corresponding gateway_request_id.
# Note: Only authenticated user with API key
@router.get("/all_parsed_output_files_from_request/{gateway_request_id}")
async def get_all_parsed_output_files_from_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    # TODO: Implement
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/raw_output_file/{gateway_result_id}")
async def get_raw_output_file(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.sense.get_by_result_id(db=db, result_id=gateway_result_id)  # anyone can call it
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    raw_file_bytes = await common.search_file(task_from_db=task_from_db, service=wn.WalletNodeService.SENSE)
    return await common.stream_file(file_bytes=raw_file_bytes,
                                    original_file_name=f"{task_from_db.original_file_name}.json")


@router.get("/parsed_output_file/{gateway_result_id}")
async def get_parsed_output_file(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.sense.get_by_result_id(db=db, result_id=gateway_result_id)  # anyone can call it
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    raw_file_bytes = await common.search_file(task_from_db=task_from_db, service=wn.WalletNodeService.SENSE)
    # TODO: parse file_bytes
    parsed_file_bytes = raw_file_bytes
    return await common.stream_file(file_bytes=parsed_file_bytes,
                                    original_file_name=f"{task_from_db.original_file_name}.json")


# Get the underlying Sense raw_output_file from the corresponding Sense Registration Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/raw_output_file_by_registration_ticket/{registration_ticket_txid}")
async def get_raw_output_file_by_reg_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session)
):
    task_from_db = crud.sense.get_by_reg_txid(db=db, reg_txid=registration_ticket_txid)  # anyone can call it
    if task_from_db:
        raw_file_bytes = await common.search_file(task_from_db=task_from_db, service=wn.WalletNodeService.SENSE)
        file_name = f"{task_from_db.original_file_name}.json"
    else:
        raw_file_bytes = await common.get_file_from_pastel(reg_ticket_txid=registration_ticket_txid,
                                                           service=wn.WalletNodeService.SENSE)
        file_name = f"{registration_ticket_txid}.json"
    return await common.stream_file(file_bytes=raw_file_bytes,
                                    original_file_name=file_name)


# Get the underlying Sense parsed_output_file from the corresponding Sense Registration Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/parsed_output_file_by_registration_ticket/{registration_ticket_txid}")
async def get_parsed_output_file_by_reg_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session)
):
    task_from_db = crud.sense.get_by_reg_txid(db=db, reg_txid=registration_ticket_txid)  # anyone can call it
    if task_from_db:
        raw_file_bytes = await common.search_file(task_from_db=task_from_db, service=wn.WalletNodeService.SENSE)
        file_name = f"{task_from_db.original_file_name}.json"
    else:
        raw_file_bytes = await common.get_file_from_pastel(reg_ticket_txid=registration_ticket_txid,
                                                           service=wn.WalletNodeService.SENSE)
        file_name = f"{registration_ticket_txid}.json"
    # TODO: parse file_bytes
    parsed_file_bytes = raw_file_bytes
    return await common.stream_file(file_bytes=parsed_file_bytes,
                                    original_file_name=file_name)


# Get the underlying Sense raw_output_file from the corresponding Sense Activation Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/raw_output_file_by_activation_txid/{activation_ticket_txid}")
async def get_raw_output_file_by_act_txid(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session)
):
    task_from_db = crud.sense.get_by_act_txid(db=db, act_txid=activation_ticket_txid)  # anyone can call it
    if task_from_db:
        raw_file_bytes = await common.search_file(task_from_db=task_from_db, service=wn.WalletNodeService.SENSE)
        file_name = f"{task_from_db.original_file_name}.json"
    else:
        # TODO: Implement
        # registration_ticket_txid =
        # await common.get_reg_txid_from_pastel_by_act_txid(act_ticket_txid=activation_ticket_txid)
        registration_ticket_txid = None
        raw_file_bytes = await common.get_file_from_pastel(reg_ticket_txid=registration_ticket_txid,
                                                           service=wn.WalletNodeService.SENSE)
        file_name = f"{registration_ticket_txid}.json"
    return await common.stream_file(file_bytes=raw_file_bytes,
                                    original_file_name=file_name)


# Get the underlying Sense parsed_output_file from the corresponding Sense Activation Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/raw_output_file_by_activation_txid/{activation_ticket_txid}")
async def get_raw_output_file_by_act_txid(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session)
):
    task_from_db = crud.sense.get_by_act_txid(db=db, act_txid=activation_ticket_txid)  # anyone can call it
    if task_from_db:
        raw_file_bytes = await common.search_file(task_from_db=task_from_db, service=wn.WalletNodeService.SENSE)
        file_name = f"{task_from_db.original_file_name}.json"
    else:
        # TODO: Implement
        # registration_ticket_txid =
        # await common.get_reg_txid_from_pastel_by_act_txid(act_ticket_txid=activation_ticket_txid)
        registration_ticket_txid = None
        raw_file_bytes = await common.get_file_from_pastel(reg_ticket_txid=registration_ticket_txid,
                                                           service=wn.WalletNodeService.SENSE)
        file_name = f"{registration_ticket_txid}.json"
    # TODO: parse file_bytes
    parsed_file_bytes = raw_file_bytes
    return await common.stream_file(file_bytes=parsed_file_bytes,
                                    original_file_name=file_name)


# Get a list of the Sense raw_output_files for the given pastel_id
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/raw_output_file_by_pastel_id/{pastel_id_of_user}")
async def get_raw_output_file_by_pastel_id(
        *,
        pastel_id_of_user: str,
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    # TODO: Implement
    # registration_ticket_txid = await common.get_reg_txid_from_pastel_by_paslte_id(pastel_id=pastel_id_of_user)
    registration_ticket_txid = None
    raw_file_bytes = await common.get_file_from_pastel(reg_ticket_txid=registration_ticket_txid,
                                                       service=wn.WalletNodeService.SENSE)
    file_name = f"{registration_ticket_txid}.json"
    return await common.stream_file(file_bytes=raw_file_bytes,
                                    original_file_name=file_name)


# Get a list of the Sense parsed_output_files for the given pastel_id
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/parsed_output_file_by_pastel_id/{pastel_id_of_user}")
async def parsed_raw_output_file_by_pastel_id(
        *,
        pastel_id_of_user: str,
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    # TODO: Implement
    # registration_ticket_txid = await common.get_reg_txid_from_pastel_by_paslte_id(pastel_id=pastel_id_of_user)
    registration_ticket_txid = None
    raw_file_bytes = await common.get_file_from_pastel(reg_ticket_txid=registration_ticket_txid,
                                                       service=wn.WalletNodeService.SENSE)
    file_name = f"{registration_ticket_txid}.json"
    # TODO: parse file_bytes
    parsed_file_bytes = raw_file_bytes
    return await common.stream_file(file_bytes=parsed_file_bytes,
                                    original_file_name=file_name)


# Get ALL Pastel Sense ticket from the blockchain corresponding to a particular gateway_request_id.
# Note: Only authenticated user with API key
@router.get("/pastel_tickets/{gateway_request_id}")
async def get_pastel_ticket(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    # TODO: Implement
    raise HTTPException(status_code=501, detail="Not implemented yet")


# Get Pastel Sense ticket from the blockchain corresponding to a particular gateway_result_id.
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


# Get the Pastel Ticket metadata corresponding to a Sense Registration Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/pastel_ticket_by_registration_ticket/{registration_ticket_txid}")
async def get_pastel_ticket_by_reg_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
):
    # TODO: Implement
    raise HTTPException(status_code=501, detail="Not implemented yet")


# Get the set of Pastel Sense ticket from the blockchain corresponding to a particular media_file_sha256_hash;
# Contains block number and pastel_id in case there are multiple results for the same media_file_sha256_hash
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/pastel_ticket_by_stored_file_hash/{stored_file_sha256_hash}")
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

    apikey = await deps.APIKeyAuth.get_api_key_for_cascade(db, api_key)
    current_user = await deps.APIKeyAuth.get_user_by_apikey(db, api_key)

    tickets = crud.sense.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not tickets:
        raise HTTPException(status_code=404, detail="No gateway_result or gateway_request found")

    await common.process_websocket_for_result(websocket, tickets, wn.WalletNodeService.SENSE, gateway_request_id)


@router.websocket("/status/result")
async def ticket_status(
        websocket: WebSocket,
        gateway_result_id: str = Query(default=None),
        api_key: str = Query(default=None),
        db: Session = Depends(session.get_db_session),
):
    await websocket.accept()

    await deps.APIKeyAuth.get_api_key_for_cascade(db, api_key)
    current_user = await deps.APIKeyAuth.get_user_by_apikey(db, api_key)

    tickets = [crud.sense.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)]
    if not tickets or not tickets[0]:
        raise HTTPException(status_code=404, detail="gateway_result not found")

    await common.process_websocket_for_result(websocket, tickets, wn.WalletNodeService.SENSE)
