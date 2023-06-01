from fastapi import APIRouter, Depends, HTTPException, UploadFile, WebSocket, Query, Body
from typing import List, Optional

from pydantic import parse_raw_as
from sqlalchemy.orm import Session
from starlette.responses import Response
from datetime import datetime

import app.db.session as session
from app import models, crud, schemas
from app.api import deps, common
import app.utils.walletnode as wn
from app.utils.ipfs_tools import search_file_locally_or_in_ipfs

router = APIRouter()


# Submit a NFT gateway_request for the current user.
# Note: Only authenticated user with API key
@router.post("", response_model=schemas.ResultRegistrationResult, response_model_exclude_none=True)
async def process_request(
        *,
        file: UploadFile,
        make_publicly_accessible: bool = Query(True, description="Make the file publicly accessible"),
        collection_act_txid: Optional[str] = Query("", description="Transaction ID of the collection, if any"),
        open_api_group_id: Optional[str] = Query("pastel", description="Group ID for the NFT, in most cases you don't need to change it"),
        nft_details_payload: str = Body(...),
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.ResultRegistrationResult:
    nft_properties = parse_raw_as(schemas.NftPropertiesExternal, nft_details_payload)
    return await common.process_nft_request(file=file,
                                            make_publicly_accessible=make_publicly_accessible,
                                            collection_act_txid=collection_act_txid,
                                            open_api_group_id=open_api_group_id,
                                            nft_details_payload=nft_properties,
                                            user_id=current_user.id)


# Get all NFT gateway_results for the current user.
# Note: Only authenticated user with API key
@router.get("/gateway_results", response_model=List[schemas.ResultRegistrationResult], response_model_exclude_none=True)
async def get_all_results(
        *,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_nft),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.ResultRegistrationResult]:
    task_results = []
    tasks_from_db = crud.nft.get_multi_by_owner(db=db, owner_id=current_user.id)
    if not tasks_from_db:
        raise HTTPException(status_code=404, detail="No gateway_requests found")
    for task_from_db in tasks_from_db:
        task_result = await common.check_result_registration_status(task_from_db, wn.WalletNodeService.NFT)
        task_results.append(task_result)
    return task_results


# Get an individual NFT gateway_result by its result_id.
# Note: Only authenticated user with API key
@router.get("/gateway_results/{gateway_result_id}",
            response_model=schemas.ResultRegistrationResult, response_model_exclude_none=True)
async def get_result_by_result_id(
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


# Get the underlying NFT stored_file from the corresponding gateway_result_id
# Note: Only authenticated user with API key
@router.get("/stored_file/{gateway_result_id}")
async def get_stored_file_by_result_id(
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
@router.get("/stored_file_from_registration_ticket/{registration_ticket_txid}")
async def get_stored_file_by_registration_ticket(
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
@router.get("/stored_file_from_activation_ticket/{activation_ticket_txid}")
async def get_stored_file_by_activation_ticket(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
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
@router.get("/public_stored_file_from_registration_ticket/{registration_ticket_txid}")
async def get_public_stored_file_by_registration_ticket(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
):
    return common.get_public_file(db=db,
                                  ticket_type="nft",
                                  registration_ticket_txid=registration_ticket_txid,
                                  wn_service=wn.WalletNodeService.NFT)


# Get the ORIGINAL uploaded file from the corresponding gateway_result_id
# Note: Only authenticated user with API key
@router.get("/originally_submitted_file/{gateway_result_id}")
async def get_originally_submitted_file_by_result_id(
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


# Get Pastel NFT registration ticket from the blockchain corresponding to a particular gateway_result_id.
# Note: Only authenticated user with API key
@router.get("/pastel_registration_ticket/{gateway_result_id}")
async def get_pastel_nft_registration_ticket_by_result_id(
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
@router.get("/pastel_activation_ticket/{gateway_result_id}")
async def get_pastel_sense_activation_ticket_by_result_id(
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
@router.get("/pastel_registration_ticket_from_txid/{registration_ticket_txid}")
async def get_pastel_registration_ticket_by_its_txid(
        *,
        registration_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
):
    return await common.get_registration_nft_ticket(registration_ticket_txid)


# Get the Pastel NFT Activation Ticket from the blockchain from its Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/pastel_activation_ticket_from_txid/{activation_ticket_txid}")
async def get_pastel_activation_ticket_by_its_txid(
        *,
        activation_ticket_txid: str,
        db: Session = Depends(session.get_db_session),
):
    return await common.get_activation_ticket(activation_ticket_txid, wn.WalletNodeService.NFT)


# Get the set of Pastel NFT ticket from the blockchain corresponding to a particular media_file_sha256_hash;
# Contains block number and pastel_id in case there are multiple results for the same media_file_sha256_hash
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/pastel_ticket_by_media_file_hash/{media_file_sha256_hash}")
async def get_pastel_ticket_data_from_media_file_hash(
        *,
        media_file_sha256_hash: str,
        db: Session = Depends(session.get_db_session),
):
    output = []
    tickets = crud.reg_ticket.get_by_hash(db=db, data_hash=media_file_sha256_hash)
    for ticket in tickets:
        if ticket.ticket_type == "nft":
            reg_ticket = await common.get_registration_action_ticket(ticket.reg_ticket_txid, wn.WalletNodeService.NFT)
            output.append(reg_ticket)
    return output


# Get the underlying NFT raw_dd_result_file from the corresponding gateway_result_id.
# Note: Only authenticated user with API key
@router.get("/raw_dd_result_file/{gateway_result_id}")
async def get_raw_dd_result_file(
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
@router.get("/parsed_dd_result_file/{gateway_result_id}")
async def get_parsed_dd_result_file(
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
    parsed_file_bytes = await common.parse_sense_data(raw_file_bytes)
    return Response(content=parsed_file_bytes, media_type="application/json")


# Get the underlying NFT raw_dd_result_file from the corresponding NFT Registration Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/raw_dd_result_file_by_registration_ticket/{registration_ticket_txid}")
async def get_raw_dd_result_file_by_registration_ticket(
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


# Get the underlying Sense parsed_dd_result_file from the corresponding NFT Registration Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/parsed_dd_result_file_by_registration_ticket/{registration_ticket_txid}")
async def get_parsed_dd_result_file_by_registration_ticket(
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
    parsed_file_bytes = await common.parse_sense_data(raw_file_bytes)
    return Response(content=parsed_file_bytes, media_type="application/json")


# Get the underlying Sense raw_dd_result_file from the corresponding NFT Activation Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/raw_dd_result_file_by_activation_ticket/{activation_ticket_txid}")
async def get_raw_dd_result_file_by_activation_ticket(
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


# Get the underlying Sense parsed_dd_result_file from the corresponding NFT Activation Ticket Transaction ID
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/parsed_dd_result_file_by_activation_txid/{activation_ticket_txid}")
async def parsed_dd_result_file_by_act_txid(
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
    parsed_file_bytes = await common.parse_sense_data(raw_file_bytes)
    return Response(content=parsed_file_bytes, media_type="application/json")


# Get a list of the NFT raw_dd_result_file for the given pastel_id
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/raw_dd_result_file_by_pastel_id/{pastel_id_of_user}")
async def get_raw_dd_result_file_by_pastel_id(
        *,
        pastel_id_of_user: str,
):
    return await common.get_all_sense_data_for_pastelid(pastel_id=pastel_id_of_user,
                                                        search_data_lambda=lambda txid:
                                                            common.search_nft_dd_result_pastel(
                                                                reg_ticket_txid=txid,
                                                                throw=False)
                                                        )


# Get a list of the NFT parsed_dd_result_file for the given pastel_id
# Note: Available to any user and also visible on the Pastel Explorer site
@router.get("/parsed_dd_result_file_by_pastel_id/{pastel_id_of_user}")
async def parsed_raw_dd_result_file_by_pastel_id(
        *,
        pastel_id_of_user: str,
):
    return await common.get_all_sense_data_for_pastelid(pastel_id=pastel_id_of_user,
                                                        search_data_lambda=lambda txid:
                                                            common.search_nft_dd_result_pastel(
                                                                reg_ticket_txid=txid,
                                                                throw=False),
                                                        parse=True)


@router.websocket("/status/result")
async def ticket_status(
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


@router.get("/result/transfer_pastel_ticket")
async def transfer_pastel_ticket_to_another_pastelid(
        *,
        gateway_result_id: str = Query(),
        pastel_id: str = Query(),
        db: Session = Depends(session.get_db_session),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    task_from_db = crud.nft.get_by_result_id_and_owner(db=db, result_id=gateway_result_id, owner_id=current_user.id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")

    offer_ticket = await common.create_offer_ticket(task_from_db, pastel_id)

    if offer_ticket and 'txid' in offer_ticket and offer_ticket['txid']:
        upd = {"offer_ticket_txid": offer_ticket['txid'],
               "offer_ticket_intended_rcpt_pastel_id": pastel_id,
               "updated_at": datetime.utcnow()}
        crud.nft.update(db=db, db_obj=task_from_db, obj_in=upd)

    return offer_ticket
