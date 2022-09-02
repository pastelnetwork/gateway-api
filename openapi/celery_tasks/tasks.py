from celery import shared_task


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5},
             name='cascade:cascade_process')
def cascade_process(self, file_name: str):

    # if not os.path.exists(tmpDirectory):
    #     os.makedirs(tmpDirectory)

    # file_id, fee = wn_call(True,
    #                        'upload',
    #                        {},
    #                        [('file', (file.filename, file.file, file.content_type))],
    #                        {},
    #                        "file_id", "estimated_fee")
    #
    # await store_tmp_file(file, file_id)

    # details = await process(file_id, fee / 5)
    return {file_name: "file_id"}


@shared_task(bind=True, utoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5},
             name='sense:sense_process')
def sense_process(self):
    return ""
