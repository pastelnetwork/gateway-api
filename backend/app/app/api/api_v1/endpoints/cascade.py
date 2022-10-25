from fastapi import APIRouter, Depends, UploadFile#, HTTPException

from typing import List
from starlette.responses import JSONResponse
from sqlalchemy.orm import Session

import app.celery_tasks.cascade as cascade
import app.db.session as session
from app.core.celery_utils import get_task_info
from app.utils.filestorage import LocalFile
from app.api import deps
from app import models#, crud, schemas

router = APIRouter()


@router.post("/process")
async def cascade_process(
        *,
        files: List[UploadFile],
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> dict:
    results = {}
    for file in files:
        lf = LocalFile(file.filename, file.content_type)
        await lf.save(file)
        res = cascade.cascade_process.delay(lf)
        results.update({file.filename: res.id})

    return JSONResponse(results)


@router.get("/task/{task_id}")
async def get_task_status(
        *,
        task_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade)
        # current_user: models.User = Depends(deps.OAuth2Auth.get_current_user)
) -> dict:
    """
    Return the status of the submitted Task
    """
    return get_task_info(task_id)
