from celery import group
from fastapi import APIRouter, UploadFile
from typing import List
from starlette.responses import JSONResponse

import celery_tasks.tasks as tasks
from config.celery_utils import get_task_info

router = APIRouter(
    prefix="/cascade",
    tags=["cascade"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Not found"}},
)


# @router.post("/process/{api_key}/{file_id}")
@router.post("/process")
async def cascade_process(files: List[UploadFile]) -> dict:

    # if not os.path.exists(tmpDirectory):
    #     os.makedirs(tmpDirectory)

    data: dict = {}
    # celery_tasks = []
    results = {}
    for file in files:
        # await store_tmp_file(file)
        task = tasks.cascade_process.apply_async(args=[file.filename])
        results.update({file.filename: task.id})
        # celery_tasks.append(tasks.cascade_process.s(file.filename))
    # return JSONResponse({"task_id": task.id})
    return JSONResponse(results)

    # create a group with all the tasks
    # job = group(celery_tasks)
    # result = job.apply_async()
    # ret_values = result.get(disable_sync_subtasks=False)
    # for result in ret_values:
    #     print(result)
    #     data.update(result)
    # return data


# async def store_tmp_file(file, file_id):
#     await file.seek(0)
#     content = await file.read()
#     with open(f'{tmpDirectory}/{file_id}', 'wb') as tmp_file:
#         tmp_file.write(content)


@router.get("/task/{task_id}")
async def get_task_status(task_id: str) -> dict:
    """
    Return the status of the submitted Task
    """
    return get_task_info(task_id)
