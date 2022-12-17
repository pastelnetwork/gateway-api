import uuid
import base64
import logging
from typing import List

import requests
import ipfshttpclient

from fastapi import Depends, UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse

from sqlalchemy.orm import Session

import app.db.session as session
from app.utils.filestorage import LocalFile
from app import crud, models, schemas
from app.celery_tasks.pastel_tasks import get_celery_task_info
from app.core.config import settings
from app.utils import walletnode as wn


async def do_works(
        *,
        worker,
        files: List[UploadFile],
        current_user: models.User
) -> schemas.WorkResult:
    work_id = str(uuid.uuid4())
    results = schemas.WorkResult(work_id=work_id, tickets=[])
    for file in files:
        lf = LocalFile(file.filename, file.content_type)
        ticket_id = str(uuid.uuid4())
        await lf.save(file)
        res = (
                worker.register_file.s(lf, work_id, ticket_id, current_user.id) |
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
            status = 'PENDING'
        elif ticket.ticket_status == 'DONE':
            status = 'SUCCESS'
        elif ticket.ticket_status == 'DEAD':
            status = 'FAILED'
        else:
            task_info = get_celery_task_info(ticket.ticket_status)
            status = task_info['celery_task_status']
    else:
        status = 'UNKNOWN'
    wn_task_status = ''
    if ticket.ticket_status != 'DONE':
        wn_task_status = wn.call(False,
                                 service,
                                 f'{ticket.wn_task_id}/history',
                                 {}, [], {},
                                 "", "")
        for step in wn_task_status:
            if step['status'] == 'Registration Rejected':
                status = 'ERROR' if settings.RETURN_DETAILED_WN_ERROR else 'PENDING'
                break
            if step['status'] == 'Registration Completed':
                status = 'DONE'
                break
    reg_result = schemas.TicketRegistrationResult(
        file=ticket.original_file_name,
        ticket_id=ticket.ticket_id,
        status=status,
    )
    if status != 'ERROR' and status != 'FAILED':
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


async def get_file(
        *,
        ticket_id: str,
        db: Session = Depends(session.get_db_session),
        service: wn.WalletNodeService,
):
    ticket = crud.cascade.get_by_ticket_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    file_bytes = None
    if service == wn.WalletNodeService.CASCADE and ticket.pastel_id != settings.PASTEL_ID:
        logging.error("Backend does not have correct Pastel ID")
    else:
        wn_resp = wn.call(False,
                          service,
                          f'download?pid={settings.PASTEL_ID}&txid={ticket.reg_ticket_txid}',
                          {},
                          [],
                          { 'Authorization': settings.PASSPHRASE,},
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
            ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
            file_bytes = ipfs_client.cat(ticket.ipfs_link)
            if not file_bytes:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"IPFS file not found")
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pastel file not found")

    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found")

    response = StreamingResponse(iter([file_bytes]),
                                 media_type="application/x-binary"
                                 )
    response.headers["Content-Disposition"] = f"attachment; filename={ticket.original_file_name}"
    return response
