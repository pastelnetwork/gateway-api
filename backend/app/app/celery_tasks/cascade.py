from celery import shared_task

import app.utils.walletnode as wn
import app.utils.pasteld as psl
from app.core.config import settings
from app import crud, models, schemas
from app.db.session import db_context


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, max_retries=5,
             name='cascade:register_image')
def register_image(self, local_file, work_id, user_id):
    task_id = register_image.request.id
    with db_context() as session:
        cascade_task = crud.cascade.get_by_task_id(session, task_id=task_id)

    if not cascade_task:
        data = local_file.read()
        file_id, fee = wn.call(True,
                               'upload',
                               {},
                               [('file', (local_file.name, data, local_file.type))],
                               {},
                               "file_id", "estimated_fee")

        height = psl.call("getblockcount", [])
        with db_context() as session:
            new_cascade_task = schemas.CascadeCreate(
                original_file_name=local_file.name,
                original_file_content_type=local_file.type,
                original_file_local_path=local_file.path,
                work_id=work_id,
                last_task_id=task_id,
                wn_file_id=file_id,
                wn_fee=fee,
                height=height,
            )
            crud.cascade.create_with_owner(session, obj_in=new_cascade_task, owner_id=user_id)

    return task_id


@shared_task(bind=True, autoretry_for=(Exception,),
             default_retry_delay=300, retry_backoff=150, max_retries=10,
             name='cascade:preburn_fee')
def preburn_fee(self, prev_task_id):
    with db_context() as session:
        cascade_task = crud.cascade.get_by_task_id(session, task_id=prev_task_id)

    if not cascade_task:
        raise Exception

    burn_amount = cascade_task.wn_fee/5
    height = psl.call("getblockcount", [])

    task_id = preburn_fee.request.id
    if not cascade_task.burn_txid:
        with db_context() as session:
            burn_tx = crud.preburn_tx.get_bound_to_task(session, task_id=task_id)
            if not burn_tx:
                burn_tx = crud.preburn_tx.get_non_used_by_fee(session, fee=burn_amount)
                if not burn_tx:
                    burn_txid = psl.call("sendtoaddress", [settings.BURN_ADDRESS, burn_amount])
                    burn_txid = f"Test - {task_id}"
                    burn_tx = crud.preburn_tx.create_new_bound(session,
                                                               fee=burn_amount,
                                                               height=height,
                                                               txid=burn_txid,
                                                               task_id=task_id)
                else:
                    burn_tx = crud.preburn_tx.bind_pending_to_task(session, burn_tx,
                                                                   task_id=task_id)
            if burn_tx.height > height - 5:
                preburn_fee.retry()

            upd = {"burn_txid": burn_tx.txid, "last_task_id": task_id}
            crud.cascade.update(session, db_obj=cascade_task, obj_in=upd)

    return task_id


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, max_retries=10,
             name='cascade:process')
def process(self, prev_task_id):
    with db_context() as session:
        cascade_task = crud.cascade.get_by_task_id(session, task_id=prev_task_id)

    if not cascade_task:
        raise Exception

    burn_txid = cascade_task.burn_txid
    file_name = cascade_task.original_file_name
    wn_file_id = cascade_task.wn_file_id
    wn_fee = cascade_task.wn_fee
    height = cascade_task.height

    task_id = process.request.id
    with db_context() as session:
        upd = {"last_task_id": task_id}
        crud.cascade.update(session, db_obj=cascade_task, obj_in=upd)

    task_id = wn.call(True,
                      f'start/{wn_file_id}',
                      json.dumps({
                          "burn_txid": burn_txid,
                          "app_pastelid": settings.PASTEL_ID,
                      }),
                      [],
                      {
                          'app_pastelid_passphrase': settings.PASSPHRASE,
                          'Content-Type': 'application/json'
                      },
                      "task_id", "")

    # ipfs_client = ipfshttpclient.connect()  # Connects to: /dns/localhost/tcp/5001/http
    # res = ipfs_client.add(f'{tmpDirectory}/{file_id}')
    # ipfs_link = 'https://ipfs.io/ipfs/' + res['Hash']

    return {"file_name": file_name, "file_id": wn_file_id, "fee": wn_fee,
            "burn_txid": burn_txid, "height": height, "last_task_id": task_id}


@shared_task(bind=True, utoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5},
             name='sense:sense_process')
def sense_process(self):
    return ""
