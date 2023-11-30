import base64
import json
import logging
import re
import time
from typing import Dict

import requests
from enum import Enum

from fastapi import HTTPException
from requests.auth import HTTPBasicAuth

from app.core.config import settings
from app.utils.authentication import send_alert_email
from app.utils.secret_manager import get_pastelid_pwd_from_secret_manager

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
    if not resp or "result" not in resp:
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


async def create_offer_ticket(act_ticket_txid: str, price: int, current_pastel_id: str, current_passphrase: str,
                              rcpt_pastel_id: str, funding_address: str | None):
    if not funding_address:
        spendable_address = find_address_with_funds(settings.COLLECTION_TICKET_FEE)
        if not spendable_address:
            logger.error(f"No spendable address found for amount > {price}. [act_ticket_txid: {act_ticket_txid}]")
            send_alert_email(
                f"No spendable address found to pay Offer ticket fee in the amount > {settings.COLLECTION_TICKET_FEE}")
            raise HTTPException(status_code=500, detail=f"Failed to create offer ticket for: {act_ticket_txid}")

    offer_ticket = call('tickets', ['register', 'offer',
                                    act_ticket_txid,
                                    price,
                                    current_pastel_id, current_passphrase,
                                    0, 0, 1, funding_address if funding_address else settings.MAIN_GATEWAY_ADDRESS,
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


def check_balance(need_amount: float, send_email: bool = True) -> bool:
    balance = call('getbalance', [])
    if balance < need_amount:
        logger.error(f"Insufficient funds: balance {balance}")
        if send_email:
            send_alert_email(f"Insufficient funds: balance {balance}")
        return False
    return True


class TicketTransactionStatus(Enum):
    NOT_FOUND = 0
    WAITING = 1
    CONFIRMED = 2


async def check_ticket_transaction(txid, msg, current_block_height, start_waiting_block_height,
                                   max_wait_blocks=100) -> TicketTransactionStatus:
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
            return TicketTransactionStatus.WAITING

    return TicketTransactionStatus.NOT_FOUND


class TicketCreateStatus(Enum):
    ALREADY_EXIST = 0
    CREATED = 1
    ERROR = 2


def create_activation_ticket(task_from_db, called_at_height, ticket_type,
                             funding_address: str | None) -> (TicketCreateStatus, str | None):
    try:
        # can throw exception here
        min_ticket_fee = task_from_db.wn_fee + settings.MIN_TICKET_PRICE_BALANCE
        if not check_address_balance(funding_address, min_ticket_fee, f"{ticket_type} ticket"):
            return TicketCreateStatus.ERROR, None
        pastel_id_pwd = get_pastelid_pwd_from_secret_manager(task_from_db.pastel_id)
        activation_ticket = call('tickets', ['register', ticket_type,
                                             task_from_db.reg_ticket_txid,
                                             called_at_height,
                                             task_from_db.wn_fee,
                                             task_from_db.pastel_id,
                                             pastel_id_pwd,
                                             funding_address if funding_address else None]
                                 )   # can throw exception here
        if activation_ticket and 'txid' in activation_ticket:
            logger.info(f"Created {ticket_type} ticket {activation_ticket['txid']}")
            return TicketCreateStatus.CREATED, activation_ticket['txid']

        logger.error(f"Error while creating {ticket_type} ticket {activation_ticket}")
        return TicketCreateStatus.ERROR, None

    except PasteldException as e:
        logger.error(f"Exception calling pasteld to create {ticket_type} ticket: {e}")
        error_msg = (f"Ticket (action-act) is invalid. The Activation ticket for the Registration ticket with txid "
                     f"[{task_from_db.reg_ticket_txid}] already exists")
        if hasattr(e, 'message') and error_msg in e.message:
            match = re.search(r'txid=(.*?)]', e.message)
            return TicketCreateStatus.ALREADY_EXIST, match.group(1) if match else None
    except Exception as e:
        logger.error(f"Exception calling pastled to create {ticket_type} ticket: {e}")
        return TicketCreateStatus.ERROR, None


def create_and_register_pastelid(passkey: str, funding_address: str) -> str | None:
    full_pastelid = call('pastelid', ['newkey', passkey])
    if full_pastelid and isinstance(full_pastelid, dict) and "pastelid" in full_pastelid:
        pastelid = full_pastelid["pastelid"]
        call('tickets', ['register', 'id', pastelid, passkey,
                         funding_address if funding_address else settings.MAIN_GATEWAY_ADDRESS])
        return pastelid
    return None


def create_address() -> str | None:
    new_address = call('getnewaddress', [])
    if new_address and isinstance(new_address, str):
        return new_address
    return None


def check_address_balance(address: str | None, need_amount: float, what: str, send_email: bool = True) -> bool:
    if not address:
        return check_balance(need_amount, send_email)

    address_balance = call("z_getbalance", [address])
    if address_balance < need_amount:
        logger.error(f"Not enough funds on {address} to pay for {what}."
                     f"Need > {need_amount} but has {address_balance}")
        if send_email:
            send_alert_email(f"No enough funds on {address} to pay for {what}."
                             f"Need > {need_amount} but has {address_balance}")
        return False
    return True


def send_to_many_z(from_address: str, to_addresses: Dict[str, float], _fee: float = 0.0001) -> str | None:
    to_addresses_upd = [{"address": key, "amount": value} for key, value in to_addresses.items()]
    total_amount = sum(to_addresses.values())
    try:
        opid = call("z_sendmanywithchangetosender", [from_address, to_addresses_upd])
        if opid and isinstance(opid, str):
            for _ in range(5):
                op_status = call("z_getoperationstatus", [[opid]])
                for operation in op_status:
                    if operation['id'] == opid:
                        status = operation['status']
                        if status == 'success':
                            return operation['result']['txid']
                        elif status == 'failed':
                            logger.error(f"z_sendmanywithchangetosender failed: {operation['error']['message']}")
                            return None
                        else:
                            break
    except PasteldException as e:
        logger.error(f"Exception calling pasteld z_sendmanywithchangetosender: {e}")
    except Exception as e:
        logger.error(f"Exception calling pasteld z_sendmanywithchangetosender: {e}")
    logger.error(f"Failed to send {total_amount} using z_sendmanywithchangetosender from {from_address}")
    return None


def get_amount_for_address(address):
    response = call('listaddressamounts', [])
    if response and isinstance(response, dict):
        return response.get(address, 0)
    return 0


def check_wallet_balance_and_wait(address: str, need_amount, wait_loops=5, wait_time=120):
    height_before = call("getblockcount", [])
    height_now = 0
    wallet_balance = get_amount_for_address(address)
    for ind in range(wait_loops):

        address_balance = call("z_getbalance", [address])
        if address_balance > need_amount:
            return True

        logger.info(f"Address balance is not enough: {address_balance} < {need_amount}."
                    f"will check wallet balance and wait for the next block, if wallet balance is enough")

        wallet_balance = get_amount_for_address(address)
        if wallet_balance > need_amount:
            if height_now > height_before:
                logger.error(f"Not enough balance even after next block: "
                             f"wallet_balance={wallet_balance}, need_amount={need_amount}")
                return False
            height_now = call("getblockcount", [])
            logger.info(f"Wallet balance is enough: {wallet_balance} > {need_amount},"
                        f" but there are no UTXOs to spend yet. Waiting for the next block - "
                        f"{height_before + 1}. Now is {height_now}")
            if ind < wait_loops:
                time.sleep(wait_time)  # 2 minutes delay

    logger.error(f"Not enough balance even after {wait_time*wait_loops} seconds: "
                 f"wallet_balance={wallet_balance}, need_amount={need_amount}")
    return False


def find_address_with_funds(need_amount: float) -> str | None:
    address_list = call("listaddressamounts", [])
    if address_list:
        for address, value in address_list.items():
            if value > need_amount:
                return address
    return None
