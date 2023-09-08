import logging
from pathlib import Path
import ipfshttpclient
import requests
import aiohttp

from app.core.config import settings

logger = logging.getLogger(__name__)


class IPFSClient:
    def __init__(self, base_url="http://127.0.0.1:5001/api/v0"):
        self.base_url = base_url
        self.session = aiohttp.ClientSession()

    async def add(self, file_path):
        url = f"{self.base_url}/add"
        async with self.session.post(url, data={'file': open(file_path, 'rb')}) as response:
            return await response.json()

    async def pin_add(self, cid):
        url = f"{self.base_url}/pin/add?arg={cid}"
        async with self.session.post(url) as response:
            return await response.json()

    async def get(self, cid):
        url = f"{self.base_url}/get?arg={cid}"
        async with self.session.post(url) as response:
            return await response.read()

    async def cat(self, cid):
        url = f"{self.base_url}/cat?arg={cid}"
        async with self.session.post(url) as response:
            return await response.read()

    async def close(self):
        await self.session.close()

# Usage example
# import asyncio

# async def main():
#     client = IPFSClient()
#     # Use the client's methods here...
#     await client.close()

# asyncio.run(main())


async def search_file_locally_or_in_ipfs(file_local_path, ipfs_cid, nothrow=False):
    path = Path(file_local_path)
    if not path.is_file():
        if ipfs_cid:
            try:
                logger.info(f'File not found locally, trying to download from IPFS...')
                ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
                ipfs_client.get(ipfs_cid, path.parent)
            except Exception as e:
                if nothrow:
                    logger.error(f'File not found locally and no IPFS link provided')
                    return None
                raise IPFSException(f'File not found neither locally nor in IPFS: {e}')
            new_path = path.parent / ipfs_cid
            new_path.rename(path)
        else:
            if nothrow:
                logger.error(f'File not found locally and no IPFS link provided')
                return None
            raise IPFSException(f'File not found locally and no IPFS link provided')
    data = open(path, 'rb')
    return data


async def store_file_to_ipfs(file_local_path):
    try:
        ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        res = ipfs_client.add(file_local_path)
        cid = res["Hash"]
        if cid:
            await pin_file_to_scaleway(cid)
        return cid
    except Exception as e:
        logger.info(f'Error while storing file into IPFS... {e}')
        return None


async def remove_file_from_ipfs(ipfs_cid):
    try:
        ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        ipfs_client.pin.rm(ipfs_cid)
    except Exception as e:
        logger.error(f"Error removing file from IPFS: {e}")


async def read_file_from_ipfs(ipfs_cid):
    try:
        ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        return ipfs_client.cat(ipfs_cid)
    except Exception as e:
        logger.error(f"File not found in the IPFS - {e}")
        return None


async def get_file_from_ipfs(ipfs_cid, file_path) -> bool:
    try:
        ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        ipfs_client.get(ipfs_cid, file_path)
        return True
    except Exception as e:
        logger.error(f"File not found in the IPFS - {e}")
        return False


async def pin_file_to_scaleway(ipfs_cid):
    scw_pin_url = f"{settings.SCW_PIN_URL_PREFIX}/{settings.SCW_REGION}/{settings.SCW_PIN_URL_SUFFIX}"

    try:
        r = requests.post(
            scw_pin_url,
            headers={
                "X-Auth-Token": settings.SCW_SECRET_KEY,
                "Content-Type": "application/json"
            },
            json={
                "cid": {ipfs_cid},
                "name": "",
                "origins": ["ipfs"],
                "pin_options": None,
                "volume_id": settings.SCW_VOLUME_ID
            },
            timeout=10
        )
        if r.status_code != 200:
            logger.error(f"Error pinning file to Scaleway: {r.text}")
            return False
    except Exception as e:
        logger.error(f"Error pinning file to Scaleway: {e}")
        return False


class IPFSException(Exception):
    def __init__(self, message):
        self.message = message or "PastelAPIException"
        super().__init__(self.message)
