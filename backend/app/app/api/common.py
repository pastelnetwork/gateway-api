import asyncio
import uuid
import base64
import logging
from typing import List
from datetime import datetime

import requests
import ipfshttpclient

from fastapi import UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse

from app.utils.filestorage import LocalFile
from app import schemas
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


async def get_file_from_pastel(*, reg_ticket_txid, service: wn.WalletNodeService):
    file_bytes = None
    wn_resp = wn.call(False,
                      service,
                      f'download?pid={settings.PASTEL_ID}&txid={reg_ticket_txid}',
                      {},
                      [],
                      {'Authorization': settings.PASSPHRASE, },
                      "file", "", True)

    if not wn_resp:
        if service == wn.WalletNodeService.SENSE:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pastel file not found")
    elif not isinstance(wn_resp, requests.models.Response):
        file_bytes = base64.b64decode(wn_resp)
        if not file_bytes:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Pastel file's incorrect")
    else:
        logging.error(wn_resp.text)
    return file_bytes


async def search_file(*, task_from_db, service: wn.WalletNodeService):
    file_bytes = None
    if service == wn.WalletNodeService.CASCADE and task_from_db.pastel_id != settings.PASTEL_ID:
        logging.error("Backend does not have correct Pastel ID")
    elif task_from_db.ticket_status == 'DONE' or task_from_db.ticket_status == 'SUCCESS':
        file_bytes = await get_file_from_pastel(reg_ticket_txid=task_from_db.reg_ticket_txid, service=service)
    if service == wn.WalletNodeService.CASCADE and not file_bytes:
        if task_from_db.ipfs_link:
            try:
                ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
                file_bytes = ipfs_client.cat(task_from_db.ipfs_link)
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"IPFS file not found")

            if not file_bytes:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"IPFS file not found")
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pastel file not found")

    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found")

    return file_bytes


async def stream_file(*, file_bytes, original_file_name: str):

    response = StreamingResponse(iter([file_bytes]),
                                 media_type="application/x-binary"
                                 )
    response.headers["Content-Disposition"] = f"attachment; filename={original_file_name}"
    return response


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
