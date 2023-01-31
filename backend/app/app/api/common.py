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


async def do_works(
        *,
        worker,
        files: List[UploadFile],
        user_id: int
) -> schemas.WorkResult:
    work_id = str(uuid.uuid4())
    results = schemas.WorkResult(work_id=work_id, tickets=[])
    for file in files:
        lf = LocalFile(file.filename, file.content_type)
        ticket_id = str(uuid.uuid4())
        await lf.save(file)
        res = (
                worker.register_file.s(lf, work_id, ticket_id, user_id) |
                worker.preburn_fee.s() |
                worker.process.s()
        ).apply_async()
        reg_result = schemas.TicketRegistrationResult(
            file=file.filename,
            ticket_id=ticket_id,
            status=res.status,
        )
        results.tickets.append(reg_result)

    return results


async def check_ticket_registration_status(ticket, service: wn.WalletNodeService) -> schemas.TicketRegistrationResult:
    if ticket.ticket_status:
        if ticket.ticket_status == 'STARTED':
            registration_status = 'PENDING'
        elif ticket.ticket_status == 'DONE':
            registration_status = 'SUCCESS'
        elif ticket.ticket_status == 'DEAD':
            registration_status = 'FAILED'
        else:
            task_info = get_celery_task_info(ticket.ticket_status)
            registration_status = task_info['celery_task_status']
    else:
        registration_status = 'UNKNOWN'
    wn_task_status = ''
    if ticket.ticket_status != 'DONE' and ticket.ticket_status != 'DEAD' and ticket.wn_task_id:
        wn_task_status = wn.call(False,
                                 service,
                                 f'{ticket.wn_task_id}/history',
                                 {}, [], {},
                                 "", "")
        if wn_task_status and 'message' in wn_task_status:
            registration_status = wn_task_status['message']
        else:
            for step in wn_task_status:
                if step['status'] == 'Registration Rejected':
                    registration_status = 'ERROR' if settings.RETURN_DETAILED_WN_ERROR else 'PENDING'
                    break
                if step['status'] == 'Registration Completed':
                    registration_status = 'SUCCESS'
                    break
    reg_result = schemas.TicketRegistrationResult(
        file=ticket.original_file_name,
        ticket_id=ticket.ticket_id,
        status=registration_status,
    )
    if registration_status != 'ERROR' and registration_status != 'FAILED':
        reg_result.reg_ticket_txid = ticket.reg_ticket_txid
        reg_result.act_ticket_txid = ticket.act_ticket_txid
        if service != wn.WalletNodeService.SENSE:
            reg_result.ipfs_link = f'https://ipfs.io/ipfs/{ticket.ipfs_link}'
            reg_result.aws_link = ticket.aws_link
            reg_result.other_links = ticket.other_links
    else:
        reg_result.error = wn_task_status
    return reg_result


async def parse_users_works(tickets, service: wn.WalletNodeService) -> List[schemas.WorkResult]:
    works = {}
    for ticket in tickets:
        if ticket.work_id in works:
            work = works[ticket.work_id]
        else:
            work = schemas.WorkResult(work_id=ticket.work_id, tickets=[])

        ticket_result = await check_ticket_registration_status(ticket, service)
        work.tickets.append(ticket_result)
        works[ticket.work_id] = work
    return list(works.values())


async def parse_user_work(tickets_in_work, work_id, service: wn.WalletNodeService) -> schemas.WorkResult:
    results = schemas.WorkResult(work_id=work_id, tickets=[])
    for ticket in tickets_in_work:
        ticket_result = await check_ticket_registration_status(ticket, service)
        results.tickets.append(ticket_result)
    return results


async def process_websocket_for_tickets(websocket, tickets, service: wn.WalletNodeService, work_id: str = None):
    while True:
        all_failed = True
        all_success = True
        tickets_json = []
        for ticket in tickets:
            result = await check_ticket_registration_status(ticket, service)
            if result is not None:
                tickets_json.append(
                    {
                        'ticket_id': result.ticket_id,
                        'status': result.status,
                    }
                )
            all_failed &= result.status == "FAILED"
            all_success &= result.status == "SUCCESS"

        if work_id:
            result_json = {
                'work_id': work_id,
                'work_status': 'FAILED' if all_failed else 'SUCCESS' if all_success else 'PENDING',
                'tickets': tickets_json,
            }
        else:
            result_json = tickets_json[0]

        await websocket.send_json(result_json)
        if all_failed or all_success:
            break

        await asyncio.sleep(150)  # 2.5 minutes


async def get_file(
        *,
        ticket,
        service: wn.WalletNodeService,
        file_bytes=None
):
    if service == wn.WalletNodeService.CASCADE and ticket.pastel_id != settings.PASTEL_ID:
        logging.error("Backend does not have correct Pastel ID")
    elif ticket.ticket_status == 'DONE' or ticket.ticket_status == 'SUCCESS':
        wn_resp = wn.call(False,
                          service,
                          f'download?pid={settings.PASTEL_ID}&txid={ticket.reg_ticket_txid}',
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

    if service == wn.WalletNodeService.CASCADE and not file_bytes:
        if ticket.ipfs_link:
            try:
                ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
                file_bytes = ipfs_client.cat(ticket.ipfs_link)
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"IPFS file not found")

            if not file_bytes:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"IPFS file not found")
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pastel file not found")

    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found")

    response = StreamingResponse(iter([file_bytes]),
                                 media_type="application/x-binary"
                                 )

    if service == wn.WalletNodeService.SENSE:
        file_name = f"{ticket.original_file_name}.json"
    else:
        file_name = ticket.original_file_name

    response.headers["Content-Disposition"] = f"attachment; filename={file_name}"
    return response


import app.utils.pasteld as psl


async def create_offer_ticket(
        ticket,
        pastel_id,
        service: wn.WalletNodeService
) -> schemas.WorkResult:
    offer_ticket = psl.call('tickets', ['register', 'offer',
                                        ticket.act_ticket_txid,
                                        1,
                                        settings.PASTEL_ID,
                                        settings.PASSPHRASE,
                                        0, 0, 1, "",
                                        pastel_id],
                            )
    return offer_ticket
