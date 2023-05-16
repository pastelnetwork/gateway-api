import logging
from pathlib import Path
import ipfshttpclient

from app.core.config import settings

logger = logging.getLogger(__name__)


async def search_file_locally_or_in_ipfs(file_local_path, file_ipfs_link):
    path = Path(file_local_path)
    if not path.is_file():
        if file_ipfs_link:
            try:
                logging.info(f'File not found locally, trying to download from IPFS...')
                ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
                ipfs_client.get(file_ipfs_link, path.parent)
            except Exception as e:
                raise IPFSException(f'File not found neither locally nor in IPFS: {e}')
            new_path = path.parent / file_ipfs_link
            new_path.rename(path)
        else:
            raise IPFSException(f'File not found locally and no IPFS link provided')
    data = open(path, 'rb')
    return data


async def store_file_to_ipfs(file_local_path):
    try:
        ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        res = ipfs_client.add(file_local_path)
        return res["Hash"]
    except Exception as e:
        logging.info(f'Error while storing file into IPFS... {e}')
        return None


async def remove_file_from_ipfs(ipfs_link):
    try:
        ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        ipfs_client.pin.rm(ipfs_link)
    except Exception as e:
        logger.error(f"Error removing file from IPFS: {e}")


async def read_file_from_ipfs(ipfs_link):
    try:
        ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        return ipfs_client.cat(ipfs_link)
    except Exception as e:
        logging.error(f"File not found in the IPFS - {e}")
        return None


async def get_file_from_ipfs(ipfs_link, file_path) -> bool:
    try:
        ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        ipfs_client.get(ipfs_link, file_path)
        return True
    except Exception as e:
        logging.error(f"File not found in the IPFS - {e}")
        return False


class IPFSException(Exception):
    def __init__(self, message):
        self.message = message or "PastelAPIException"
        super().__init__(self.message)
