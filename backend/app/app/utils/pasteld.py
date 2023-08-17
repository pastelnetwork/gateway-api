import base64
import json
import logging
import re

import requests
from enum import Enum

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
    if 400 <= response.status_code < 600:
        logger.info(f"Request to cNode was: Body: {response.request.body}")
        logger.info(f"Response from cNode: {response.text}")
        if nothrow:
            return response
        resp = response.json()
        if resp and "error" in resp:
            raise PasteldException(resp["error"]["message"])

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


class TicketTransactionStatus(Enum):
    NOT_FOUND = 0
    WAITING = 1
    CONFIRMED = 2


async def check_ticket_transaction(txid, msg, current_block_height, start_waiting_block_height,
                                   interval=20, max_wait_blocks=100) -> TicketTransactionStatus:
    response = call('getrawtransaction', [txid, 1], nothrow=True)  # won't throw exception here
    if response and isinstance(response, dict):
        # ticket transaction is found at least locally
        if "height" in response and response["height"] > 0:
            msg += f" is in the block {response['height']}"
            start_waiting_block_height = response['height']
            # ticket is probably included into block
            if "confirmations" in response and response["confirmations"] > 0:
                # ticket is confirmed
                logger.info(f"{msg} and confirmed")
                return TicketTransactionStatus.CONFIRMED

            msg += f" but not confirmed yet."
        else:
            msg += f" is not included into the block yet"

        # ticket is not confirmed yet OR not included into the block yet, will wait for it
        if current_block_height - start_waiting_block_height <= max_wait_blocks:
            # if delta % interval != 0:
            #     logger.info(f"{msg}. Waiting...")
            #     return TicketTransactionStatus.WAITING

            # logger.info(f"{msg} after {delta} blocks. Resubmitting transaction")
            # if not await sign_and_submit(txid):
            #     logger.error(f"{msg} after {delta} blocks. Resubmit failed. Waiting again...")
            return TicketTransactionStatus.WAITING

    return TicketTransactionStatus.NOT_FOUND


async def sign_and_submit(txid) -> bool:
    try:
        tnx = call('getrawtransaction', [txid])   # will throw exception here
        response = call('signrawtransaction', [txid])  # will throw exception here
        if response and isinstance(response, dict) \
                and 'complete' in response and response['complete']\
                and 'hex' in response and response['hex']:
            signed_txid = call('sendrawtransaction', [response['hex']])
            return True
        else:
            logger.error(f"Failed to signrawtransaction for {txid}: {response}")
            return False
    except Exception as e:
        logger.error(f"Failed to getrawtransaction for {txid}: {e}")
        return False


class TicketCreateStatus(Enum):
    ALREADY_EXIST = 0
    CREATED = 1
    ERROR = 2


def create_activation_ticket(task_from_db, called_at_height, ticket_type) -> (TicketCreateStatus, str | None):
    try:
        if not check_balance(task_from_db.wn_fee + 1000):   # can throw exception here
            return
        activation_ticket = call('tickets', ['register', ticket_type,
                                             task_from_db.reg_ticket_txid,
                                             called_at_height,
                                             task_from_db.wn_fee,
                                             settings.PASTEL_ID,
                                             settings.PASTEL_ID_PASSPHRASE]
                                     )   # can throw exception here
        if activation_ticket and 'txid' in activation_ticket:
            logger.info(f"Created {ticket_type} ticket {activation_ticket['txid']}")
            return TicketCreateStatus.CREATED, activation_ticket['txid']

        logger.error(f"Error while creating {ticket_type} ticket {activation_ticket}")
        return TicketCreateStatus.ERROR, None

    except PasteldException as e:
        logger.error(f"Exception calling pastled to create {ticket_type} ticket: {e}")
        error_msg = (f"Ticket (action-act) is invalid. The Activation ticket for the Registration ticket with txid "
                     f"[{task_from_db.reg_ticket_txid}] already exists")
        if hasattr(e, 'message') and error_msg in e.message:
            match = re.search(r'txid=(.*?)]', e.message)
            return TicketCreateStatus.ALREADY_EXIST, match.group(1) if match else None
    except Exception as e:
        logger.error(f"Exception calling pastled to create {ticket_type} ticket: {e}")
        return TicketCreateStatus.ERROR, None
