from fastapi import APIRouter, Depends, HTTPException, UploadFile, WebSocket, Query
import zipfile
import io
from typing import List, Optional
from sqlalchemy.orm import Session

import app.celery_tasks.cascade as cascade
import app.db.session as session
from app.api import deps, common
from app import models, crud, schemas
import app.utils.walletnode as wn
from app.utils.ipfs_tools import search_file_locally_or_in_ipfs

router = APIRouter()


# Submit a Cascade OpenAPI gateway_request for the current user
# Note: Only authenticated user with API key
@router.post("", response_model=schemas.RequestResult, response_model_exclude_none=True)
async def process_request(
        *,
        files: List[UploadFile],
        make_publicly_accessible: bool = Query(True, description="Make the file publicly accessible"),
        after_activation_transfer_to_pastelid: Optional[str] = Query(None, description="PastelID to transfer the NFT to after activation, if any"),
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.RequestResult:
    return await common.process_action_request(db=db, worker=cascade,
                                               files=files,
                                               make_publicly_accessible=make_publicly_accessible,
                                               collection_act_txid=None,
                                               open_api_group_id=None,
                                               after_activation_transfer_to_pastelid=after_activation_transfer_to_pastelid,
                                               user_id=current_user.id,
                                               service=wn.WalletNodeService.CASCADE)


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
    tasks_from_db = crud.cascade.get_multi_by_owner(db=db, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_requests found")
    return await common.parse_users_requests(tasks_from_db, wn.WalletNodeService.CASCADE)


# Get an individual Cascade gateway_request by its gateway_request_id
# Note: Only authenticated user with API key
@router.get("/gateway_requests/{gateway_request_id}", response_model=schemas.RequestResult, response_model_exclude_none=True)
async def get_request_by_request_id(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.RequestResult:
    """
    Return the status of the submitted Work
    """
    tasks_from_db = crud.cascade.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")
    return await common.parse_user_request(tasks_from_db, gateway_request_id, wn.WalletNodeService.CASCADE)


# Get all Cascade gateway_results for the current user
# Note: Only authenticated user with API key
@router.get("/gateway_results", response_model=List[schemas.ResultRegistrationResult], response_model_exclude_none=True)
async def get_all_results(
        *,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.ResultRegistrationResult]:
    tasks_results = []
    tasks_from_db = crud.cascade.get_multi_by_owner(db=db, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_requests found")
    for task_from_db in tasks_from_db:
        task_result = await common.check_result_registration_status(task_from_db, wn.WalletNodeService.CASCADE)
        tasks_results.append(task_result)
    return tasks_results


# Get an individual Cascade gateway_result by its result_id
# Note: Only authenticated user with API key
@router.get("/gateway_results/{gateway_result_id}",
            response_model=schemas.ResultRegistrationResult, response_model_exclude_none=True)
async def get_result_by_result_id(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.ResultRegistrationResult:
    task_from_db = crud.cascade.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    return await common.check_result_registration_status(task_from_db, wn.WalletNodeService.CASCADE)


# Get ALL underlying Cascade stored_files from the corresponding gateway_request_id
# Note: Only authenticated user with API key
@router.get("/all_files_from_request/{gateway_request_id}")
async def get_all_files_from_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    tasks_from_db = crud.cascade.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for task_from_db in tasks_from_db:
            file_bytes = await common.search_gateway_file(db=db,
                                                          task_from_db=task_from_db,
                                                          service=wn.WalletNodeService.CASCADE,
                                                          update_task_in_db_func=crud.cascade.update)
            zip_file.writestr(task_from_db.original_file_name, file_bytes)

    return await common.stream_file(file_bytes=zip_buffer.getvalue(),
                                    original_file_name=f"{gateway_request_id}.zip",
                                    content_type="application/zip")


# Get the underlying Cascade stored_file from the corresponding gateway_result_id
# Note: Only authenticated user with API key
@router.get("/stored_file/{gateway_result_id}")
async def get_stored_file_by_result_id(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.cascade.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    file_bytes = await common.search_gateway_file(db=db,
                                                  task_from_db=task_from_db,
                                                  service=wn.WalletNodeService.CASCADE,
                                                  update_task_in_db_func=crud.cascade.update)
    return await common.stream_file(file_bytes=file_bytes,
                                    original_file_name=f"{task_from_db.original_file_name}")


# Get the underlying Cascade stored_file from the corresponding Cascade Registration Ticket Transaction ID
# Only succeeds if the user owns the Cascade file (authenticated user with API key)
#    - in the context of Gateway it means that file was registered by that instance of Gateway with its PastelID
@router.get("/stored_file_from_registration_ticket/{registration_ticket_txid}")
async def get_stored_file_by_registration_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.cascade.get_by_reg_txid_and_owner(db=db, owner_id=current_user.id,
                                                          reg_txid=registration_ticket_txid)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    file_bytes = await common.search_gateway_file(db=db,
                                                  task_from_db=task_from_db,
                                                  service=wn.WalletNodeService.CASCADE,
                                                  update_task_in_db_func=crud.cascade.update)
    return await common.stream_file(file_bytes=file_bytes,
                                    original_file_name=f"{task_from_db.original_file_name}")


# Get the underlying Cascade stored_file from the corresponding Cascade Activation Ticket Transaction ID
# Only succeeds if the user owns the Cascade file (authenticated user with API key)
#    - in the context of Gateway it means that file was registered by that instance of Gateway with its PastelID
@router.get("/stored_file_from_activation_ticket/{activation_ticket_txid}")
async def get_stored_file_by_activation_ticket(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.cascade.get_by_act_txid_and_owner(db=db, owner_id=current_user.id,
                                                          act_txid=activation_ticket_txid)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    file_bytes = await common.search_gateway_file(db=db,
                                                  task_from_db=task_from_db,
                                                  service=wn.WalletNodeService.CASCADE,
                                                  update_task_in_db_func=crud.cascade.update)
    return await common.stream_file(file_bytes=file_bytes,
                                    original_file_name=f"{task_from_db.original_file_name}")


# Get the Public Cascade stored_file from the corresponding Cascade Registration Ticket Transaction ID
# Only succeeds if the file was made Public during registration (by setting flag make_publicly_accessible)
# Note: Available to any user
@router.get("/public_stored_file_from_registration_ticket/{registration_ticket_txid}")
async def get_public_stored_file_by_registration_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
):
    return await common.get_public_file(db=db,
                                  ticket_type="cascade",
                                  registration_ticket_txid=registration_ticket_txid,
                                  wn_service=wn.WalletNodeService.CASCADE)


# Get the ORIGINAL uploaded from the corresponding gateway_result_id
# Note: Only authenticated user with API key
@router.get("/originally_submitted_file/{gateway_result_id}")
async def get_originally_submitted_file_by_result_id(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.cascade.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    try:
        file_bytes = await search_file_locally_or_in_ipfs(task_from_db.original_file_local_path,
                                                          task_from_db.original_file_ipfs_link)
    except Exception as e:
        raise HTTPException(status_code=404, detail="File not found")

    return await common.stream_file(file_bytes=file_bytes.read(),
                                    original_file_name=f"{task_from_db.original_file_name}")


# Get ALL Pastel cascade registration tickets from the blockchain corresponding to a particular gateway_request_id.
# Note: Only authenticated user with API key
@router.get("/pastel_registration_tickets/{gateway_request_id}")
async def get_all_pastel_cascade_registration_tickets_from_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    tasks_from_db = crud.cascade.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")
    return await common.get_all_reg_ticket_from_request(gateway_request_id=gateway_request_id,
                                                        tasks_from_db=tasks_from_db,
                                                        service_type="cascade",
                                                        get_registration_ticket_lambda=lambda reg_ticket_txid:
                                                          common.get_registration_action_ticket(
                                                            ticket_txid=reg_ticket_txid,
                                                            service=wn.WalletNodeService.CASCADE)
                                                        )


# Get the Pastel Cascade registration ticket from the blockchain corresponding to a particular gateway_result_id
# Note: Only authenticated user with API key
@router.get("/pastel_registration_ticket/{gateway_result_id}")
async def get_pastel_cascade_registration_ticket_by_result_id(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.cascade.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")

    return await common.get_registration_action_ticket(task_from_db.reg_ticket_txid, wn.WalletNodeService.CASCADE)


# Get the Pastel Cascade Activation ticket from the blockchain corresponding to a particular gateway_result_id
# Note: Only authenticated user with API key
@router.get("/pastel_activation_ticket/{gateway_result_id}")
async def get_pastel_cascade_activation_ticket_by_result_id(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.cascade.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")

    return await common.get_activation_ticket(task_from_db.act_ticket_txid, wn.WalletNodeService.CASCADE)


# Get the Pastel Cascade registration ticket from the blockchain from its Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/pastel_registration_ticket_from_txid/{registration_ticket_txid}")
async def get_pastel_registration_ticket_by_its_txid(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
):
    return await common.get_registration_action_ticket(registration_ticket_txid, wn.WalletNodeService.CASCADE)


# Get the Pastel Cascade activation ticket from the blockchain from its Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/pastel_activation_ticket_from_txid/{activation_ticket_txid}")
async def get_pastel_activation_ticket_by_its_txid(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
):
    return await common.get_activation_ticket(activation_ticket_txid, wn.WalletNodeService.CASCADE)


# Get the set of Pastel Cascade tickets from the blockchain corresponding to a particular stored_file_sha256_hash.
# Contains pastel_block_number and pastel_id in case there are multiple results for the same stored_file_sha256_hash
# Note: Available to any user
@router.get("/pastel_ticket_from_stored_file_hash/{stored_file_sha256_hash_as_hex}")
async def get_pastel_registration_ticket_by_stored_file_hash(
        *,
        stored_file_sha256_hash_as_hex: str,
        db: Session = Depends(session.get_db_session),
):
    output = []
    tickets = crud.reg_ticket.get_by_hash(db=db, data_hash_as_hex=stored_file_sha256_hash_as_hex)
    for ticket in tickets:
        if ticket.ticket_type == "cascade":
            reg_ticket = await common.get_registration_action_ticket(ticket.reg_ticket_txid, wn.WalletNodeService.CASCADE)
            output.append(reg_ticket)
    return output


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

    tasks_in_db = crud.cascade.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    await common.process_websocket_for_result(websocket, tasks_in_db, wn.WalletNodeService.CASCADE, gateway_request_id)


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
    await common.process_websocket_for_result(websocket, results, wn.WalletNodeService.CASCADE)


@router.get("/result/transfer_pastel_ticket")
async def transfer_pastel_ticket_to_another_pastelid(
        *,
        gateway_result_id: str = Query(),
        pastel_id: str = Query(),
        db: Session = Depends(session.get_db_session),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    return await common.transfer_ticket(db, gateway_result_id, current_user.id, pastel_id,
                                        crud.cascade.get_by_result_id_and_owner, crud.cascade.update)
