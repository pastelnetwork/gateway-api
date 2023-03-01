import asyncio
import json
import zipfile
import io
import os
import uuid
import base64
import logging
from typing import List
from datetime import datetime

import requests
import ipfshttpclient
import zstd as zstd

from fastapi import UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse

from app.utils.filestorage import LocalFile
from app import schemas, crud
from app.core.config import settings
from app.utils import walletnode as wn
import app.utils.pasteld as psl


async def process_request(
        *,
        worker,
        files: List[UploadFile],
        user_id: int
) -> schemas.RequestResult:
    request_id = str(uuid.uuid4())
    request_result = schemas.RequestResult(
        request_id=request_id,
        request_status=schemas.Status.PENDING,
        results=[]
    )
    for file in files:
        lf = LocalFile(file.filename, file.content_type)
        result_id = str(uuid.uuid4())
        await lf.save(file)
        _ = (
                worker.register_file.s(lf, request_id, result_id, user_id) |
                worker.preburn_fee.s() |
                worker.process.s()
        ).apply_async()
        reg_result = schemas.ResultRegistrationResult(
            file_name=file.filename,
            file_type=file.content_type,
            result_id=result_id,
            result_status=schemas.Status.PENDING,
            created_at=datetime.utcnow(),
            last_updated_at=datetime.utcnow(),
        )
        request_result.results.append(reg_result)

    return request_result


async def check_result_registration_status(task_from_db, service: wn.WalletNodeService) \
        -> schemas.ResultRegistrationResult:

    result_registration_status = schemas.Status.UNKNOWN
    if task_from_db.ticket_status:
        if task_from_db.ticket_status == 'STARTED':
            result_registration_status = schemas.Status.PENDING
        elif task_from_db.ticket_status == 'DONE':
            result_registration_status = schemas.Status.SUCCESS
        elif task_from_db.ticket_status == 'DEAD':
            result_registration_status = schemas.Status.FAILED

    wn_task_status = ''
    if (result_registration_status == schemas.Status.UNKNOWN or
        result_registration_status == schemas.Status.PENDING) \
            and task_from_db.wn_task_id:
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
    reg_result = schemas.ResultRegistrationResult(
        file_name=task_from_db.original_file_name,
        file_type=task_from_db.original_file_content_type,
        result_id=task_from_db.ticket_id,
        created_at=task_from_db.created_at,
        last_updated_at=task_from_db.updated_at,
        result_status=result_registration_status,
    )
    if result_registration_status != schemas.Status.ERROR and result_registration_status != schemas.Status.FAILED:
        reg_result.registration_ticket_txid = task_from_db.reg_ticket_txid
        reg_result.activation_ticket_txid = task_from_db.act_ticket_txid
        if service != wn.WalletNodeService.SENSE:
            reg_result.ipfs_link = f'https://ipfs.io/ipfs/{task_from_db.ipfs_link}'
            reg_result.aws_link = task_from_db.aws_link
            reg_result.other_links = task_from_db.other_links
    else:
        reg_result.error = wn_task_status
    return reg_result


async def parse_users_requests(tasks_from_db, service: wn.WalletNodeService) -> List[schemas.RequestResult]:
    gw_requests = {}
    all_failed_map = {}
    all_success_map = {}
    for task_from_db in tasks_from_db:
        if task_from_db.work_id in gw_requests:
            request = gw_requests[task_from_db.work_id]
        else:
            request = schemas.RequestResult(request_id=task_from_db.work_id,
                                            request_status=schemas.Status.UNKNOWN,
                                            results=[])
            all_failed_map[task_from_db.work_id] = True
            all_success_map[task_from_db.work_id] = True

        result_registration_result = await check_result_registration_status(task_from_db, service)
        request.results.append(result_registration_result)
        all_failed_map[task_from_db.work_id] &= result_registration_result.result_status == schemas.Status.FAILED
        all_success_map[task_from_db.work_id] &= result_registration_result.result_status == schemas.Status.SUCCESS
        request.request_status = schemas.Status.FAILED if all_failed_map[task_from_db.work_id] \
            else schemas.Status.SUCCESS if all_success_map[task_from_db.work_id] \
            else schemas.Status.PENDING
        gw_requests[task_from_db.work_id] = request
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


async def get_file_from_pastel(*, reg_ticket_txid, service: wn.WalletNodeService, throw: bool = True):
    file_bytes = None
    wn_resp = wn.call(False,
                      service,
                      f'download?pid={settings.PASTEL_ID}&txid={reg_ticket_txid}',
                      {},
                      [],
                      {'Authorization': settings.PASSPHRASE, },
                      "file", "", True)

    if not wn_resp:
        if service == wn.WalletNodeService.SENSE and throw:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pastel file not found")
    elif not isinstance(wn_resp, requests.models.Response):
        file_bytes = base64.b64decode(wn_resp)
        if not file_bytes:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Pastel file's incorrect")
    else:
        logging.error(wn_resp.text)
    return file_bytes


async def search_file_in_local_cache(*, reg_ticket_txid) -> bytes:
    cached_result_file = \
        f"{settings.FILE_STORAGE}/{settings.FILE_STORAGE_FOR_RESULTS_SUFFIX}/{reg_ticket_txid}"
    try:
        with open(cached_result_file, 'rb') as f:
            return f.read()
    except Exception as e:
        logging.error(f"File not found in the local storage - {e}")


async def store_file_into_local_cache(*, reg_ticket_txid, file_bytes):
    cached_result_file = \
        f"{settings.FILE_STORAGE}/{settings.FILE_STORAGE_FOR_RESULTS_SUFFIX}/{reg_ticket_txid}"
    try:
        if not os.path.exists(f"{settings.FILE_STORAGE}/{settings.FILE_STORAGE_FOR_RESULTS_SUFFIX}"):
            os.makedirs(f"{settings.FILE_STORAGE}/{settings.FILE_STORAGE_FOR_RESULTS_SUFFIX}")

        with open(cached_result_file, 'wb') as f:
            f.write(file_bytes)
    except Exception as e:
        logging.error(f"File not saved in the local storage - {e}")


async def add_local_file_into_ipfs(*, reg_ticket_txid) -> str:
    cached_result_file = \
        f"{settings.FILE_STORAGE}/{settings.FILE_STORAGE_FOR_RESULTS_SUFFIX}/{reg_ticket_txid}"
    try:
        ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        res = ipfs_client.add(cached_result_file)
        return res["Hash"]
    except Exception as e:
        logging.error(f"File not saved in the IPFS - {e}")


async def search_gateway_file(*, db, task_from_db, service: wn.WalletNodeService, update_task_in_db_func) -> bytes:

    if service == wn.WalletNodeService.SENSE and task_from_db.ticket_status not in ['DONE', 'SUCCESS']:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found")

    file_bytes = None
    if service == wn.WalletNodeService.CASCADE \
            and task_from_db.pastel_id != settings.PASTEL_ID:  # and not task_from_db.public:
        logging.error("Backend does not have correct Pastel ID")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=f"Only owner can download cascade file")

    file_bytes = await search_file_in_local_cache(reg_ticket_txid=task_from_db.reg_ticket_txid)
    not_locally_cached = not file_bytes

    if not file_bytes and task_from_db.ipfs_link:
        try:
            ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
            file_bytes = ipfs_client.cat(task_from_db.ipfs_link)
        except Exception as e:
            logging.error(f"File not found in the IPFS - {e}")

    if not file_bytes and task_from_db.ticket_status in ['DONE', 'SUCCESS']:
        file_bytes = await get_file_from_pastel(reg_ticket_txid=task_from_db.reg_ticket_txid, service=service)

    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found")

    # cache file in local storage and IPFS
    if not_locally_cached:
        await store_file_into_local_cache(reg_ticket_txid=task_from_db.reg_ticket_txid, file_bytes=file_bytes)

    if not task_from_db.ipfs_link:
        ipfs_link = await add_local_file_into_ipfs(reg_ticket_txid=task_from_db.reg_ticket_txid)
        if ipfs_link:
            upd = {"ipfs_link": ipfs_link, "updated_at": datetime.utcnow()}
            update_task_in_db_func(db, db_obj=task_from_db, obj_in=upd)

    return file_bytes


async def search_pastel_file(*, reg_ticket_txid: str, service: wn.WalletNodeService, throw=True) -> bytes:

    file_bytes = await search_file_in_local_cache(reg_ticket_txid=reg_ticket_txid)
    not_locally_cached = not file_bytes

    if not file_bytes:
        file_bytes = await get_file_from_pastel(reg_ticket_txid=reg_ticket_txid, service=service, throw=throw)

    if not file_bytes and throw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found")

    # cache file in local storage and IPFS
    if file_bytes and not_locally_cached:
        await store_file_into_local_cache(reg_ticket_txid=reg_ticket_txid, file_bytes=file_bytes)

    return file_bytes


async def get_all_reg_ticket_from_request(*, gateway_request_id, tasks_from_db,
                                          service_type: str, service: wn.WalletNodeService):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for task_from_db in tasks_from_db:
            ticket = await get_registration_action_ticket(
                task_from_db.reg_ticket_txid,
                service)
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


async def get_all_sense_data_from_request(*, db, tasks_from_db, gateway_request_id, parse=False):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for task_from_db in tasks_from_db:
            raw_file_bytes = await search_gateway_file(db=db,
                                                       task_from_db=task_from_db,
                                                       service=wn.WalletNodeService.SENSE,
                                                       update_task_in_db_func=crud.sense.update)
            if parse:
                file_bytes = await parse_sense_data(raw_file_bytes, False)
                if not file_bytes:
                    file_bytes = raw_file_bytes
            else:
                file_bytes = raw_file_bytes
            # convert to bytes
            # file_bytes = json.dumps(ticket, indent=2).encode('utf-8')
            zip_file.writestr(f"{task_from_db.original_file_name}-sense-data.json", file_bytes)
    return await stream_file(file_bytes=zip_buffer.getvalue(),
                             original_file_name=f"{gateway_request_id}-sense-data.zip",
                             content_type="application/zip")


async def get_all_sense_data_for_pastelid(*, pastel_id: str, parse=False):
    registration_ticket_txids = await get_reg_txids_by_pastel_id(pastel_id=pastel_id)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for txid in registration_ticket_txids:
            raw_file_bytes = await search_pastel_file(reg_ticket_txid=txid,
                                                      service=wn.WalletNodeService.SENSE,
                                                      throw=False)
            if not raw_file_bytes:
                continue
            if parse:
                file_bytes = await parse_sense_data(raw_file_bytes, False)
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


async def create_offer_ticket(task_from_db, pastel_id, service: wn.WalletNodeService):
    offer_ticket = psl.call('tickets', ['register', 'offer',
                                        task_from_db.act_ticket_txid,
                                        1,
                                        settings.PASTEL_ID,
                                        settings.PASSPHRASE,
                                        0, 0, 1, "",
                                        pastel_id],
                            )
    return offer_ticket


async def get_registration_action_ticket(ticket_txid, service: wn.WalletNodeService):
    expected_ticket_type = "action-reg"

    if service == wn.WalletNodeService.CASCADE:
        expected_action_type = "cascade"
    elif service == wn.WalletNodeService.SENSE:
        expected_action_type = "sense"
    else:
        raise HTTPException(status_code=501, detail=f"Invalid service type - {service}")

    try:
        reg_ticket = psl.call("tickets", ['get', ticket_txid])
    except psl.PasteldException as e:
        raise HTTPException(status_code=404, detail=f"{expected_action_type} registration ticket not found")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Failed to get {expected_action_type} registration ticket - {e}")

    if not reg_ticket or \
            "ticket" not in reg_ticket or \
            "action_ticket" not in reg_ticket["ticket"] or \
            "type" not in reg_ticket["ticket"] or \
            "action_type" not in reg_ticket["ticket"]:
        raise HTTPException(status_code=501, detail=f"Invalid {expected_action_type} registration ticket")

    if reg_ticket["ticket"]["type"] != expected_ticket_type:
        raise HTTPException(status_code=501,
                            detail=f'Invalid {expected_action_type} registration ticket type - '
                                   f'{reg_ticket["ticket"]["type"]}')

    if reg_ticket["ticket"]["action_type"] != expected_action_type:
        raise HTTPException(status_code=501,
                            detail=f'Invalid {expected_action_type} registration ticket action type - '
                                   f'{reg_ticket["ticket"]["action_type"]}')

    # Base64decode the ticket
    reg_ticket_action_ticket_str = base64.b64decode(reg_ticket["ticket"]["action_ticket"]).decode('utf-8')

    # Convert to json
    reg_ticket["ticket"]["action_ticket"] = json.loads(reg_ticket_action_ticket_str)

    if not reg_ticket["ticket"]["action_ticket"] or \
            "action_ticket_version" not in reg_ticket["ticket"]["action_ticket"] or \
            "action_type" not in reg_ticket["ticket"]["action_ticket"] or \
            "api_ticket" not in reg_ticket["ticket"]["action_ticket"]:
        raise HTTPException(status_code=501, detail=f"Failed to decode action_ticket in the "
                                                    f"{expected_action_type} registration ticket")
    if reg_ticket["ticket"]["action_ticket"]["action_type"] != expected_action_type:
        raise HTTPException(status_code=501,
                            detail=f'Invalid "app_ticket" in the {expected_action_type} '
                                   f'registration ticket action type - '
                                   f'{reg_ticket["ticket"]["action_type"]}')

    # ASCII85decode the api_ticket
    api_ticket_str = base64.a85decode(reg_ticket["ticket"]["action_ticket"]["api_ticket"])

    reg_ticket["ticket"]["action_ticket"]["api_ticket"] = json.loads(api_ticket_str)

    return reg_ticket


async def get_activation_action_ticket(ticket_txid, service: wn.WalletNodeService):
    expected_ticket_type = "action-act"

    if service == wn.WalletNodeService.CASCADE:
        expected_action_type = "cascade"
    elif service == wn.WalletNodeService.SENSE:
        expected_action_type = "sense"
    else:
        raise HTTPException(status_code=501, detail=f"Invalid service type - {service}")

    try:
        act_ticket = psl.call("tickets", ['get', ticket_txid])
    except psl.PasteldException as e:
        raise HTTPException(status_code=501, detail=f"{expected_action_type} activation ticket not found - {e}")
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


async def parse_sense_data(raw_bytes: bytes, throw=True) -> bytearray:
    try:
        sense_data_json = json.loads(raw_bytes)
    except Exception as e:
        logging.error(f"Invalid sense data - {e}")
        if throw:
            raise HTTPException(status_code=501, detail=f"Invalid sense data - {e}")
        else:
            return None

    if not sense_data_json:
        logging.error(f"Invalid sense data")
        if throw:
            raise HTTPException(status_code=501, detail=f"Invalid sense data")
        else:
            return None

    if 'rareness_scores_table_json_compressed_b64' in sense_data_json:
        decode_decompress_item(sense_data_json,
                               'rareness_scores_table_json_compressed_b64')

    if 'internet_rareness' in sense_data_json:
        if 'rare_on_internet_summary_table_as_json_compressed_b64' in sense_data_json['internet_rareness']:
            decode_decompress_item(sense_data_json['internet_rareness'],
                                   'rare_on_internet_summary_table_as_json_compressed_b64')

        if 'rare_on_internet_graph_json_compressed_b64' in sense_data_json['internet_rareness']:
            decode_decompress_item(sense_data_json['internet_rareness'],
                                   'rare_on_internet_graph_json_compressed_b64')

        if 'alternative_rare_on_internet_dict_as_json_compressed_b64' in sense_data_json['internet_rareness']:
            decode_decompress_item(sense_data_json['internet_rareness'],
                                   'alternative_rare_on_internet_dict_as_json_compressed_b64')

    return json.dumps(sense_data_json)


def decode_decompress_item(json_object: dict, key: str):
    compressed_value = base64.b64decode(json_object[key])
    if compressed_value:
        decompressed_value = zstd.decompress(compressed_value)
        if decompressed_value:
            try:
                decompressed_json = json.loads(decompressed_value)
                json_object[key] = decompressed_json
            except Exception as e:
                logging.error(f"Invalid sense data - {e}")


async def get_reg_txid_by_act_txid(act_txid: str) -> str:
    try:
        act_ticket = psl.call("tickets", ['get', act_txid])
    except psl.PasteldException as e:
        raise HTTPException(status_code=501, detail=f"Action Activation ticket not found - {e}")
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Failed to get action activation ticket - {e}")
    if not act_ticket or \
            'ticket' not in act_ticket or \
            'reg_txid' not in act_ticket['ticket']:
        raise HTTPException(status_code=501, detail=f"Invalid action activation ticket")

    return act_ticket['ticket']['reg_txid']


async def get_reg_txids_by_pastel_id(pastel_id: str) -> List[str]:
    txids = []
    try:
        reg_tickets = psl.call("tickets", ['find', 'action', pastel_id])
    except psl.PasteldException as e:
        raise HTTPException(status_code=501, detail=f"Action registration ticket not found - {e}")
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Failed to get action registration ticket - {e}")

    for reg_ticket in reg_tickets:
        if 'txid' in reg_ticket:
            txids.append(reg_ticket['txid'])

    return txids
