import base64
import logging
import uuid

import requests
import ipfshttpclient
from fastapi import APIRouter, Depends, UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse

from typing import List
from sqlalchemy.orm import Session

import app.celery_tasks.cascade as cascade
from app.celery_tasks.base import get_celery_task_info
import app.db.session as session
from app.utils.filestorage import LocalFile
from app.api import deps
from app import models, crud, schemas
import app.utils.walletnode as wn
from app.core.config import settings

router = APIRouter()


@router.post("/", response_model=schemas.WorkResult, response_model_exclude_none=True)
async def do_work(
        *,
        files: List[UploadFile],
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.WorkResult:
    work_id = str(uuid.uuid4())
    results = schemas.WorkResult(work_id=work_id, tickets=[])
    for file in files:
        lf = LocalFile(file.filename, file.content_type)
        ticket_id = str(uuid.uuid4())
        await lf.save(file)
        res = (
                cascade.register_image.s(lf, work_id, ticket_id, current_user.id) |
                cascade.preburn_fee.s() |
                cascade.process.s()
        ).apply_async()
        reg_result = schemas.TicketRegistrationResult(
            file=file.filename,
            ticket_id=ticket_id,
            status=res.status,
        )
        results.tickets.append(reg_result)

    return results


@router.get("/works", response_model=List[schemas.WorkResult], response_model_exclude_none=True)
async def get_works(
        *,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.WorkResult]:
    """
    Return the status of the submitted Work
    """
    works = {}
    tickets = crud.cascade.get_multi_by_owner(db=db, owner_id=current_user.id)
    for ticket in tickets:
        if ticket.work_id in works:
            work = works[ticket.work_id]
        else:
            work = schemas.WorkResult(work_id=ticket.work_id, tickets=[])

        ticket_result = await check_ticket_registration_status(ticket)
        work.tickets.append(ticket_result)
        works[ticket.work_id] = work

    return list(works.values())


@router.get("/works/{work_id}", response_model=schemas.WorkResult, response_model_exclude_none=True)
async def get_work(
        *,
        work_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.WorkResult:
    """
    Return the status of the submitted Work
    """
    results = schemas.WorkResult(work_id=work_id, tickets=[])
    tickets_in_work = crud.cascade.get_all_in_work(db=db, work_id=work_id)
    for ticket in tickets_in_work:
        ticket_result = await check_ticket_registration_status(ticket)
        results.tickets.append(ticket_result)

    return results


@router.get("/tickets", response_model=List[schemas.TicketRegistrationResult], response_model_exclude_none=True)
async def get_tickets(
        *,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.TicketRegistrationResult]:
    results = []
    tickets = crud.cascade.get_multi_by_owner(db=db, owner_id=current_user.id)
    for ticket in tickets:
        ticket_result = await check_ticket_registration_status(ticket)
        results.append(ticket_result)
    return results


@router.get("/tickets/{ticket_id}", response_model=schemas.TicketRegistrationResult, response_model_exclude_none=True)
async def get_ticket(
        *,
        ticket_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.TicketRegistrationResult:
    ticket = crud.cascade.get_by_ticket_id(db=db, ticket_id=ticket_id)
    ticket_result = await check_ticket_registration_status(ticket)
    return ticket_result


async def check_ticket_registration_status(ticket) -> schemas.TicketRegistrationResult:
    if ticket.ticket_status:
        if ticket.ticket_status == 'STARTED':
            status = 'PENDING'
        elif ticket.ticket_status == 'DONE':
            status = 'SUCCESS'
        else:
            task_info = get_celery_task_info(ticket.ticket_status)
            status = task_info['celery_task_status']
    else:
        status = 'UNKNOWN'
    wn_task_status = ''
    if ticket.ticket_status != 'DONE':
        wn_task_status = wn.call(False,
                                 f'{ticket.wn_task_id}/history',
                                 {},
                                 [],
                                 {},
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
    if status != 'ERROR':
        reg_result.reg_ticket_txid = ticket.reg_ticket_txid
        reg_result.act_ticket_txid = ticket.act_ticket_txid
        reg_result.ipfs_link = f'https://ipfs.io/ipfs/{ticket.ipfs_link}'
        reg_result.aws_link = ticket.aws_link
        reg_result.other_links = ticket.other_links
    else:
        reg_result.error = wn_task_status
    return reg_result


@router.get("/file/{ticket_id}")
async def get_file(
        *,
        ticket_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    ticket = crud.cascade.get_by_ticket_id(db=db, ticket_id=ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    file_bytes = None
    if ticket.pastel_id != settings.PASTEL_ID:
        logging.error("Backend does not have correct Pastel ID")
    else:
        wn_resp = wn.call(False,
                          f'download?pid={settings.PASTEL_ID}&txid={ticket.reg_ticket_txid}',
                          {},
                          [],
                          {
                              'Authorization': settings.PASSPHRASE,
                          },
                          "file", "", True)

        if not isinstance(wn_resp, requests.models.Response):
            file_bytes = base64.b64decode(wn_resp)
            if not file_bytes:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Pastel file's incorrect")
        else:
            logging.error(wn_resp.text)

    if not file_bytes:
        if ticket.ipfs_link:
            ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
            file_bytes = ipfs_client.cat(ticket.ipfs_link)
            if not file_bytes:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"IPFS file not found")
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pastel file not found")

    response = StreamingResponse(iter([file_bytes]),
                                 media_type="application/x-binary"
                                 )
    response.headers["Content-Disposition"] = f"attachment; filename={ticket.original_file_name}"
    return response
