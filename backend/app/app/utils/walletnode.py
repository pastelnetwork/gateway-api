import base64
import logging
import requests
from enum import Enum

from app.core.config import settings
from app.utils.authentication import send_alert_email
from app.utils.secret_manager import get_pastelid_pwd_from_secret_manager

logger = logging.getLogger(__name__)


class WalletNodeService(Enum):
    NFT = 'nfts'
    CASCADE = 'openapi/cascade'
    SENSE = 'openapi/sense'
    COLLECTION = 'collection'

    def __str__(self):
        return self.value


def call(post, service: WalletNodeService, url_cmd, payload, files, headers, return_item1, return_item2, nothrow=False):
    if url_cmd:
        wn_url = f'{settings.WN_BASE_URL}/{service.value}/{url_cmd}'
    else:
        wn_url = f'{settings.WN_BASE_URL}/{service.value}'

    logger.info(f"Calling WalletNode with: header: {headers} and payload: {payload}")

    try:
        if post:
            response = requests.post(wn_url, headers=headers, data=payload, files=files, timeout=300)
        else:
            response = requests.get(wn_url, headers=headers, data=payload, files=files, timeout=300)
    except requests.Timeout as te:
        logger.error(f"Timeout calling WalletNode: {te}")
        send_alert_email(f"Timeout calling WalletNode RPC: {te}")
        if nothrow:
            return None
        raise WalletnodeException()
    except Exception as e:
        logger.error(f"Exception calling WalletNode: {e}")
        if nothrow:
            return None
        raise WalletnodeException()
    logger.info(f"Request to WalletNode was: URL: {response.request.url}\nMethod: {response.request.method}"
                f"\nHeaders: {response.request.headers}")
    if 400 <= response.status_code < 600:
        logger.info(f"Request to WalletNode was: \nBody: {response.request.body}")
        logger.info(f"Response from WalletNode: {response.text}")
        if nothrow:
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


async def get_file_from_pastel(*, reg_ticket_txid, pastel_id: str, wn_service: WalletNodeService):
    logger.info(f"{wn_service} get_file_from_pastel: reg_ticket_txid = {reg_ticket_txid}")
    pastel_id_pwd = get_pastelid_pwd_from_secret_manager(pastel_id)
    if not pastel_id_pwd:
        logger.error(f"Pastel ID {pastel_id} not found in secret manager")
        return None
    if wn_service == WalletNodeService.SENSE:
        file_key = "file"
    else:
        file_key = "file_id"
    wn_resp = call(False,
                   wn_service,
                   f'download?pid={pastel_id}&txid={reg_ticket_txid}',
                   {},
                   [],
                   {'Authorization': pastel_id_pwd, },
                   file_key, "", True)    # This call will not throw!

    if not wn_resp:
        logger.error(f"Pastel file not found - reg ticket txid = {reg_ticket_txid}")
    elif not isinstance(wn_resp, requests.models.Response):
        logger.info(f"{wn_service} get_file_from_pastel: WN response = {wn_resp}")
        if wn_service == WalletNodeService.SENSE:
            return await decode_wn_return(wn_resp, reg_ticket_txid)
        else:
            return await download_file_from_wn_by_id(wn_resp, reg_ticket_txid, pastel_id)
    else:
        logger.error(wn_resp.text)
    return None


async def get_nft_dd_result_from_pastel(*, reg_ticket_txid: str, pastel_id: str):
    logger.info(f"get_nft_dd_result_from_pastel: reg_ticket_txid = {reg_ticket_txid}")
    pastel_id_pwd = get_pastelid_pwd_from_secret_manager(pastel_id)
    if not pastel_id_pwd:
        logger.error(f"Pastel ID {pastel_id} not found in secret manager")
        return None
    wn_resp = call(False,
                   WalletNodeService.NFT,
                   f'get_dd_result_file?pid={pastel_id}&txid={reg_ticket_txid}',
                   {},
                   [],
                   {'Authorization': pastel_id_pwd, },
                   "file", "", True)    # This call will not throw!

    if not wn_resp:
        logger.error(f"NFT DD result for file not found - reg ticket txid = {reg_ticket_txid}")
    elif not isinstance(wn_resp, requests.models.Response):
        return await decode_wn_return(wn_resp, reg_ticket_txid)
    return None


async def download_file_from_wn_by_id(file_id, reg_ticket_txid, pastel_id: str):
    logger.info(f"download_file_from_wn_by_id: file_id = {file_id}; reg_ticket_txid = {reg_ticket_txid}")
    pastel_id_pwd = get_pastelid_pwd_from_secret_manager(pastel_id)
    if not pastel_id_pwd:
        logger.error(f"Pastel ID {pastel_id} not found in secret manager")
        return None
    try:
        file_url = f'{settings.WN_BASE_URL}/files/{file_id}?pid={pastel_id}'
        payload = {}
        headers = {'Authorization': pastel_id_pwd, }
        file_response = requests.request("GET", file_url, headers=headers, data=payload)
        if file_response.status_code != 200:
            logger.info(f"Calling WN as: "
                        f"URL: {file_response.request.url}\nMethod: {file_response.request.method}"
                        f"\nHeaders: {file_response.request.headers}\nBody: {file_response.request.body}")
            logger.info(f"Response from WN: {file_response.text}")
            logger.error(f"Pastel file not found - reg ticket txid = {reg_ticket_txid}: error in wn/files response")
        else:
            logger.info(f"download_file_from_wn_by_id: got file. file_id = {file_id}; "
                        f"reg_ticket_txid = {reg_ticket_txid}")
            return file_response.content
    except Exception as e:
        logger.error(f"Exception while downloading file from WN {e} - reg ticket txid = {reg_ticket_txid}")
    return None


async def decode_wn_return(wn_data, reg_ticket_txid):
    data_bytes = None
    try:
        data_bytes = base64.b64decode(wn_data)
    except Exception as e:
        logger.error(f"Exception while decoding dd data {e} - reg ticket txid = {reg_ticket_txid}")
    if not data_bytes:
        logger.error(f"DD data is incorrect - reg ticket txid = {reg_ticket_txid}")
    return data_bytes
