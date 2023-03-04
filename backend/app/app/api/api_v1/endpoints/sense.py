from fastapi import APIRouter, Depends, HTTPException, UploadFile, WebSocket, Query
from typing import List
from sqlalchemy.orm import Session
from starlette.responses import Response

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
    tasks_from_db = crud.sense.get_multi_by_owner(db=db, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_requests found")
    return await common.parse_users_requests(tasks_from_db, wn.WalletNodeService.SENSE)


# Get an individual Sense gateway_request by its gateway_request_id.
# Note: Only authenticated user with API key
@router.get("/gateway_requests/{gateway_request_id}", response_model=schemas.RequestResult,
            response_model_exclude_none=True)
async def get_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.RequestResult:
    tasks_from_db = crud.sense.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")
    return await common.parse_user_request(tasks_from_db, gateway_request_id, wn.WalletNodeService.SENSE)


# Get all Sense gateway_results for the current user.
# Note: Only authenticated user with API key
@router.get("/gateway_results", response_model=List[schemas.ResultRegistrationResult], response_model_exclude_none=True)
async def get_results(
        *,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.ResultRegistrationResult]:
    task_results = []
    tasks_from_db = crud.sense.get_multi_by_owner(db=db, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_requests found")
    for task_from_db in tasks_from_db:
        task_result = await common.check_result_registration_status(task_from_db, wn.WalletNodeService.SENSE)
        task_results.append(task_result)
    return task_results


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
    task_from_db = crud.sense.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    return await common.check_result_registration_status(task_from_db, wn.WalletNodeService.SENSE)


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
    tasks_from_db = crud.sense.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")
    return await common.get_all_sense_data_from_request(db=db,
                                                        tasks_from_db=tasks_from_db,
                                                        gateway_request_id=gateway_request_id)


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
    tasks_from_db = crud.sense.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")
    return await common.get_all_sense_data_from_request(db=db,
                                                        tasks_from_db=tasks_from_db,
                                                        gateway_request_id=gateway_request_id,
                                                        parse=True)


# Get the underlying Sense raw_outputs_file from the corresponding gateway_result_id.
# Note: Only authenticated user with API key
@router.get("/raw_output_file/{gateway_result_id}")
async def get_raw_output_file(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> Response:
    task_from_db = crud.sense.get_by_result_id(db=db, result_id=gateway_result_id)  # anyone can call it
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    json_bytes = await common.search_gateway_file(db=db,
                                                  task_from_db=task_from_db,
                                                  service=wn.WalletNodeService.SENSE,
                                                  update_task_in_db_func=crud.sense.update)
    return Response(content=json_bytes, media_type="application/json")


# Get the underlying Sense parsed_outputs_file from the corresponding gateway_result_id.
# Note: Only authenticated user with API key
@router.get("/parsed_output_file/{gateway_result_id}")
async def get_parsed_output_file(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> Response:
    task_from_db = crud.sense.get_by_result_id(db=db, result_id=gateway_result_id)  # anyone can call it
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    raw_file_bytes = await common.search_gateway_file(db=db,
                                                      task_from_db=task_from_db,
                                                      service=wn.WalletNodeService.SENSE,
                                                      update_task_in_db_func=crud.sense.update)
    parsed_file_bytes = await common.parse_sense_data(raw_file_bytes)
    return Response(content=parsed_file_bytes, media_type="application/json")


# Get the underlying Sense raw_output_file from the corresponding Sense Registration Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/raw_output_file_by_registration_ticket/{registration_ticket_txid}")
async def get_raw_output_file_by_registration_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session)
) -> Response:
    task_from_db = crud.sense.get_by_reg_txid(db=db, reg_txid=registration_ticket_txid)  # anyone can call it
    if task_from_db:
        raw_file_bytes = await common.search_gateway_file(db=db,
                                                          task_from_db=task_from_db,
                                                          service=wn.WalletNodeService.SENSE,
                                                          update_task_in_db_func=crud.sense.update)
    else:
        raw_file_bytes = await common.search_pastel_file(reg_ticket_txid=registration_ticket_txid,
                                                         service=wn.WalletNodeService.SENSE)
    return Response(content=raw_file_bytes, media_type="application/json")


# Get the underlying Sense parsed_output_file from the corresponding Sense Registration Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/parsed_output_file_by_registration_ticket/{registration_ticket_txid}")
async def get_parsed_output_file_by_registration_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session)
) -> Response:
    task_from_db = crud.sense.get_by_reg_txid(db=db, reg_txid=registration_ticket_txid)  # anyone can call it
    if task_from_db:
        raw_file_bytes = await common.search_gateway_file(db=db,
                                                          task_from_db=task_from_db,
                                                          service=wn.WalletNodeService.SENSE,
                                                          update_task_in_db_func=crud.sense.update)
    else:
        raw_file_bytes = await common.search_pastel_file(reg_ticket_txid=registration_ticket_txid,
                                                         service=wn.WalletNodeService.SENSE)
    parsed_file_bytes = await common.parse_sense_data(raw_file_bytes)
    return Response(content=parsed_file_bytes, media_type="application/json")


# Get the underlying Sense raw_output_file from the corresponding Sense Activation Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/raw_output_file_by_activation_ticket/{activation_ticket_txid}")
async def get_raw_output_file_by_activation_ticket(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session)
) -> Response:
    task_from_db = crud.sense.get_by_act_txid(db=db, act_txid=activation_ticket_txid)  # anyone can call it
    if task_from_db:
        raw_file_bytes = await common.search_gateway_file(db=db,
                                                          task_from_db=task_from_db,
                                                          service=wn.WalletNodeService.SENSE,
                                                          update_task_in_db_func=crud.sense.update)
    else:
        registration_ticket_txid = await common.get_reg_txid_by_act_txid(activation_ticket_txid)
        raw_file_bytes = await common.search_pastel_file(reg_ticket_txid=registration_ticket_txid,
                                                         service=wn.WalletNodeService.SENSE)
    return Response(content=raw_file_bytes, media_type="application/json")


# Get the underlying Sense parsed_output_file from the corresponding Sense Activation Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/parsed_output_file_by_activation_txid/{activation_ticket_txid}")
async def parsed_raw_output_file_by_act_txid(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session)
) -> Response:
    task_from_db = crud.sense.get_by_act_txid(db=db, act_txid=activation_ticket_txid)  # anyone can call it
    if task_from_db:
        raw_file_bytes = await common.search_gateway_file(db=db,
                                                          task_from_db=task_from_db,
                                                          service=wn.WalletNodeService.SENSE,
                                                          update_task_in_db_func=crud.sense.update)
    else:
        registration_ticket_txid = await common.get_reg_txid_by_act_txid(activation_ticket_txid)
        raw_file_bytes = await common.search_pastel_file(reg_ticket_txid=registration_ticket_txid,
                                                         service=wn.WalletNodeService.SENSE)
    parsed_file_bytes = await common.parse_sense_data(raw_file_bytes)
    return Response(content=parsed_file_bytes, media_type="application/json")


# Get a list of the Sense raw_output_files for the given pastel_id
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/raw_output_file_by_pastel_id/{pastel_id_of_user}")
async def get_raw_output_file_by_pastel_id(
        *,
        pastel_id_of_user: str,
):
    return await common.get_all_sense_data_for_pastelid(pastel_id=pastel_id_of_user)


# Get a list of the Sense parsed_output_files for the given pastel_id
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/parsed_output_file_by_pastel_id/{pastel_id_of_user}")
async def parsed_raw_output_file_by_pastel_id(
        *,
        pastel_id_of_user: str,
):
    return await common.get_all_sense_data_for_pastelid(pastel_id=pastel_id_of_user, parse=True)


# Get ALL Pastel Sense registration tickets from the blockchain corresponding to a particular gateway_request_id.
# Note: Only authenticated user with API key
@router.get("/pastel_registration_tickets/{gateway_request_id}")
async def get_all_pastel_sense_registration_tickets_from_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    tasks_from_db = crud.sense.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")

    return await common.get_all_reg_ticket_from_request(gateway_request_id=gateway_request_id,
                                                        tasks_from_db=tasks_from_db,
                                                        service_type="sense",
                                                        service=wn.WalletNodeService.SENSE)


# Get Pastel Sense registration ticket from the blockchain corresponding to a particular gateway_result_id.
# Note: Only authenticated user with API key
@router.get("/pastel_registration_ticket/{gateway_result_id}")
async def get_pastel_sense_registration_ticket_by_result_id(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.sense.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")

    return await common.get_registration_action_ticket(task_from_db.reg_ticket_txid, wn.WalletNodeService.SENSE)


# Get Pastel Sense activation ticket from the blockchain corresponding to a particular gateway_result_id.
# Note: Only authenticated user with API key
@router.get("/pastel_activation_ticket/{gateway_result_id}")
async def get_pastel_sense_activation_ticket_by_result_id(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.sense.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")

    return await common.get_activation_action_ticket(task_from_db.act_ticket_txid, wn.WalletNodeService.SENSE)


# Get the Pastel Sense Registration Ticket from the blockchain from its Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/pastel_registration_ticket_from_txid/{registration_ticket_txid}")
async def get_pastel_registration_ticket_by_its_txid(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
):
    return await common.get_registration_action_ticket(registration_ticket_txid, wn.WalletNodeService.SENSE)


# Get the Pastel Sense Activation Ticket from the blockchain from its Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/pastel_activation_ticket_from_txid/{activation_ticket_txid}")
async def get_pastel_activation_ticket_by_its_txid(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
):
    return await common.get_activation_action_ticket(activation_ticket_txid, wn.WalletNodeService.SENSE)


# Get the set of Pastel Sense ticket from the blockchain corresponding to a particular media_file_sha256_hash;
# Contains block number and pastel_id in case there are multiple results for the same media_file_sha256_hash
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/pastel_ticket_by_media_file_hash/{media_file_sha256_hash}")
async def get_pastel_ticket_data_from_media_file_hash(
        *,
        media_file_sha256_hash: str,
        db: Session = Depends(session.get_db_session),
):
    # TODO: Implement get_pastel_ticket_data_from_media_file_hash
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.websocket("/status/request")
async def request_status(
        websocket: WebSocket,
        gateway_request_id: str = Query(default=None),
        api_key: str = Query(default=None),
        db: Session = Depends(session.get_db_session),
):
    await websocket.accept()

    apikey = await deps.APIKeyAuth.get_api_key_for_sense(db, api_key)
    current_user = await deps.APIKeyAuth.get_user_by_apikey(db, api_key)

    tasks_in_db = crud.sense.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    await common.process_websocket_for_result(websocket, tasks_in_db, wn.WalletNodeService.SENSE, gateway_request_id)


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

    tasks_in_db = [crud.sense.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)]
    await common.process_websocket_for_result(websocket, tasks_in_db, wn.WalletNodeService.SENSE)
