from fastapi import APIRouter, UploadFile
from typing import List
from starlette.responses import JSONResponse

import celery_tasks.tasks as tasks
from core.celery_utils import get_task_info
from utils.filestorage import LocalFile

router = APIRouter(
    prefix="/cascade",
    tags=["cascade"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Not found"}},
)


@router.post("/process")
async def cascade_process(*, files: List[UploadFile]) -> JSONResponse:

    data: dict = {}
    results = {}
    for file in files:
        lf = LocalFile(file.filename, file.content_type)
        await lf.save(file)
        task = tasks.cascade_process.apply_async(args=[lf])
        results.update({file.filename: task.id})
    return JSONResponse(results)


@router.get("/task/{task_id}")
async def get_task_status(*, task_id: str) -> dict:
    """
    Return the status of the submitted Task
    """
    return get_task_info(task_id)
