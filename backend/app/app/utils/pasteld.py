import base64
import json
import logging
import requests

from fastapi import HTTPException
from requests.auth import HTTPBasicAuth

from app.core.config import settings
from app.utils.authentication import send_alert_email

logger = logging.getLogger(__name__)


def call(method, parameters, nothrow=False):
    payload_getinfo = {"jsonrpc": "1.0", "id": "pastelapi", "method": method, "params": parameters}
    payload = json.dumps(payload_getinfo)

    logger.info(f"Calling cNode as: {payload}")

    auth = HTTPBasicAuth(settings.PASTEL_RPC_USER, settings.PASTEL_RPC_PWD)
    try:
        response = requests.post(settings.PASTEL_RPC_URL, payload, auth=auth, timeout=600)
    except requests.Timeout as te:
        logger.error(f"Timeout calling pasteld RPC: {te}")
        send_alert_email(f"Timeout calling pasteld RPC: {te}")
        if nothrow:
            return None
        raise PasteldException()
    except Exception as e:
        logger.error(f"Exception calling pasteld RPC: {e}")
        send_alert_email(f"Exception calling pasteld RPC: {e}")
        if nothrow:
            return None
        raise PasteldException()
    logger.info(f"Request to cNode was: "
                f"URL: {response.request.url}\nMethod: {response.request.method}\nHeaders: "
                f"{response.request.headers}")
    if response.status_code != 200:
        logger.info(f"Request to cNode was: Body: {response.request.body}")
        logger.info(f"Response from cNode: {response.text}")
        if nothrow:
            return response
    response.raise_for_status()
    resp = response.json()
    if not resp or not resp["result"]:
        if nothrow:
            return None
        raise PasteldException()
    return resp["result"]


class PasteldException(Exception):
    """Exception raised for errors in the pasteld call

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message="Call to pasteld failed"):
        self.message = message
        super().__init__(self.message)


async def parse_registration_action_ticket(reg_ticket, expected_ticket_type, expected_action_type: list[str]):
    if not reg_ticket or \
            "ticket" not in reg_ticket or \
            "action_ticket" not in reg_ticket["ticket"] or \
            "type" not in reg_ticket["ticket"] or \
            "action_type" not in reg_ticket["ticket"]:
        raise HTTPException(status_code=501, detail=f"Invalid {expected_action_type} registration ticket")

    if reg_ticket["ticket"]["type"] != expected_ticket_type:
        raise HTTPException(status_code=501,
                            detail=f'Invalid {expected_action_type} registration ticket type - '
                                   f'{reg_ticket["ticket"]["type"]}')

    if reg_ticket["ticket"]["action_type"] not in expected_action_type:
        raise HTTPException(status_code=501,
                            detail=f'Invalid {expected_action_type} registration ticket action type - '
                                   f'{reg_ticket["ticket"]["action_type"]}')

    # Base64decode the ticket
    reg_ticket_action_ticket_str = base64.b64decode(reg_ticket["ticket"]["action_ticket"]).decode('utf-8')

    # Convert to json
    reg_ticket["ticket"]["action_ticket"] = json.loads(reg_ticket_action_ticket_str)

    if not reg_ticket["ticket"]["action_ticket"] or \
            "action_ticket_version" not in reg_ticket["ticket"]["action_ticket"] or \
            "action_type" not in reg_ticket["ticket"]["action_ticket"] or \
            "api_ticket" not in reg_ticket["ticket"]["action_ticket"]:
        raise HTTPException(status_code=501, detail=f"Failed to decode action_ticket in the "
                                                    f"{expected_action_type} registration ticket")
    if reg_ticket["ticket"]["action_ticket"]["action_type"] not in expected_action_type:
        raise HTTPException(status_code=501,
                            detail=f'Invalid "app_ticket" in the {expected_action_type} '
                                   f'registration ticket action type - '
                                   f'{reg_ticket["ticket"]["action_type"]}')

    try:
        # ASCII85decode the api_ticket
        api_ticket_str = base64.a85decode(reg_ticket["ticket"]["action_ticket"]["api_ticket"])
        reg_ticket["ticket"]["action_ticket"]["api_ticket"] = json.loads(api_ticket_str)
    except ValueError as ve:
        logger.warning(f"Failed to ascii85 decode api_ticket in the {expected_action_type} registration ticket: {ve}")
        try:
            # Base64decode the api_ticket
            api_ticket_str = base64.b64decode(reg_ticket["ticket"]["action_ticket"]["api_ticket"])
            reg_ticket["ticket"]["action_ticket"]["api_ticket"] = json.loads(api_ticket_str)
        except ValueError as ve:
            if str(ve) == "Incorrect padding":
                try:
                    api_ticket_str = reg_ticket["ticket"]["action_ticket"]["api_ticket"]
                    api_ticket_str += '=='
                    api_ticket_str = base64.b64decode(api_ticket_str)
                    reg_ticket["ticket"]["action_ticket"]["api_ticket"] = json.loads(api_ticket_str)
                except ValueError as ve:
                    logger.warning(f"Failed to base64 decode api_ticket in the {expected_action_type} "
                                   f"with extra padding registration ticket: {ve}")
            else:
                logger.warning(f"Failed to base64 decode api_ticket in the {expected_action_type} "
                               f"registration ticket: {ve}")

    return reg_ticket


async def parse_registration_nft_ticket(reg_ticket):
    if not reg_ticket or "ticket" not in reg_ticket or "nft_ticket" not in reg_ticket["ticket"]:
        raise HTTPException(status_code=501, detail=f"Invalid NFT registration ticket")

    # Base64decode the ticket
    reg_ticket_nft_ticket_str = base64.b64decode(reg_ticket["ticket"]["nft_ticket"]).decode('utf-8')

    # Convert to json
    reg_ticket["ticket"]["nft_ticket"] = json.loads(reg_ticket_nft_ticket_str)

    if not reg_ticket["ticket"]["nft_ticket"] or \
            "nft_ticket_version" not in reg_ticket["ticket"]["nft_ticket"] or \
            "app_ticket" not in reg_ticket["ticket"]["nft_ticket"]:
        raise HTTPException(status_code=501, detail=f"Failed to decode action_ticket in the "
                                                    f"NFT registration ticket")

    try:
        # ASCII85decode the app_ticket
        app_ticket_str = base64.a85decode(reg_ticket["ticket"]["nft_ticket"]["app_ticket"])
        reg_ticket["ticket"]["nft_ticket"]["app_ticket"] = json.loads(app_ticket_str)
    except ValueError as ve:
        logger.warning(f"Failed to ascii85 decode app_ticket in the NFT registration ticket: {ve}")
        try:
            # Base64decode the app_ticket
            app_ticket_str = base64.b64decode(reg_ticket["ticket"]["nft_ticket"]["app_ticket"])
            reg_ticket["ticket"]["nft_ticket"]["app_ticket"] = json.loads(app_ticket_str)
        except ValueError as ve:
            if str(ve) == "Incorrect padding":
                try:
                    app_ticket_str = reg_ticket["ticket"]["nft_ticket"]["app_ticket"]
                    app_ticket_str += '=='
                    app_ticket_str = base64.b64decode(app_ticket_str)
                    reg_ticket["ticket"]["nft_ticket"]["app_ticket"] = json.loads(app_ticket_str)
                except ValueError as ve:
                    logger.warning(f"Failed to base64 decode api_ticket in the NFT "
                                   f"with extra padding registration ticket: {ve}")
            else:
                logger.warning(f"Failed to base64 decode app_ticket in the NFT "
                               f"registration ticket: {ve}")

    return reg_ticket


async def create_offer_ticket(task_from_db, current_pastel_id, current_passphrase, rcpt_pastel_id):
    offer_ticket = call('tickets', ['register', 'offer',
                                    task_from_db.act_ticket_txid,
                                    1,
                                    current_pastel_id, current_passphrase,
                                    0, 0, 1, "",
                                    rcpt_pastel_id],
                        nothrow=True)   # won't throw exception here
    if not offer_ticket or not isinstance(offer_ticket, dict):
        raise HTTPException(status_code=500, detail=f"Failed to create offer ticket: {offer_ticket}")
    return offer_ticket


async def verify_message(message, signature, pastel_id) -> bool:
    response = call('pastelid', ['verify', message, signature, pastel_id], nothrow=True)   # won't throw exception here
    if isinstance(response, dict) and 'verification' in response and response['verification'] == 'OK':
        return True
    return False


def check_balance(need_amount: float) -> bool:
    balance = call("getbalance", [])
    if balance < need_amount:
        logger.error(f"Insufficient funds: balance {balance}")
        send_alert_email(f"Insufficient funds: balance {balance}")
        return False
    return True
