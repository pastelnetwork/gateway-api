from fastapi import APIRouter, Depends, UploadFile

from typing import List
from sqlalchemy.orm import Session

import app.celery_tasks.cascade as cascade
import app.db.session as session
from app.api import deps, common
from app import models, crud, schemas
import app.utils.walletnode as wn


router = APIRouter()


@router.post("/", response_model=schemas.WorkResult, response_model_exclude_none=True)
async def do_work(
        *,
        files: List[UploadFile],
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.WorkResult:
    return await common.do_works(worker=cascade, files=files, current_user=current_user)


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
    tickets = crud.cascade.get_multi_by_owner(db=db, owner_id=current_user.id)
    return await common.parse_users_works(tickets, wn.WalletNodeService.CASCADE)


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
    tickets_in_work = crud.cascade.get_all_in_work(db=db, work_id=work_id)
    return await common.parse_user_work(tickets_in_work, work_id, wn.WalletNodeService.CASCADE)


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
        ticket_result = await common.check_ticket_registration_status(ticket, wn.WalletNodeService.CASCADE)
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
    ticket_result = await common.check_ticket_registration_status(ticket, wn.WalletNodeService.CASCADE)
    return ticket_result


@router.get("/file/{ticket_id}")
async def get_file(
        *,
        ticket_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    return await common.get_file(ticket_id=ticket_id, db=db, service=wn.WalletNodeService.CASCADE)
