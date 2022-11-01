from celery.result import AsyncResult
import celery

from app import crud, schemas
from app.db.session import db_context


class PastelTask(celery.Task):
    def run(self, *args, **kwargs):
        pass

    def on_success(self, retval, task_id, args, kwargs):

        if args:
            if len(args) == 1:
                ticket_id = args[0]
            elif len(args) == 4:
                ticket_id = args[2]
            else:
                raise Exception("Invalid args")

        with db_context() as session:
            cascade_task = crud.cascade.get_by_ticket_id(session, ticket_id=ticket_id)
            upd = {"task_id": "DONE"}
            crud.cascade.update(session, db_obj=cascade_task, obj_in=upd)

    # def on_failure(self, exc, task_id, args, kwargs, einfo):
    #     print(f'{task_id} failed: {exc}')
    #
    # def on_retry(self, exc, task_id, args, kwargs, einfo):
    #     print(f'{task_id} retrying: {exc}')


def get_task_info(task_id):
    """
    return task info for the given task_id
    """
    task_result = AsyncResult(task_id)
    result = {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_state": task_result.state,
        "task_result": str(task_result.result)
    }
    return result
