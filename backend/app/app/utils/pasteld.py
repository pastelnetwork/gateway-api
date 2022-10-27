import json
import requests
from requests.auth import HTTPBasicAuth

from app.core.config import settings


def call(method, parameters):
    payload_getinfo = {"jsonrpc": "1.0", "id": "pastelapi", "method": method, "params": parameters}
    payload = json.dumps(payload_getinfo)
    auth = HTTPBasicAuth(settings.PASTEL_RPC_USER, settings.PASTEL_RPC_PWD)
    response = requests.post(settings.PASTEL_RPC_URL, payload, auth=auth)
    response.raise_for_status()
    resp = response.json()
    if not resp or not resp["result"]:
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
