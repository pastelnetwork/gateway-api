import base64
import json
import logging

import requests
from fastapi import HTTPException
from requests.auth import HTTPBasicAuth

from app.core.config import settings


def call(method, parameters, nothrow=False):
    payload_getinfo = {"jsonrpc": "1.0", "id": "pastelapi", "method": method, "params": parameters}
    payload = json.dumps(payload_getinfo)
    auth = HTTPBasicAuth(settings.PASTEL_RPC_USER, settings.PASTEL_RPC_PWD)
    response = requests.post(settings.PASTEL_RPC_URL, payload, auth=auth)
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
        logging.warning(f"Failed to ascii85 decode api_ticket in the {expected_action_type} registration ticket: {ve}")
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
                    logging.warning(f"Failed to base64 decode api_ticket in the {expected_action_type} "
                                    f"with extra padding registration ticket: {ve}")
            else:
                logging.warning(f"Failed to base64 decode api_ticket in the {expected_action_type} "
                                f"registration ticket: {ve}")

    return reg_ticket
