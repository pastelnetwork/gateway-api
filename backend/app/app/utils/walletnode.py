import base64
import logging

import requests
from enum import Enum

from app.core.config import settings


class WalletNodeService(Enum):
    NFT = 'nfts'
    CASCADE = 'openapi/cascade'
    SENSE = 'openapi/sense'

    def __str__(self):
        return self.value


def call(post, service: WalletNodeService, url_cmd, payload, files, headers, return_item1, return_item2, nothrow=False):
    wn_url = f'{settings.WN_BASE_URL}/{service.value}/{url_cmd}'

    if post:
        response = requests.post(wn_url, headers=headers, data=payload, files=files)
    else:
        response = requests.get(wn_url, headers=headers, data=payload, files=files)
    if nothrow and response.status_code != 200:
        return response
    response.raise_for_status()

    upload_resp = response.json()

    if not return_item1:
        return upload_resp

    if not upload_resp or return_item1 not in upload_resp:
        raise WalletnodeException(f"Error, field '{return_item1}' not found")

    if not return_item2:
        return upload_resp[return_item1]

    if return_item1 not in upload_resp:
        raise WalletnodeException(f"Error, field '{return_item2}' not found")

    return upload_resp[return_item1], upload_resp[return_item2]


class WalletnodeException(Exception):
    """Exception raised for errors in the walletnode call

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message="Call to walletnode failed"):
        self.message = message
        super().__init__(self.message)


async def get_file_from_pastel(*, reg_ticket_txid, wn_service: WalletNodeService):
    file_bytes = None
    wn_resp = call(False,
                   wn_service,
                   f'download?pid={settings.PASTEL_ID}&txid={reg_ticket_txid}',
                   {},
                   [],
                   {'Authorization': settings.PASTEL_ID_PASSPHRASE, },
                   "file", "", True)    # This call will not throw!

    if not wn_resp:
        logging.error(f"Pastel file not found - reg ticket txid = {reg_ticket_txid}")
    elif not isinstance(wn_resp, requests.models.Response):
        try:
            file_bytes = base64.b64decode(wn_resp)
        except Exception as e:
            logging.error(f"Exception while decoding pastel file {e} - reg ticket txid = {reg_ticket_txid}")
        if not file_bytes:
            logging.error(f"Pastel file is incorrect - reg ticket txid = {reg_ticket_txid}")
    else:
        logging.error(wn_resp.text)
    return file_bytes
