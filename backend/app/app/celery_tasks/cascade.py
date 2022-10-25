from celery import shared_task

import app.utils.walletnode as wn
import app.utils.pasteld as psl
# from app.core.config import settings
from app import crud  # , models, schemas
from app.db.session import db_context


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=150, retry_kwargs={"max_retries": 5},
             name='cascade:cascade_process')
def cascade_process(self, file):
    data = file.read()

    file_id, fee = wn.call(True,
                           'upload',
                           {},
                           [('file', (file.name, data, file.type))],
                           {},
                           "file_id", "estimated_fee")

    height = psl.call("getblockcount", [])

    burn_amount = fee / 5
    with db_context() as session:
        task_id = cascade_process.request.id
        burn_tx = crud.preburn_tx.get_bound_to_task(session, task_id=task_id)
        if not burn_tx:
            burn_tx = crud.preburn_tx.get_non_used_by_fee(session, fee=burn_amount)
            if not burn_tx:
                # burn_txid = psl.call("sendtoaddress", [settings.BURN_ADDRESS, burn_amount])
                burn_txid = f"Test - {task_id}"
                burn_tx = crud.preburn_tx.create_new_bound(session,
                                                           fee=burn_amount,
                                                           height=height,
                                                           txid=burn_txid,
                                                           task_id=task_id)
            else:
                burn_tx = crud.preburn_tx.bind_pending_to_task(session, burn_tx,
                                                               task_id=task_id)
    if burn_tx.height > height - 10:
        cascade_process.retry()
    burn_txid = burn_tx.txid

    # task_id = wn.call(True,
    #                   f'start/{file_id}',
    #                   json.dumps({
    #                       "burn_txid": burn_txid,
    #                       "app_pastelid": settings.PASTEL_ID,
    #                   }),
    #                   [],
    #                   {
    #                       'app_pastelid_passphrase': settings.PASSPHRASE,
    #                       'Content-Type': 'application/json'
    #                   },
    #                   "task_id", "")

    # ipfs_client = ipfshttpclient.connect()  # Connects to: /dns/localhost/tcp/5001/http
    # res = ipfs_client.add(f'{tmpDirectory}/{file_id}')
    # ipfs_link = 'https://ipfs.io/ipfs/' + res['Hash']

    return {file.name: file_id, "fee": fee, "burn_txid": burn_txid, "height": height}


@shared_task(bind=True, utoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5},
             name='sense:sense_process')
def sense_process(self):
    return ""
