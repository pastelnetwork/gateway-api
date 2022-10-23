from celery import shared_task

import app.utils.walletnode as wn
import app.utils.pasteld as psl
from app.core.config import settings


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

    # burn_txid = psl.call("sendtoaddress", [settings.BURN_ADDRESS, fee / 5])
    height = psl.call("getblockcount", [])

    # task_id = wn.call(True,
    #                   f'start/{file_id}',
    #                   json.dumps({
    #                       "burn_txid": burn_txid_to_use,
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

    # return {file.name: file_id, fee: fee, burn_txid: burn_txid, height: height}
    return {file.name: file_id, "fee": fee, "height": height}


@shared_task(bind=True, utoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5},
             name='sense:sense_process')
def sense_process(self):
    return ""
