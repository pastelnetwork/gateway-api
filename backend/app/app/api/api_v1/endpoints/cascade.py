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


@router.post("/", response_model=schemas.RequestResult, response_model_exclude_none=True)
async def process_request(
        *,
        files: List[UploadFile],
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.RequestResult:
    return await common.process_request(worker=cascade, files=files, user_id=current_user.id)


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
    tasks = crud.cascade.get_multi_by_owner(db=db, owner_id=current_user.id)
    if not tasks:
        raise HTTPException(status_code=404, detail="No gateway_requests found")
    return await common.parse_users_requests(tasks, wn.WalletNodeService.CASCADE)


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


@router.get("/all_files_from_request/{gateway_request_id}")
async def get_all_files_from_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    raise HTTPException(status_code=501, detail="Not implemented yet")


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


@router.get("/stored_file_by_registration_ticket/{registration_ticket_txid}")
async def get_file_by_reg_txid(
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


@router.get("/stored_file_by_activation_ticket/{activation_ticket_txid}")
async def get_file_by_act_txid(
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


@router.get("/pastel_ticket/{gateway_result_id}")
async def get_pastel_ticket(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/pastel_ticket_by_registration_ticket/{registration_ticket_txid}")
async def get_pastel_ticket_by_reg_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/pastel_ticket_by_stored_file_hash/{stored_file_sha256_hash}")
async def get_pastel_ticket_data_from_stored_file_hash(
        *,
        stored_file_sha256_hash: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
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

    results = crud.cascade.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not results:
        raise HTTPException(status_code=404, detail="No gateway_result or gateway_request found")

    await common.process_websocket_for_result(websocket, results, wn.WalletNodeService.CASCADE, gateway_request_id)


@router.websocket("/status/result")
async def result_status(
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
