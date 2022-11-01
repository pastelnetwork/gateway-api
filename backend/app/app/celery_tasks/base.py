from celery.result import AsyncResult
import celery

from app import crud
from app.db.session import db_context


class PastelTask(celery.Task):
    def run(self, *args, **kwargs):
        pass

    def on_success(self, retval, task_id, args, kwargs):

        ticket_id = ''
        if args:
            if len(args) == 1:
                ticket_id = args[0]
            elif len(args) == 4:
                ticket_id = args[2]

        if not ticket_id:
            raise Exception("Invalid args")

        with db_context() as session:
            task = crud.cascade.get_by_ticket_id(session, ticket_id=ticket_id)
            upd = {"task_status": "STARTED"}
            crud.cascade.update(session, db_obj=task, obj_in=upd)

    # def on_failure(self, exc, task_id, args, kwargs, einfo):
    #     print(f'{task_id} failed: {exc}')
    #
    # def on_retry(self, exc, task_id, args, kwargs, einfo):
    #     print(f'{task_id} retrying: {exc}')


def get_celery_task_info(celery_task_id):
    """
    return task info for the given celery_task_id
    """
    task_result = AsyncResult(celery_task_id)
    result = {
        "celery_task_id": celery_task_id,
        "celery_task_status": task_result.status,
        "celery_task_state": task_result.state,
        "celery_task_result": str(task_result.result)
    }
    return result
