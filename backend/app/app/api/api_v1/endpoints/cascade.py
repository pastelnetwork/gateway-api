import uuid

from fastapi import APIRouter, Depends, UploadFile  # , HTTPException

from typing import List
from starlette.responses import JSONResponse
from sqlalchemy.orm import Session

import app.celery_tasks.cascade as cascade
from app.celery_tasks.base import get_task_info
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
        task_result = schemas.TaskResult(
            file=file.filename,
            ticket_id=ticket_id,
            status=res.status,
        )
        results.tickets.append(task_result)

    return results


@router.get("/{work_id}", response_model=schemas.WorkResult, response_model_exclude_none=True)
async def get_work_status(
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
    stored_tasks = crud.cascade.get_all_in_work(db=db, work_id=work_id)
    for task in stored_tasks:
        if task.task_id:
            if task.task_id == 'DONE':
                status = 'PENDING'
            else:
                task_info = get_task_info(task.task_id)
                status = task_info['task_status']
        else:
            status = 'UNKNOWN'

        wn_task_status = wn.call(False,
                                 f'{task.wn_task_id}/history',
                                 {},
                                 [],
                                 {},
                                 "", "")
        for step in wn_task_status:
            if step['status'] == 'Task Rejected':
                status = 'ERROR' if settings.RETURN_DETAILED_WN_ERROR else 'PENDING'
                break
            if step['status'] == 'Task Completed':
                status = 'DONE'
                break

        task_result = schemas.TaskResult(
            file=task.original_file_name,
            ticket_id=task.ticket_id,
            status=status,
        )

        if status != 'ERROR':
            task_result.reg_ticket_txid = task.reg_ticket_txid
            task_result.act_ticket_txid = task.act_ticket_txid
            task_result.ipfs_link = task.ipfs_link
            task_result.aws_link = task.aws_link
            task_result.other_links = task.other_links
        else:
            task_result.error = wn_task_status

        results.tickets.append(task_result)

    return results
