import uuid
import zipfile
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, WebSocket, Query, Body
from typing import List, Optional

from sqlalchemy.orm import Session
from starlette.responses import Response

import app.db.session as session
from app import models, crud, schemas
from app.api import deps, common
import app.utils.walletnode as wn
from app.core.status import ReqStatus
from app.utils.ipfs_tools import search_file_locally_or_in_ipfs
from app.utils.filestorage import LocalFile
from app.core.config import settings

router = APIRouter()


# Submit a NFT gateway_request for the current user.
# Note: Only authenticated user with API key
@router.post("", response_model=schemas.RequestResult, response_model_exclude_none=True, operation_id="nft_process_request")
async def process_request(
        *,
        file: UploadFile,
        make_publicly_accessible: bool = Query(True, description="Make the file publicly accessible"),
        collection_act_txid: Optional[str] = Query("", description="Transaction ID of the collection, if any"),
        open_api_group_id: Optional[str] = Query("pastel", description="Group ID for the NFT, in most cases you don't need to change it"),
        after_activation_transfer_to_pastelid: Optional[str] = Query("", description="PastelID to transfer the NFT to after activation, if any"),
        nft_details_payload: str = Body(...),
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.RequestResult:

    reg_result = await common.check_file_is_not_empty(file)
    if reg_result is not None:
        return schemas.RequestResult(
            request_id='',
            request_status=schemas.Status.ERROR,
            results=[reg_result]
        )

    reg_result = await common.check_image(file, db, wn.WalletNodeService.NFT)
    if reg_result is not None:
        return schemas.RequestResult(
            request_id='',
            request_status=schemas.Status.ERROR,
            results=[reg_result]
        )

    request_id = str(uuid.uuid4())
    result_id = str(uuid.uuid4())
    lf = LocalFile(file.filename, file.content_type, result_id)
    await lf.save(file)

    nft_properties = schemas.NftPropertiesExternal.model_validate_json(nft_details_payload)
    return await common.process_nft_request(db=db, lf=lf,
                                            request_id=request_id,
                                            result_id=result_id,
                                            make_publicly_accessible=make_publicly_accessible,
                                            collection_act_txid=collection_act_txid,
                                            open_api_group_id=open_api_group_id,
                                            after_activation_transfer_to_pastelid=after_activation_transfer_to_pastelid,
                                            nft_details_payload=nft_properties,
                                            user_id=current_user.id,
                                            api_key=api_key)


# Two-step NFT start - Upload file for NFT request.
# Note: Only authenticated user with API key
@router.post("/step_1_upload_image_file", response_model=schemas.ResultRegistrationResult, response_model_exclude_none=True, operation_id="nft_step1_upload_image_file")
async def step_1_upload_image_file(
        *,
        file: UploadFile,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    reg_result = await common.check_file_is_not_empty(file)
    if reg_result is not None:
        return reg_result

    reg_result = await common.check_image(file, db, wn.WalletNodeService.NFT)
    if reg_result is not None:
        return reg_result

    file_id = str(uuid.uuid4())
    lf = LocalFile(file.filename, file.content_type, file_id)
    await lf.save(file)
    return schemas.ResultRegistrationResult(
        file_name=file.filename,
        file_type=file.content_type,
        file_id=file_id,
        result_status=schemas.Status.SUCCESS,
    )

# Two-step NFT start - Submit a NFT gateway_request for the current user.
# Note: Only authenticated user with API key
@router.post("/step_2_process_nft", response_model=schemas.RequestResult, response_model_exclude_none=True, operation_id="nft_step2_process_nft")
async def step_2_process_nft(
        *,
        file_id: str = Query("file_id", description="File ID from the upload endpoint"),
        make_publicly_accessible: bool = Query(True, description="Make the file publicly accessible"),
        collection_act_txid: Optional[str] = Query("", description="Transaction ID of the collection, if any"),
        open_api_group_id: Optional[str] = Query("pastel", description="Group ID for the NFT, in most cases you don't need to change it"),
        after_activation_transfer_to_pastelid: Optional[str] = Query("", description="PastelID to transfer the NFT to after activation, if any"),
        nft_details_payload: schemas.NftPropertiesExternal = Body(...),
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.RequestResult:
    lf = LocalFile.load(file_id)
    request_id = str(uuid.uuid4())
    return await common.process_nft_request(db=db, lf=lf,
                                            request_id=request_id,
                                            result_id=file_id,
                                            make_publicly_accessible=make_publicly_accessible,
                                            collection_act_txid=collection_act_txid,
                                            open_api_group_id=open_api_group_id,
                                            after_activation_transfer_to_pastelid=after_activation_transfer_to_pastelid,
                                            nft_details_payload=nft_details_payload,
                                            user_id=current_user.id,
                                            api_key=api_key)


# Get all NFT OpenAPI gateway_requests for the current user.
# Note: Only authenticated user with API key
@router.get("/gateway_requests", response_model=List[schemas.RequestResult], response_model_exclude_none=True, operation_id="nft_get_all_requests")
async def get_all_requests(
        *,
        status_requested: Optional[ReqStatus] = Query(None),
        offset: int = 0, limit: int = 10000,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.RequestResult]:
    tasks_from_db = crud.nft.get_multi_by_owner_and_status(db=db, owner_id=current_user.id,
                                                           req_status=status_requested.value if status_requested else None,
                                                           skip=offset, limit=limit)
    if not tasks_from_db:
        raise HTTPException(status_code=200, detail="No gateway_requests found")
    return await common.parse_users_requests(tasks_from_db, wn.WalletNodeService.NFT)


# Get an individual NFT gateway_request by its gateway_request_id.
# Note: Only authenticated user with API key
@router.get("/gateway_requests/{gateway_request_id}", response_model=schemas.RequestResult, response_model_exclude_none=True, operation_id="nft_get_request")
async def get_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.RequestResult:
    tasks_from_db = crud.nft.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")
    return await common.parse_user_request(tasks_from_db, gateway_request_id, wn.WalletNodeService.NFT)


# Get all NFT gateway_results for the current user.
# Note: Only authenticated user with API key
@router.get("/gateway_results", response_model=List[schemas.ResultRegistrationResult], response_model_exclude_none=True, operation_id="nft_get_all_results")
async def get_all_results(
        *,
        status_requested: Optional[ReqStatus] = Query(None),
        offset: int = 0, limit: int = 10000,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.ResultRegistrationResult]:
    task_results = []
    tasks_from_db = crud.nft.get_multi_by_owner_and_status(db=db, owner_id=current_user.id,
                                                           req_status=status_requested.value if status_requested else None,
                                                           skip=offset, limit=limit)
    if not tasks_from_db:
        raise HTTPException(status_code=200, detail="No gateway_requests found")
    for task_from_db in tasks_from_db:
        task_result = await common.check_result_registration_status(task_from_db, wn.WalletNodeService.NFT)
        task_results.append(task_result)
    return task_results


# Get an individual NFT gateway_result by its result_id.
# Note: Only authenticated user with API key
@router.get("/gateway_results/{gateway_result_id}", response_model=schemas.ResultRegistrationResult, response_model_exclude_none=True, operation_id="nft_get_result")
async def get_result(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.ResultRegistrationResult:
    task_from_db = crud.nft.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    return await common.check_result_registration_status(task_from_db, wn.WalletNodeService.NFT)


# Get ALL underlying NFT stored_files from the corresponding gateway_request_id
# Note: Only authenticated user with API key
@router.get("/all_files_from_request/{gateway_request_id}", operation_id="nft_get_all_files_from_request")
async def get_all_files_from_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    tasks_from_db = crud.nft.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for task_from_db in tasks_from_db:
            file_bytes = await common.search_gateway_file(db=db,
                                                          task_from_db=task_from_db,
                                                          service=wn.WalletNodeService.NFT,
                                                          update_task_in_db_func=crud.nft.update)
            zip_file.writestr(task_from_db.original_file_name, file_bytes)

    return await common.stream_file(file_bytes=zip_buffer.getvalue(),
                                    original_file_name=f"{gateway_request_id}.zip",
                                    content_type="application/zip")


# Get the underlying NFT stored_file from the corresponding gateway_result_id
# Note: Only authenticated user with API key
@router.get("/stored_file/{gateway_result_id}", operation_id="nft_get_stored_file_from_result")
async def get_stored_file_from_result(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.nft.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    file_bytes = await common.search_gateway_file(db=db,
                                                  task_from_db=task_from_db,
                                                  service=wn.WalletNodeService.NFT,
                                                  update_task_in_db_func=crud.nft.update)
    return await common.stream_file(file_bytes=file_bytes,
                                    original_file_name=f"{task_from_db.original_file_name}")


# Get the underlying NFT stored_file from the corresponding NFT Registration Ticket Transaction ID
# Only succeeds if the user owns the NFT file (authenticated user with API key)
#    - in the context of Gateway it means that file was registered by that instance of Gateway with its PastelID
@router.get("/stored_file_from_registration_ticket/{registration_ticket_txid}", operation_id="nft_get_stored_file_from_registration_ticket")
async def get_stored_file_from_registration_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.nft.get_by_reg_txid_and_owner(db=db, owner_id=current_user.id,
                                                      reg_txid=registration_ticket_txid)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    file_bytes = await common.search_gateway_file(db=db,
                                                  task_from_db=task_from_db,
                                                  service=wn.WalletNodeService.NFT,
                                                  update_task_in_db_func=crud.nft.update)
    return await common.stream_file(file_bytes=file_bytes,
                                    original_file_name=f"{task_from_db.original_file_name}")


# Get the underlying NFT stored_file from the corresponding NFT Activation Ticket Transaction ID
# Only succeeds if the user owns the NFT file (authenticated user with API key)
#    - in the context of Gateway it means that file was registered by that instance of Gateway with its PastelID
@router.get("/stored_file_from_activation_ticket/{activation_ticket_txid}", operation_id="nft_get_stored_file_from_activation_ticket")
async def get_stored_file_from_activation_ticket(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.nft.get_by_act_txid_and_owner(db=db, owner_id=current_user.id,
                                                          act_txid=activation_ticket_txid)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    file_bytes = await common.search_gateway_file(db=db,
                                                  task_from_db=task_from_db,
                                                  service=wn.WalletNodeService.NFT,
                                                  update_task_in_db_func=crud.nft.update)
    return await common.stream_file(file_bytes=file_bytes,
                                    original_file_name=f"{task_from_db.original_file_name}")


# Get the Public NFT stored_file from the corresponding NFT Registration Ticket Transaction ID
# Only succeeds if the file was made Public during registration (by setting flag make_publicly_accessible)
# Note: Available to any user
@router.get("/public_stored_file_from_registration_ticket/{registration_ticket_txid}", operation_id="nft_get_public_stored_file_from_registration_ticket")
async def get_public_stored_file_from_registration_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
):
    return await common.get_public_file(db=db,
                                  ticket_type="nft",
                                  registration_ticket_txid=registration_ticket_txid,
                                  wn_service=wn.WalletNodeService.NFT)


# Get the ORIGINAL uploaded file from the corresponding gateway_result_id
# Note: Only authenticated user with API key
@router.get("/originally_submitted_file/{gateway_result_id}", operation_id="nft_get_originally_submitted_file_from_result")
async def get_originally_submitted_file_from_result(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.nft.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    try:
        file_bytes = await search_file_locally_or_in_ipfs(task_from_db.original_file_local_path,
                                                          task_from_db.original_file_ipfs_link)
    except Exception as e:
        raise HTTPException(status_code=404, detail="File not found")

    return await common.stream_file(file_bytes=file_bytes.read(),
                                    original_file_name=f"{task_from_db.original_file_name}")


# Get ALL Pastel NFT registration tickets from the blockchain corresponding to a particular gateway_request_id.
# Note: Only authenticated user with API key
@router.get("/pastel_registration_tickets/{gateway_request_id}", operation_id="nft_get_all_pastel_registration_tickets_from_request")
async def get_all_pastel_nft_registration_tickets_from_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    tasks_from_db = crud.nft.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")
    return await common.get_all_reg_ticket_from_request(gateway_request_id=gateway_request_id,
                                                        tasks_from_db=tasks_from_db,
                                                        service_type="nft",
                                                        get_registration_ticket_lambda=lambda reg_ticket_txid:
                                                            common.get_registration_nft_ticket(
                                                                ticket_txid=reg_ticket_txid)
                                                        )


# Get Pastel NFT registration ticket from the blockchain corresponding to a particular gateway_result_id.
# Note: Only authenticated user with API key
@router.get("/pastel_registration_ticket/{gateway_result_id}", operation_id="nft_get_pastel_registration_ticket_from_result")
async def get_pastel_nft_registration_ticket_from_result(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.nft.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")

    return await common.get_registration_nft_ticket(task_from_db.reg_ticket_txid)


# Get Pastel NFT activation ticket from the blockchain corresponding to a particular gateway_result_id.
# Note: Only authenticated user with API key
@router.get("/pastel_activation_ticket/{gateway_result_id}", operation_id="nft_get_pastel_activation_ticket_from_result")
async def get_pastel_nft_activation_ticket_from_result(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.nft.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")

    return await common.get_activation_ticket(task_from_db.act_ticket_txid, wn.WalletNodeService.NFT)


# Get the Pastel NFT Registration Ticket from the blockchain from its Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/pastel_registration_ticket_from_txid/{registration_ticket_txid}", operation_id="nft_get_pastel_registration_ticket_from_txid")
async def get_pastel_registration_ticket_from_txid(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
):
    return await common.get_registration_nft_ticket(registration_ticket_txid)


# Get the Pastel NFT Activation Ticket from the blockchain from its Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/pastel_activation_ticket_from_txid/{activation_ticket_txid}", operation_id="nft_get_pastel_activation_ticket_from_txid")
async def get_pastel_activation_ticket_from_txid(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
):
    return await common.get_activation_ticket(activation_ticket_txid, wn.WalletNodeService.NFT)


# Get the set of Pastel NFT ticket from the blockchain corresponding to a particular media_file_sha256_hash;
# Contains block number and pastel_id in case there are multiple results for the same media_file_sha256_hash
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/pastel_registration_ticket_from_media_file_hash/{media_file_sha256_hash}", operation_id="nft_get_pastel_registration_ticket_from_media_file_hash")
async def get_pastel_registration_ticket_from_media_file_hash(
        *,
        media_file_sha256_hash: str,
        db: Session = Depends(session.get_db_session),
):
    output = []
    tickets = crud.reg_ticket.get_by_hash(db=db, data_hash_as_hex=media_file_sha256_hash, ticket_type="nft")
    for ticket in tickets:
        reg_ticket = await common.get_registration_nft_ticket(ticket.reg_ticket_txid)
        output.append(reg_ticket)
    return output


# Get the set of underlying NFT raw_outputs_files from the corresponding gateway_request_id.
# Note: Only authenticated user with API key
@router.get("/all_raw_dd_result_files_from_request/{gateway_request_id}", operation_id="nft_get_all_raw_dd_result_files_from_request")
async def get_all_raw_dd_result_files_from_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    tasks_from_db = crud.nft.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")
    return await common.get_all_sense_or_nft_dd_data_from_request(tasks_from_db=tasks_from_db,
                                                                  gateway_request_id=gateway_request_id,
                                                                  search_data_lambda=lambda task_from_db:
                                                                    common.search_nft_dd_result_gateway(
                                                                        db=db,
                                                                        task_from_db=task_from_db,
                                                                        update_task_in_db_func=crud.nft.update),
                                                                  file_suffix='nft-dd-data'
                                                                  )


# Get the set of underlying NFT parsed_outputs_files from the corresponding gateway_request_id.
# Note: Only authenticated user with API key
@router.get("/all_parsed_dd_result_files_from_request/{gateway_request_id}", operation_id="nft_get_all_parsed_dd_result_files_from_request")
async def get_all_parsed_dd_result_files_from_request(
        *,
        gateway_request_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    tasks_from_db = crud.nft.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_results or gateway_requests found")
    return await common.get_all_sense_or_nft_dd_data_from_request(tasks_from_db=tasks_from_db,
                                                                  gateway_request_id=gateway_request_id,
                                                                  search_data_lambda=lambda task_from_db:
                                                                    common.search_nft_dd_result_gateway(
                                                                        db=db,
                                                                        task_from_db=task_from_db,
                                                                        update_task_in_db_func=crud.nft.update),
                                                                  file_suffix='nft-dd-data',
                                                                  parse=True)


# Get the underlying NFT raw_dd_result_file from the corresponding gateway_result_id.
# Note: Only authenticated user with API key
@router.get("/raw_dd_result_file/{gateway_result_id}", operation_id="nft_get_raw_dd_result_file_from_result")
async def get_raw_dd_result_file_from_result(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> Response:
    task_from_db = crud.nft.get_by_result_id(db=db, result_id=gateway_result_id)  # anyone can call it
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    json_bytes = await common.search_nft_dd_result_gateway(db=db,
                                                           task_from_db=task_from_db,
                                                           update_task_in_db_func=crud.nft.update)
    return Response(content=json_bytes, media_type="application/json")


# Get the underlying NFT parsed_dd_result_file from the corresponding gateway_result_id.
# Note: Only authenticated user with API key
@router.get("/parsed_dd_result_file/{gateway_result_id}", operation_id="nft_get_parsed_dd_result_file_from_result")
async def get_parsed_dd_result_file_from_result(
        *,
        gateway_result_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> Response:
    task_from_db = crud.nft.get_by_result_id(db=db, result_id=gateway_result_id)  # anyone can call it
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")
    raw_file_bytes = await common.search_nft_dd_result_gateway(db=db,
                                                               task_from_db=task_from_db,
                                                               update_task_in_db_func=crud.nft.update)
    parsed_file_bytes = await common.parse_dd_data(raw_file_bytes)
    return Response(content=parsed_file_bytes, media_type="application/json")


# Get the underlying NFT raw_dd_result_file from the corresponding NFT Registration Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/raw_dd_result_file_from_registration_ticket/{registration_ticket_txid}", operation_id="nft_get_raw_dd_result_file_from_registration_ticket")
async def get_raw_dd_result_file_from_registration_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session)
) -> Response:
    task_from_db = crud.nft.get_by_reg_txid(db=db, reg_txid=registration_ticket_txid)  # anyone can call it
    if task_from_db:
        raw_file_bytes = await common.search_nft_dd_result_gateway(db=db,
                                                                   task_from_db=task_from_db,
                                                                   update_task_in_db_func=crud.nft.update)
    else:
        raw_file_bytes = await common.search_nft_dd_result_pastel(reg_ticket_txid=registration_ticket_txid)
    return Response(content=raw_file_bytes, media_type="application/json")


# Get the underlying NFT parsed_dd_result_file from the corresponding NFT Registration Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/parsed_dd_result_file_from_registration_ticket/{registration_ticket_txid}", operation_id="nft_get_parsed_dd_result_file_from_registration_ticket")
async def get_parsed_dd_result_file_from_registration_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session)
) -> Response:
    task_from_db = crud.nft.get_by_reg_txid(db=db, reg_txid=registration_ticket_txid)  # anyone can call it
    if task_from_db:
        raw_file_bytes = await common.search_nft_dd_result_gateway(db=db,
                                                                   task_from_db=task_from_db,
                                                                   update_task_in_db_func=crud.nft.update)
    else:
        raw_file_bytes = await common.search_nft_dd_result_pastel(reg_ticket_txid=registration_ticket_txid)
    parsed_file_bytes = await common.parse_dd_data(raw_file_bytes)
    return Response(content=parsed_file_bytes, media_type="application/json")


# Get the underlying NFT raw_dd_result_file from the corresponding NFT Activation Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/raw_dd_result_file_from_activation_ticket/{activation_ticket_txid}", operation_id="nft_get_raw_dd_result_file_from_activation_ticket")
async def get_raw_dd_result_file_from_activation_ticket(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session)
) -> Response:
    task_from_db = crud.nft.get_by_act_txid(db=db, act_txid=activation_ticket_txid)  # anyone can call it
    if task_from_db:
        raw_file_bytes = await common.search_nft_dd_result_gateway(db=db,
                                                                   task_from_db=task_from_db,
                                                                   update_task_in_db_func=crud.nft.update)
    else:
        registration_ticket_txid = await common.get_reg_txid_by_act_txid(activation_ticket_txid)
        raw_file_bytes = await common.search_nft_dd_result_pastel(reg_ticket_txid=registration_ticket_txid)
    return Response(content=raw_file_bytes, media_type="application/json")


# Get the underlying NFT parsed_dd_result_file from the corresponding NFT Activation Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/parsed_dd_result_file_from_activation_ticket/{activation_ticket_txid}", operation_id="nft_get_parsed_dd_result_file_from_activation_ticket")
async def get_parsed_dd_result_file_from_activation_ticket(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session)
) -> Response:
    task_from_db = crud.nft.get_by_act_txid(db=db, act_txid=activation_ticket_txid)  # anyone can call it
    if task_from_db:
        raw_file_bytes = await common.search_nft_dd_result_gateway(db=db,
                                                                   task_from_db=task_from_db,
                                                                   update_task_in_db_func=crud.nft.update)
    else:
        registration_ticket_txid = await common.get_reg_txid_by_act_txid(activation_ticket_txid)
        raw_file_bytes = await common.search_nft_dd_result_pastel(reg_ticket_txid=registration_ticket_txid)
    parsed_file_bytes = await common.parse_dd_data(raw_file_bytes)
    return Response(content=parsed_file_bytes, media_type="application/json")


# Get a list of the NFT raw_dd_result_file for the given pastel_id
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/raw_dd_result_file_from_pastel_id/{pastel_id_of_user}", operation_id="nft_get_raw_dd_result_file_from_pastel_id")
async def get_raw_dd_result_file_from_pastel_id(
        *,
        pastel_id_of_user: str,
):
    return await common.get_all_sense_or_nft_dd_data_for_pastelid(pastel_id=pastel_id_of_user,
                                                                  ticket_type="nft", action_type='',
                                                                  search_data_lambda=lambda txid:
                                                                  common.search_nft_dd_result_pastel(
                                                                      reg_ticket_txid=txid,
                                                                      throw=False)
                                                                  )


# Get a list of the NFT parsed_dd_result_file for the given pastel_id
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/parsed_dd_result_file_from_pastel_id/{pastel_id_of_user}", operation_id="nft_get_parsed_dd_result_file_from_pastel_id")
async def get_parsed_dd_result_file_from_pastel_id(
        *,
        pastel_id_of_user: str,
):
    return await common.get_all_sense_or_nft_dd_data_for_pastelid(pastel_id=pastel_id_of_user,
                                                                  ticket_type="nft", action_type='',
                                                                  search_data_lambda=lambda txid:
                                                                  common.search_nft_dd_result_pastel(
                                                                      reg_ticket_txid=txid,
                                                                      throw=False),
                                                                  parse=True)


@router.websocket("/status/request")
async def request_status(
        websocket: WebSocket,
        gateway_request_id: str = Query(default=None),
        api_key: str = Query(default=None),
        db: Session = Depends(session.get_db_session),
):
    await websocket.accept()

    apikey = await deps.APIKeyAuth.get_api_key_for_nft(db, api_key)
    current_user = await deps.APIKeyAuth.get_user_by_apikey(db, api_key)

    tasks_in_db = crud.nft.get_all_in_request(db=db, request_id=gateway_request_id, owner_id=current_user.id)
    await common.process_websocket_for_result(websocket, tasks_in_db, wn.WalletNodeService.NFT, gateway_request_id)


@router.websocket("/status/result")
async def result_status(
        websocket: WebSocket,
        gateway_result_id: str = Query(default=None),
        api_key: str = Query(default=None),
        db: Session = Depends(session.get_db_session),
):
    await websocket.accept()

    await deps.APIKeyAuth.get_api_key_for_nft(db, api_key)
    current_user = await deps.APIKeyAuth.get_user_by_apikey(db, api_key)

    tasks_in_db = [crud.nft.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)]
    await common.process_websocket_for_result(websocket, tasks_in_db, wn.WalletNodeService.NFT)


@router.get("/result/transfer_pastel_ticket", operation_id="nft_transfer_pastel_ticket_to_another_pastelid")
async def transfer_pastel_ticket_to_another_pastelid(
        *,
        gateway_result_id: str = Query(),
        pastel_id: str = Query(),
        db: Session = Depends(session.get_db_session),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    return await common.transfer_ticket(db, gateway_result_id, current_user.id, pastel_id,
                                        crud.nft.get_by_result_id_and_owner, crud.nft.update)
