import requests
from enum import Enum

from app.core.config import settings


class WalletNodeService(Enum):
    NFT = 'nfts'
    CASCADE = 'openapi/cascade'
    SENSE = 'openapi/sense'

    def __str__(self):
        return self.value


def call(post, service: WalletNodeService, url_cmd, payload, files, headers, return_item1, return_item2, no_throw=False):
    wn_url = f'{settings.WN_BASE_URL}/{service.value}/{url_cmd}'

    if post:
        response = requests.post(wn_url, headers=headers, data=payload, files=files)
    else:
        response = requests.get(wn_url, headers=headers, data=payload, files=files)
    if no_throw and response.status_code != 200:
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
