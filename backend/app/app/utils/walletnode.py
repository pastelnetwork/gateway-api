import requests
from app.core.config import settings


def call(post, url_cmd, payload, files, headers, return_item1, return_item2):
    wn_url = f'{settings.BASE_CASCADE_URL}/{url_cmd}'

    if post:
        response = requests.post(wn_url, headers=headers, data=payload, files=files)
    else:
        response = requests.get(wn_url, headers=headers, data=payload, files=files)
    response.raise_for_status()
    upload_resp = response.json()

    if not return_item1:
        return upload_resp

    if not upload_resp or not upload_resp[return_item1]:
        raise WalletnodeException(f"Error, {return_item1} not found")
    if not return_item2:
        return upload_resp[return_item1]
    if not upload_resp[return_item2]:
        raise WalletnodeException(f"Error, {return_item2} not found")
    return upload_resp[return_item1], upload_resp[return_item2]


class WalletnodeException(Exception):
    """Exception raised for errors in the walletnode call

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message="Call to walletnode failed"):
        self.message = message
        super().__init__(self.message)
