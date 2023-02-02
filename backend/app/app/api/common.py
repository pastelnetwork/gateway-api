import asyncio
import uuid
import base64
import logging
from typing import List

import requests
import ipfshttpclient

from fastapi import UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse

from app.utils.filestorage import LocalFile
from app import schemas
from app.celery_tasks.pastel_tasks import get_celery_task_info
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
    results = schemas.RequestResult(work_id=request_id, tickets=[])
    for file in files:
        lf = LocalFile(file.filename, file.content_type)
        result_id = str(uuid.uuid4())
        await lf.save(file)
        res = (
                worker.register_file.s(lf, request_id, result_id, user_id) |
                worker.preburn_fee.s() |
                worker.process.s()
        ).apply_async()
        reg_result = schemas.ResultRegistrationResult(
            file_name=file.filename,
            result_id=result_id,
            result_status=res.result_status,
        )
        results.results.append(reg_result)

    return results


async def check_result_registration_status(result_from_db, service: wn.WalletNodeService) \
        -> schemas.ResultRegistrationResult:
    if result_from_db.ticket_status:
        if result_from_db.ticket_status == 'STARTED':
            result_registration_status = 'PENDING'
        elif result_from_db.ticket_status == 'DONE':
            result_registration_status = 'SUCCESS'
        elif result_from_db.ticket_status == 'DEAD':
            result_registration_status = 'FAILED'
        else:
            celery_task_info = get_celery_task_info(result_from_db.ticket_status)
            result_registration_status = celery_task_info['celery_task_status']
    else:
        result_registration_status = 'UNKNOWN'
    wn_task_status = ''
    if result_from_db.ticket_status != 'DONE' and result_from_db.ticket_status != 'DEAD' and result_from_db.wn_task_id:
        wn_task_status = wn.call(False,
                                 service,
                                 f'{result_from_db.wn_task_id}/history',
                                 {}, [], {},
                                 "", "")
        if wn_task_status and 'message' in wn_task_status:
            result_registration_status = wn_task_status['message']
        else:
            for step in wn_task_status:
                if step['status'] == 'Registration Rejected':
                    result_registration_status = 'ERROR' if settings.RETURN_DETAILED_WN_ERROR else 'PENDING'
                    break
                if step['status'] == 'Registration Completed':
                    result_registration_status = 'SUCCESS'
                    break
    reg_result = schemas.ResultRegistrationResult(
        file_name=result_from_db.original_file_name,
        result_id=result_from_db.ticket_id,
        result_status=result_registration_status,
    )
    if result_registration_status != 'ERROR' and result_registration_status != 'FAILED':
        reg_result.registration_ticket_txid = result_from_db.registration_ticket_txid
        reg_result.activation_ticket_txid = result_from_db.activation_ticket_txid
        if service != wn.WalletNodeService.SENSE:
            reg_result.ipfs_link = f'https://ipfs.io/ipfs/{result_from_db.ipfs_link}'
            reg_result.aws_link = result_from_db.aws_link
            reg_result.other_links = result_from_db.other_links
    else:
        reg_result.error = wn_task_status
    return reg_result


async def parse_users_requests(results, service: wn.WalletNodeService) -> List[schemas.RequestResult]:
    gw_requests = {}
    for result in results:
        if result.request_id in gw_requests:
            request = gw_requests[result.request_id]
        else:
            request = schemas.RequestResult(request_id=result.request_id, results=[])

        result_registration_result = await check_result_registration_status(result, service)
        request.results.append(result_registration_result)
        gw_requests[result.request_id] = request
    return list(gw_requests.values())


async def parse_user_request(results_in_request, request_id, service: wn.WalletNodeService) -> schemas.RequestResult:
    results = schemas.RequestResult(request_id=request_id, results=[])
    for result in results_in_request:
        result_registration_result = await check_result_registration_status(result, service)
        results.results.append(result_registration_result)
    return results


async def process_websocket_for_result(websocket, results, service: wn.WalletNodeService, request_id: str = None):
    while True:
        all_failed = True
        all_success = True
        results_json = []
        for result in results:
            result = await check_result_registration_status(result, service)
            if result is not None:
                results_json.append(
                    {
                        'ticket_id': result.result_id,
                        'status': result.result_status,
                    }
                )
            all_failed &= result.result_status == "FAILED"
            all_success &= result.result_status == "SUCCESS"

        if request_id:
            result_json = {
                'request_id': request_id,
                'request_status': 'FAILED' if all_failed else 'SUCCESS' if all_success else 'PENDING',
                'results': results_json,
            }
        else:
            result_json = results_json[0]

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


async def search_file(*, result, service: wn.WalletNodeService):
    file_bytes = None
    if service == wn.WalletNodeService.CASCADE and result.pastel_id != settings.PASTEL_ID:
        logging.error("Backend does not have correct Pastel ID")
    elif result.ticket_status == 'DONE' or result.ticket_status == 'SUCCESS':
        file_bytes = await get_file_from_pastel(reg_ticket_txid=result.registration_ticket_txid, service=service)
    if service == wn.WalletNodeService.CASCADE and not file_bytes:
        if result.ipfs_link:
            try:
                ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
                file_bytes = ipfs_client.cat(result.ipfs_link)
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


async def create_offer_ticket(result, pastel_id, service: wn.WalletNodeService):
    offer_ticket = psl.call('tickets', ['register', 'offer',
                                        result.activation_ticket_txid,
                                        1,
                                        settings.PASTEL_ID,
                                        settings.PASSPHRASE,
                                        0, 0, 1, "",
                                        pastel_id],
                            )
    return offer_ticket
