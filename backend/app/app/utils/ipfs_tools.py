import logging
from pathlib import Path
from io import BytesIO
import tarfile
import requests
import aiohttp
import os
import shutil

from app.core.config import settings

logger = logging.getLogger(__name__)


class IPFSClient:
    def __init__(self, base_url="http://127.0.0.1:5001/api/v0"):
        self.base_url = base_url
        self.session = None  # Initialize session as None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.session.close()

    async def add(self, file_path):
        url = f"{self.base_url}/add"
        try:
            async with self.session.post(url, data={'file': open(file_path, 'rb')}) as response:
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f'Error adding file to IPFS: {e}')
            raise e

    async def get(self, cid, save_path):
        url = f"{self.base_url}/get?arg={cid}"
        try:
            async with self.session.post(url) as response:
                if response.status != 200:
                    logger.error(f'Error getting file from IPFS: {response.status}')
                    raise Exception(f"Error getting file from IPFS: {response.status}")

                tar_data = await response.read()
                tar_stream = BytesIO(tar_data)

                temp_file_path = os.path.join("/tmp", cid)

                with tarfile.open(fileobj=tar_stream) as tar:
                    tar.extractall(path="/tmp")

                shutil.move(temp_file_path, save_path)
        except aiohttp.ClientError as e:
            logger.error(f'Error getting file from IPFS: {response.status}')
            raise e

    async def cat(self, cid):
        url = f"{self.base_url}/cat?arg={cid}"
        try:
            async with self.session.post(url) as response:
                if response.status != 200:
                    logger.error(f'Error getting file from IPFS: {response.status}')
                    raise Exception(f"Error getting file from IPFS: {response.status}")
                data = await response.read()
                return data
        except aiohttp.ClientError as e:
            logger.error(f'Error getting file from IPFS: {response.status}')
            raise e

    async def pin_add(self, cid):
        url = f"{self.base_url}/pin/add?arg={cid}"
        try:
            async with self.session.post(url) as response:
                if response.status != 200:
                    logger.error(f'Error pinning file to IPFS: {response.status}')
                    raise Exception(f"Error pinning file to IPFS: {response.status}")
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f'Error pinning file to IPFS: {response.status}')
            raise e

    async def remove_pin(self, cid):
        url = f"{self.base_url}/pin/rm?arg={cid}"
        try:
            async with self.session.post(url) as response:
                if response.status != 200:
                    logger.error(f'Error removing pin of file from IPFS: {response.status}')
                    raise Exception(f"Error removing pin of file from IPFS: {response.status}")
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f'Error removing pin of file from IPFS: {response.status}')
            raise e


async def search_file_locally_or_in_ipfs(file_local_path, ipfs_cid, nothrow=False):
    path = Path(file_local_path)
    if not path.is_file():
        if ipfs_cid:
            try:
                logger.info(f'File not found locally, trying to download from IPFS...')
                # ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
                async with IPFSClient(settings.IPFS_URL) as ipfs_client:
                    await ipfs_client.get(ipfs_cid, path.parent)
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
        # ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        async with IPFSClient(settings.IPFS_URL) as ipfs_client:
            res = await ipfs_client.add(file_local_path)
        cid = res["Hash"]
        if cid:
            await pin_file_to_scaleway(cid)
        return cid
    except Exception as e:
        logger.info(f'Error while storing file into IPFS... {e}')
        return None


async def remove_file_from_ipfs(ipfs_cid):
    try:
        # ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        # ipfs_client.pin.rm(ipfs_cid)
        async with IPFSClient(settings.IPFS_URL) as ipfs_client:
            await ipfs_client.remove_pin(ipfs_cid)
    except Exception as e:
        logger.error(f"Error removing file from IPFS: {e}")


async def read_file_from_ipfs(ipfs_cid):
    try:
        # ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        async with IPFSClient(settings.IPFS_URL) as ipfs_client:
            return await ipfs_client.cat(ipfs_cid)
    except Exception as e:
        logger.error(f"File not found in the IPFS - {e}")
        return None


async def get_file_from_ipfs(ipfs_cid, file_path) -> bool:
    try:
        # ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        async with IPFSClient(settings.IPFS_URL) as ipfs_client:
            await ipfs_client.get(ipfs_cid, file_path)
        return True
    except Exception as e:
        logger.error(f"File not found in the IPFS - {e}")
        return False


async def pin_file_to_scaleway(ipfs_cid):
    if not settings.SCW_ENABLED:
        return True

    if not settings.SCW_SECRET_KEY or not settings.SCW_VOLUME_ID:
        logger.error("Scaleway credentials not set")
        return False

    if not settings.SCW_PIN_URL_PREFIX or not settings.SCW_PIN_URL_SUFFIX:
        logger.error("Scaleway pin url not set")
        return False

    scw_pin_url = f"{settings.SCW_PIN_URL_PREFIX}/{settings.SCW_REGION}/{settings.SCW_PIN_URL_SUFFIX}"

    try:
        r = requests.post(
            scw_pin_url,
            headers={
                "X-Auth-Token": settings.SCW_SECRET_KEY,
                "Content-Type": "application/json"
            },
            json={
                "cid": ipfs_cid,
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
