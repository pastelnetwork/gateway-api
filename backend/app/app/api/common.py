import asyncio
import hashlib
import json
import zipfile
import io
import uuid
import base64
import logging
from typing import List
from datetime import datetime
import zstd as zstd

from fastapi import UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse
from requests import HTTPError

from app.utils.filestorage import LocalFile, store_file_into_local_cache, search_file_in_local_cache, \
    search_nft_dd_result, search_processed_file
from app import schemas, crud
from app.core.config import settings
from app.core.status import DbStatus, get_status_from_history_log
from app.utils import walletnode as wn
import app.utils.pasteld as psl
from app.utils.ipfs_tools import store_file_to_ipfs
import app.celery_tasks.nft as nft

logger = logging.getLogger(__name__)


async def process_nft_request(
        *,
        db,
        lf: LocalFile,
        request_id: str,
        result_id: str,
        make_publicly_accessible: bool,
        collection_act_txid: str,
        open_api_group_id: str,
        after_activation_transfer_to_pastelid: str,
        nft_details_payload: schemas.NftPropertiesExternal,
        user_id: int,
) -> schemas.RequestResult:
    await check_pastelid_for_transfer(db=db, pastel_id=after_activation_transfer_to_pastelid, user_id=user_id)

    ipfs_hash = await store_file_to_ipfs(lf.path)
    _ = (
            nft.register_file.s(result_id, lf, request_id, user_id, ipfs_hash, make_publicly_accessible,
                                collection_act_txid, open_api_group_id, nft_details_payload,
                                after_activation_transfer_to_pastelid) |
            nft.process.s()
    ).apply_async()

    reg_result = await make_pending_result(lf.name, lf.type, ipfs_hash, result_id)
    reg_result.make_publicly_accessible = make_publicly_accessible
    request_result = schemas.RequestResult(
        request_id=request_id,
        request_status=schemas.Status.PENDING,
        results=[reg_result]
    )
    return request_result


async def process_action_request(
        *,
        db,
        worker,
        files: List[UploadFile],
        make_publicly_accessible: bool,
        collection_act_txid: str,
        open_api_group_id: str,
        after_activation_transfer_to_pastelid: str,
        user_id: int,
        service: wn.WalletNodeService
) -> schemas.RequestResult:
    request_id = str(uuid.uuid4())
    request_result = schemas.RequestResult(
        request_id=request_id,
        request_status=schemas.Status.PENDING,
        results=[]
    )
    await check_pastelid_for_transfer(db=db, pastel_id=after_activation_transfer_to_pastelid, user_id=user_id)

    for file in files:
        reg_result = await check_file_is_not_empty(file)
        if reg_result is not None:
            request_result.results.append(reg_result)
            continue

        if service == wn.WalletNodeService.SENSE:
            reg_result = await check_image(file, db, service)
            if reg_result is not None:
                request_result.results.append(reg_result)
                continue

        result_id = str(uuid.uuid4())
        lf = LocalFile(file.filename, file.content_type, result_id)
        await lf.save(file)
        ipfs_hash = await store_file_to_ipfs(lf.path)
        _ = (
                worker.register_file.s(result_id, lf, request_id, user_id, ipfs_hash,
                                       make_publicly_accessible, collection_act_txid, open_api_group_id,
                                       after_activation_transfer_to_pastelid) |
                worker.preburn_fee.s() |
                worker.process.s()
        ).apply_async()

        reg_result = await make_pending_result(file.filename, file.content_type, ipfs_hash, result_id)
        if service == wn.WalletNodeService.CASCADE:
            reg_result.make_publicly_accessible=make_publicly_accessible
        request_result.results.append(reg_result)

    all_failed = True
    for result in request_result.results:
        all_failed &= result.result_status == schemas.Status.ERROR
    request_result.request_status = schemas.Status.ERROR if all_failed \
        else schemas.Status.PENDING

    return request_result


async def check_pastelid_for_transfer(*, db, pastel_id, user_id):
    if pastel_id:
        user = crud.user.get_by_pastelid(db, pastel_id=pastel_id)
        if not user or user.id != user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f'PastelID {pastel_id} for transfer registered ticket '
                                       f'not found in the user''s Claimed PastelIDs list')


async def make_pending_result(file_name, file_content_type, ipfs_hash, result_id):
    reg_result = schemas.ResultRegistrationResult(
        result_id=result_id,
        result_status=schemas.Status.PENDING,
        created_at=datetime.utcnow(),
        last_updated_at=datetime.utcnow(),
        original_file_ipfs_link=ipfs_hash,
    )
    if file_name:
        reg_result.file_name = file_name
    if file_content_type:
        reg_result.file_type = file_content_type
    if ipfs_hash:
        reg_result.original_file_ipfs_link = f'https://ipfs.io/ipfs/{ipfs_hash}'
    return reg_result


async def check_result_registration_status(task_from_db, service: wn.WalletNodeService) \
        -> schemas.ResultRegistrationResult:

    result_registration_status = schemas.Status.UNKNOWN
    if task_from_db.process_status:
        if task_from_db.process_status in [DbStatus.NEW.value, DbStatus.UPLOADED.value,
                                           DbStatus.PREBURN_FEE.value, DbStatus.STARTED.value]:
            result_registration_status = schemas.Status.PENDING
        if task_from_db.process_status in [DbStatus.ERROR.value, DbStatus.RESTARTED.value]:
            result_registration_status = schemas.Status.PENDING
        elif task_from_db.process_status == DbStatus.REGISTERED.value:
            result_registration_status = schemas.Status.PENDING_ACT
        elif task_from_db.process_status == DbStatus.DONE.value:
            result_registration_status = schemas.Status.SUCCESS
        elif task_from_db.process_status == DbStatus.DEAD.value:
            result_registration_status = schemas.Status.FAILED

    wn_task_status = ''
    if (result_registration_status == schemas.Status.UNKNOWN or
        result_registration_status == schemas.Status.PENDING) \
            and task_from_db.wn_task_id:
        try:
            history_log = get_status_from_history_log(task_from_db, service)
            if history_log and history_log.status_messages:
                wn_task_status = history_log.status_messages
            else:
                wn_task_status = wn.call(False,
                                         service,
                                         f'{task_from_db.wn_task_id}/history',
                                         {}, [], {},
                                         "", "")
            if wn_task_status:
                for step in wn_task_status:
                    if step['status'] == 'Task Rejected' or step['status'] == 'Task Failed':
                        result_registration_status = schemas.Status.ERROR \
                            if settings.RETURN_DETAILED_WN_ERROR else schemas.Status.PENDING
                        break
                    if step['status'] == 'Task Completed':
                        result_registration_status = schemas.Status.SUCCESS
                        break
                    if step['status'] == 'Request Accepted':
                        result_registration_status = schemas.Status.PENDING_REG
                    if step['status'] == 'Request Registered':
                        result_registration_status = schemas.Status.PENDING_ACT
        except Exception as e:
            logger.error(e)
            result_registration_status = schemas.Status.ERROR \
                if settings.RETURN_DETAILED_WN_ERROR else schemas.Status.PENDING

    reg_result = schemas.ResultRegistrationResult(
        result_id=task_from_db.result_id,
        created_at=task_from_db.created_at,
        last_updated_at=task_from_db.updated_at,
        result_status=result_registration_status,
        retry_num=task_from_db.retry_num,
    )
    if service != wn.WalletNodeService.COLLECTION:
        reg_result.file_name = task_from_db.original_file_name
        reg_result.file_type = task_from_db.original_file_content_type

    if result_registration_status != schemas.Status.ERROR and result_registration_status != schemas.Status.FAILED:
        reg_result.registration_ticket_txid = task_from_db.reg_ticket_txid
        reg_result.activation_ticket_txid = task_from_db.act_ticket_txid

        if service != wn.WalletNodeService.COLLECTION:
            if task_from_db.original_file_ipfs_link:
                reg_result.original_file_ipfs_link = f'https://ipfs.io/ipfs/{task_from_db.original_file_ipfs_link}'
            if task_from_db.stored_file_ipfs_link:
                reg_result.stored_file_ipfs_link = f'https://ipfs.io/ipfs/{task_from_db.stored_file_ipfs_link}'
            reg_result.stored_file_aws_link = task_from_db.stored_file_aws_link
            reg_result.stored_file_other_links = task_from_db.stored_file_other_links
            if service == wn.WalletNodeService.CASCADE or service == wn.WalletNodeService.NFT:
                if task_from_db.offer_ticket_txid:
                    reg_result.offer_ticket_txid = task_from_db.offer_ticket_txid
                if task_from_db.offer_ticket_intended_rcpt_pastel_id:
                    reg_result.offer_ticket_intended_rcpt_pastel_id = task_from_db.offer_ticket_intended_rcpt_pastel_id

        if wn_task_status and settings.RETURN_DETAILED_WN_ERROR:
            reg_result.status_messages = wn_task_status
    elif settings.RETURN_DETAILED_WN_ERROR:
        reg_result.error = wn_task_status
    return reg_result


async def parse_users_requests(tasks_from_db, service: wn.WalletNodeService) -> List[schemas.RequestResult]:
    gw_requests = {}
    all_failed_map = {}
    all_success_map = {}
    for task_from_db in tasks_from_db:
        if task_from_db.request_id in gw_requests:
            request = gw_requests[task_from_db.request_id]
        else:
            request = schemas.RequestResult(request_id=task_from_db.request_id,
                                            request_status=schemas.Status.UNKNOWN,
                                            results=[])
            all_failed_map[task_from_db.request_id] = True
            all_success_map[task_from_db.request_id] = True

        result_registration_result = await check_result_registration_status(task_from_db, service)
        request.results.append(result_registration_result)
        all_failed_map[task_from_db.request_id] &= result_registration_result.result_status == schemas.Status.FAILED
        all_success_map[task_from_db.request_id] &= result_registration_result.result_status == schemas.Status.SUCCESS
        request.request_status = schemas.Status.FAILED if all_failed_map[task_from_db.request_id] \
            else schemas.Status.SUCCESS if all_success_map[task_from_db.request_id] \
            else schemas.Status.PENDING
        gw_requests[task_from_db.request_id] = request
    return list(gw_requests.values())


async def parse_user_request(results_in_request, request_id, service: wn.WalletNodeService) -> schemas.RequestResult:
    request = schemas.RequestResult(request_id=request_id, request_status=schemas.Status.UNKNOWN, results=[])
    all_failed = True
    all_success = True
    for result in results_in_request:
        result_registration_result = await check_result_registration_status(result, service)
        request.results.append(result_registration_result)
        all_failed &= result_registration_result.result_status == schemas.Status.FAILED
        all_success &= result_registration_result.result_status == schemas.Status.SUCCESS
    request.request_status = schemas.Status.FAILED if all_failed else schemas.Status.SUCCESS if all_success \
        else schemas.Status.PENDING
    return request


async def process_websocket_for_result(websocket, tasks_from_db, service: wn.WalletNodeService, request_id: str = None):
    if not tasks_from_db or not tasks_from_db[0]:
        await websocket.send_text(f"No gateway_result or gateway_request found")
        raise HTTPException(status_code=404, detail="No gateway_result or gateway_request found")

    while True:
        all_failed = True
        all_success = True
        request_results_json = []
        for task_from_db in tasks_from_db:
            result_registration_result = await check_result_registration_status(task_from_db, service)
            if result_registration_result is not None:
                request_results_json.append(
                    {
                        'result_id': result_registration_result.result_id,
                        'file_name': result_registration_result.file_name,
                        'status': result_registration_result.result_status,
                    }
                )
            all_failed &= result_registration_result.result_status == schemas.Status.FAILED
            all_success &= result_registration_result.result_status == schemas.Status.SUCCESS

        if request_id:
            result_json = {
                'request_id': request_id,
                'request_status': 'FAILED' if all_failed else 'SUCCESS' if all_success else 'PENDING',
                'results': request_results_json,
            }
        else:
            result_json = request_results_json[0]

        await websocket.send_json(result_json)
        if all_failed or all_success:
            break

        await asyncio.sleep(150)  # 2.5 minutes


# search_gateway_file searches for file in 1) local cache; 2) Pastel network; 3) IPFS
# Is used to search for files processed by Gateway: Cascade file, Sense dd data and NFT file
async def search_gateway_file(*, db, task_from_db, service: wn.WalletNodeService, update_task_in_db_func) -> bytes:

    if service == wn.WalletNodeService.SENSE and task_from_db.process_status not in [DbStatus.DONE.value]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found")

    if (service == wn.WalletNodeService.CASCADE or service == wn.WalletNodeService.NFT) \
            and task_from_db.pastel_id != settings.PASTEL_ID:  # and not task_from_db.public:
        logger.error("Backend does not have correct Pastel ID")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=f"Only owner can download cascade file")

    try:
        return await search_processed_file(db=db, task_from_db=task_from_db,
                                           update_task_in_db_func=update_task_in_db_func,
                                           task_done=(task_from_db.process_status in [DbStatus.DONE.value]), service=service)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found")


# search_pastel_file searches for file in 1) local cache; 2) Pastel network
# Is used to search for files that were not processed by Gateway: for Sense dd data and NFT dd data
async def search_pastel_file(*, db=None, reg_ticket_txid: str, service: wn.WalletNodeService, throw=True) -> bytes:

    if db:
        ticket = crud.reg_ticket.get_by_reg_ticket_txid(db=db, txid=reg_ticket_txid)
        if ticket:
            if (service == wn.WalletNodeService.SENSE and ticket.ticket_type != 'sense' or
                    service == wn.WalletNodeService.NFT and ticket.ticket_type != 'nft' or
                    service == wn.WalletNodeService.CASCADE and ticket.ticket_type != 'cascade' or
                    service == wn.WalletNodeService.COLLECTION and ticket.ticket_type != 'collection'):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"TXID of wrong ticket type")

    file_bytes = await search_file_in_local_cache(reg_ticket_txid=reg_ticket_txid)
    not_locally_cached = not file_bytes

    if not file_bytes:
        file_bytes = await wn.get_file_from_pastel(reg_ticket_txid=reg_ticket_txid, wn_service=service)

    if not file_bytes and throw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found")

    # cache file in local storage and IPFS
    if file_bytes and not_locally_cached:
        await store_file_into_local_cache(reg_ticket_txid=reg_ticket_txid, file_bytes=file_bytes)

    return file_bytes


# search_gateway_file searches for file in 1) local cache; 2) Pastel network; 3) IPFS
# Is used to search for files processed by Gateway: Cascade file, Sense dd data and NFT file
async def search_nft_dd_result_gateway(*, db, task_from_db, update_task_in_db_func) -> bytes:

    if task_from_db.process_status not in [DbStatus.DONE.value]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found")

    try:
        return await search_nft_dd_result(db=db, task_from_db=task_from_db,
                                          update_task_in_db_func=update_task_in_db_func)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found")


# search_nft_dd_result_pastel searches for file in 1) local cache; 2) Pastel network
# Is used to search for files processed by Gateway: Cascade file, Sense dd data and NFT file
async def search_nft_dd_result_pastel(*, reg_ticket_txid: str, throw=True) -> bytes:

    dd_data = await search_file_in_local_cache(reg_ticket_txid=reg_ticket_txid, extra_suffix=".dd")
    not_locally_cached = not dd_data

    if not dd_data:
        dd_data = await wn.get_nft_dd_result_from_pastel(reg_ticket_txid=reg_ticket_txid)

    if not dd_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dupe detection data is not found")

    if isinstance(dd_data, dict):
        dd_bytes = json.dumps(dd_data).encode('utf-8')
    elif isinstance(dd_data, bytes):
        dd_bytes = dd_data
    elif isinstance(dd_data, str):
        dd_bytes = dd_data.encode('utf-8')
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dupe detection data is not found")

    # cache file in local storage only
    if not_locally_cached:
        await store_file_into_local_cache(reg_ticket_txid=reg_ticket_txid,
                                          file_bytes=dd_bytes,
                                          extra_suffix=".dd")
    return dd_bytes


async def get_all_reg_ticket_from_request(*, gateway_request_id, tasks_from_db,
                                          service_type: str,
                                          get_registration_ticket_lambda):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for task_from_db in tasks_from_db:
            ticket = await get_registration_ticket_lambda(task_from_db.reg_ticket_txid)
            # convert to bytes
            file_bytes = json.dumps(ticket, indent=2).encode('utf-8')
            zip_file.writestr(f"{task_from_db.original_file_name}-{service_type}-reg-ticket.json", file_bytes)
    return await stream_file(file_bytes=zip_buffer.getvalue(),
                             original_file_name=f"{gateway_request_id}-{service_type}-registration-tickets.zip",
                             content_type="application/zip")


async def stream_file(*, file_bytes, original_file_name: str, content_type: str = "application/x-binary"):

    response = StreamingResponse(iter([file_bytes]),
                                 media_type=content_type
                                 )

    try:
        original_file_name.encode('latin-1')
    except UnicodeEncodeError:
        original_file_name = original_file_name.encode('latin-1', 'replace')
    response.headers["Content-Disposition"] = f"attachment; filename={original_file_name}"
    return response


async def get_all_sense_or_nft_dd_data_from_request(*, tasks_from_db, gateway_request_id, search_data_lambda, file_suffix, parse=False):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for task_from_db in tasks_from_db:
            raw_file_bytes = await search_data_lambda(task_from_db)
            if parse:
                file_bytes = await parse_dd_data(raw_file_bytes, False)
                if not file_bytes:
                    file_bytes = raw_file_bytes
            else:
                file_bytes = raw_file_bytes
            # convert to bytes
            # file_bytes = json.dumps(ticket, indent=2).encode('utf-8')
            zip_file.writestr(f"{task_from_db.original_file_name}-{file_suffix}.json", file_bytes)
    return await stream_file(file_bytes=zip_buffer.getvalue(),
                             original_file_name=f"{gateway_request_id}-{file_suffix}.zip",
                             content_type="application/zip")


async def get_all_sense_or_nft_dd_data_for_pastelid(*, pastel_id: str, ticket_type: str, search_data_lambda, parse=False):
    registration_ticket_txids = await get_reg_txids_by_pastel_id(pastel_id=pastel_id, ticket_type=ticket_type)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for txid in registration_ticket_txids:
            try:
                raw_file_bytes = await search_data_lambda(txid)
            except Exception as e:
                logger.error(f"Error getting sense data for txid={txid}: {e}")
                continue
            if not raw_file_bytes:
                continue
            if parse:
                file_bytes = await parse_dd_data(raw_file_bytes, False)
                if not file_bytes:
                    file_bytes = raw_file_bytes
            else:
                file_bytes = raw_file_bytes
            # convert to bytes
            # file_bytes = json.dumps(ticket, indent=2).encode('utf-8')
            zip_file.writestr(f"{txid}-sense-data.json", file_bytes)
    return await stream_file(file_bytes=zip_buffer.getvalue(),
                             original_file_name=f"{pastel_id}-sense-data.zip",
                             content_type="application/zip")


async def get_registration_action_ticket(ticket_txid, service: wn.WalletNodeService):
    expected_ticket_type = "action-reg"

    if service == wn.WalletNodeService.CASCADE:
        expected_action_type = "cascade"
    elif service == wn.WalletNodeService.SENSE:
        expected_action_type = "sense"
    else:
        raise HTTPException(status_code=501, detail=f"Invalid service type - {service}")

    try:
        reg_ticket = psl.call("tickets", ['get', ticket_txid])   # can throw exception here
    except psl.PasteldException as e:
        raise HTTPException(status_code=404, detail=f"{expected_action_type} registration ticket not found - {e}")
    except HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to get {expected_action_type} activation ticket - {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Failed to get {expected_action_type} registration ticket - {e}")

    return await psl.parse_registration_action_ticket(reg_ticket, expected_ticket_type, [expected_action_type])


async def get_activation_ticket(ticket_txid, service: wn.WalletNodeService):
    if service == wn.WalletNodeService.CASCADE:
        expected_ticket_type = "action-act"
        expected_action_type = "cascade"
    elif service == wn.WalletNodeService.SENSE:
        expected_ticket_type = "action-act"
        expected_action_type = "sense"
    elif service == wn.WalletNodeService.NFT:
        expected_ticket_type = "nft-act"
        expected_action_type = "nft"
    else:
        raise HTTPException(status_code=501, detail=f"Invalid service type - {service}")

    try:
        act_ticket = psl.call("tickets", ['get', ticket_txid])   # can throw exception here
    except psl.PasteldException as e:
        raise HTTPException(status_code=501, detail=f"{expected_action_type} activation ticket not found - {e}")
    except HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to get {expected_action_type} activation ticket - {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Failed to get {expected_action_type} activation ticket - {e}")

    if not act_ticket or \
            "ticket" not in act_ticket or \
            "type" not in act_ticket["ticket"]:
        raise HTTPException(status_code=501, detail=f"Invalid {expected_action_type} activation ticket")

    if act_ticket["ticket"]["type"] != expected_ticket_type:
        raise HTTPException(status_code=501,
                            detail=f'Invalid {expected_action_type} activation ticket type - '
                                   f'{act_ticket["ticket"]["type"]}')

    return act_ticket


async def get_registration_nft_ticket(ticket_txid):
    try:
        reg_ticket = psl.call("tickets", ['get', ticket_txid])   # can throw exception here
    except psl.PasteldException as e:
        raise HTTPException(status_code=404, detail=f"NFT registration ticket not found - {e}")
    except HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to get NFT registration ticket - {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Failed to get NFT registration ticket - {e}")

    return await psl.parse_registration_nft_ticket(reg_ticket)


async def parse_dd_data(raw_bytes: bytes, throw=True) -> str | None:
    try:
        dd_data_json = json.loads(raw_bytes)
    except Exception as e:
        logger.error(f"Invalid sense data - {e}")
        if throw:
            raise HTTPException(status_code=501, detail=f"Invalid sense data - {e}")
        else:
            return None

    if not dd_data_json:
        logger.error(f"Invalid sense data")
        if throw:
            raise HTTPException(status_code=501, detail=f"Invalid sense data")
        else:
            return None

    if 'rareness_scores_table_json_compressed_b64' in dd_data_json:
        decode_decompress_item(dd_data_json,
                               'rareness_scores_table_json_compressed_b64')

    if 'internet_rareness' in dd_data_json:
        if 'rare_on_internet_summary_table_as_json_compressed_b64' in dd_data_json['internet_rareness']:
            decode_decompress_item(dd_data_json['internet_rareness'],
                                   'rare_on_internet_summary_table_as_json_compressed_b64')

        if 'rare_on_internet_graph_json_compressed_b64' in dd_data_json['internet_rareness']:
            decode_decompress_item(dd_data_json['internet_rareness'],
                                   'rare_on_internet_graph_json_compressed_b64')

        if 'alternative_rare_on_internet_dict_as_json_compressed_b64' in dd_data_json['internet_rareness']:
            decode_decompress_item(dd_data_json['internet_rareness'],
                                   'alternative_rare_on_internet_dict_as_json_compressed_b64')

    return json.dumps(dd_data_json)


def decode_decompress_item(json_object: dict, key: str):
    if json_object[key] is None or json_object[key] == "" or json_object[key] == "NA":
        return
    compressed_value = base64.b64decode(json_object[key])
    if compressed_value:
        decompressed_value = zstd.decompress(compressed_value)
        if decompressed_value:
            try:
                decompressed_json = json.loads(decompressed_value)
                json_object[key] = decompressed_json
            except Exception as e:
                logger.error(f"Invalid sense data - {e}")


async def get_reg_txid_by_act_txid(act_txid: str) -> str:
    try:
        act_ticket = psl.call("tickets", ['get', act_txid])   # can throw exception here
    except psl.PasteldException as e:
        raise HTTPException(status_code=501, detail=f"Action Activation ticket not found - {e}")
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Failed to get action activation ticket - {e}")
    if not act_ticket or \
            'ticket' not in act_ticket or \
            'reg_txid' not in act_ticket['ticket']:
        raise HTTPException(status_code=501, detail=f"Invalid action activation ticket")

    return act_ticket['ticket']['reg_txid']


async def get_reg_txids_by_pastel_id(pastel_id: str, ticket_type: str) -> List[str]:
    txids = []
    try:
        reg_tickets = psl.call("tickets", ['find', ticket_type, pastel_id])   # can throw exception here
    except psl.PasteldException as e:
        raise HTTPException(status_code=501, detail=f"Action registration ticket not found - {e}")
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Failed to get action registration ticket - {e}")

    for reg_ticket in reg_tickets:
        if 'txid' in reg_ticket:
            txids.append(reg_ticket['txid'])

    return txids


async def get_public_file(db, ticket_type: str, registration_ticket_txid: str, wn_service: wn.WalletNodeService):
    shadow_ticket = crud.reg_ticket.get_by_reg_ticket_txid_and_type(
        db=db,
        txid=registration_ticket_txid,
        ticket_type=ticket_type)
    if not shadow_ticket:
        # reg_ticket = await common.get_registration_action_ticket(registration_ticket_txid, wn_service)
        raise HTTPException(status_code=404, detail="File not found")
    if not shadow_ticket.is_public:
        raise HTTPException(status_code=403, detail="Non authorized access to file")

    file_bytes = await search_pastel_file(reg_ticket_txid=registration_ticket_txid, service=wn_service)
    return await stream_file(file_bytes=file_bytes, original_file_name=f"{shadow_ticket.file_name}")


async def compute_hash(upload_file: UploadFile, chunk_size: int = 8192):
    sha3_256_hash = hashlib.sha3_256()

    # Read the file in chunks
    while True:
        chunk = await upload_file.read(chunk_size)
        if not chunk:
            break
        sha3_256_hash.update(chunk)
    result = sha3_256_hash.hexdigest()

    upload_file.file.seek(0)
    return result


async def check_file_is_not_empty(file: UploadFile) -> schemas.ResultRegistrationResult | None:
    if file.filename == "":
        return schemas.ResultRegistrationResult(
            result_status=schemas.Status.ERROR,
            file_name=file.filename,
            file_type=file.content_type,
            status_messages=["File name is empty"],
        )
    if file.content_type is None:
        return schemas.ResultRegistrationResult(
            result_status=schemas.Status.ERROR,
            file_name=file.filename,
            file_type=file.content_type,
            status_messages=["File is empty"],
        )
    content = await file.read(1)
    await file.seek(0)  # reset file pointer to the beginning
    if len(content) == 0:
        return schemas.ResultRegistrationResult(
            result_status=schemas.Status.ERROR,
            file_name=file.filename,
            file_type=file.content_type,
            status_messages=["File is empty"],
        )

    return None


async def check_image(file: UploadFile, db,
                      wn_service: wn.WalletNodeService) -> schemas.ResultRegistrationResult | None:
    if (
            ("image/jpeg" not in file.content_type) and
            ("image/png" not in file.content_type) and
            ("image/webp" not in file.content_type)
    ):
        return schemas.ResultRegistrationResult(
            result_status=schemas.Status.ERROR,
            file_name=file.filename,
            file_type=file.content_type,
            status_messages=["File type not supported"],
        )

    if wn_service == wn.WalletNodeService.NFT or wn_service == wn.WalletNodeService.SENSE:
        image_hash = await compute_hash(file)
        tickets = crud.reg_ticket.get_by_hash(db=db, data_hash_as_hex=image_hash)
        for ticket in tickets:
            if ticket.ticket_type == "sense" or ticket.ticket_type == "nft":
                message = {"error": "This file has already been registered",
                           "reg_ticket_txid": tickets[0].reg_ticket_txid}
                return schemas.ResultRegistrationResult(
                    result_status=schemas.Status.ERROR,
                    file_name=file.filename,
                    file_type=file.content_type,
                    status_messages=[message],
                )

    return None


async def transfer_ticket(db, result_id, user_id, pastel_id,
                          get_result_func, update_func):

    await check_pastelid_for_transfer(db=db, pastel_id=pastel_id, user_id=user_id)

    task_from_db = get_result_func(db=db, result_id=result_id, owner_id=user_id)
    if not task_from_db:
        raise HTTPException(status_code=404, detail="gateway_result not found")

    if task_from_db.offer_ticket_intended_rcpt_pastel_id:
        raise HTTPException(status_code=404, detail=f"Ticket already transferred to "
                                                    f"{task_from_db.offer_ticket_intended_rcpt_pastel_id}")

    offer_ticket = await psl.create_offer_ticket(task_from_db,
                                                 settings.PASTEL_ID, settings.PASTEL_ID_PASSPHRASE, pastel_id)
    if offer_ticket and 'txid' in offer_ticket and offer_ticket['txid']:
        upd = {"offer_ticket_txid": offer_ticket['txid'],
               "offer_ticket_intended_rcpt_pastel_id": pastel_id,
               "updated_at": datetime.utcnow()}
        update_func(db=db, db_obj=task_from_db, obj_in=upd)

    return offer_ticket

# import asyncio
#
# async def read_file(file_path):
#     with open(file_path, 'r') as file:
#         contents = await file.read()
#         return contents
#
# async def run():
#     task1 = asyncio.create_task(read_file('/path/to/first/file'))
#     task2 = asyncio.create_task(read_file('/path/to/second/file'))
#
#     done, pending = await asyncio.wait([task1, task2], return_when=asyncio.FIRST_COMPLETED)
#
#     for task in pending:
#         task.cancel()
#
#     result = await done.pop().result()
#
#     return result
#
# if __name__ == '__main__':
#     loop = asyncio.get_event_loop()
#     result = loop.run_until_complete(run())
#     print(result)
