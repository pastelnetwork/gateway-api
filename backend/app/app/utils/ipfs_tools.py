import logging
from pathlib import Path
import ipfshttpclient

from app.core.config import settings


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


async def add_file_to_ipfs(file_local_path):
    try:
        ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        res = ipfs_client.add(file_local_path)
        original_file_ipfs_link = res["Hash"]
    except Exception as e:
        logging.info(f'Error while storing file into IPFS... {e}')
        original_file_ipfs_link = None
    return original_file_ipfs_link


async def read_file_from_ipfs(ipfs_link):
    try:
        ipfs_client = ipfshttpclient.connect(settings.IPFS_URL)
        file_bytes = ipfs_client.cat(ipfs_link)
    except Exception as e:
        logging.error(f"File not found in the IPFS - {e}")
        file_bytes = None
    return file_bytes


class IPFSException(Exception):
    def __init__(self, message):
        self.message = message or "PastelAPIException"
        super().__init__(self.message)
