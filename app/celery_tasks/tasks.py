from celery import shared_task
import utils.walletnode as wn


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5},
             name='cascade:cascade_process')
def cascade_process(self, file):

    data = file.read()

    file_id, fee = wn.call(True,
                           'upload',
                           {},
                           [('file', (file.name, data, file.type))],
                           {},
                           "file_id", "estimated_fee")

    # details = await process(file_id, fee / 5)
    return {file.name: file_id}


@shared_task(bind=True, utoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5},
             name='sense:sense_process')
def sense_process(self):
    return ""
