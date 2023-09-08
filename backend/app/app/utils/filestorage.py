import json
import logging
import os
import pathlib
import aiofiles
from datetime import datetime

from app.celery_tasks.pastel_tasks import PastelAPIException
from app.core.config import settings
from app.utils.ipfs_tools import read_file_from_ipfs, store_file_to_ipfs
from app.utils import walletnode as wn

logger = logging.getLogger(__name__)


class LocalFile:
    def __init__(self, file_name, content_type, file_id: str):
        if not os.path.exists(settings.FILE_STORAGE):
            os.makedirs(settings.FILE_STORAGE)
        self.name = file_name
        self.type = content_type
        file_extension = pathlib.Path(file_name).suffix
        self.path = f'{settings.FILE_STORAGE}/{file_id}{file_extension}'
        self.meta_path = f'{settings.FILE_STORAGE}/{file_id}.meta.json'

    async def save(self, in_data):
        async with aiofiles.open(self.path, 'wb') as out_file:
            while content := await in_data.read():
                await out_file.write(content)
        # Save the metadata
        meta = {"name": self.name, "type": self.type}
        with open(self.meta_path, 'w') as f:
            json.dump(meta, f)

    def read(self):
        return open(self.path, 'rb')

    @staticmethod
    def load(file_id):
        path = f'{settings.FILE_STORAGE}/{file_id}'
        meta_path = path + '.meta.json'
        if not os.path.exists(meta_path):
            raise FileNotFoundError("No metadata file found for given file_id")

        with open(meta_path, 'r') as f:
            meta = json.load(f)

        return LocalFile(meta["name"], meta["type"], file_id)


async def store_file_into_local_cache(*, reg_ticket_txid, file_bytes, extra_suffix: str = "") -> str:
    cached_result_file = \
        f"{settings.FILE_STORAGE}/{settings.FILE_STORAGE_FOR_RESULTS_SUFFIX}/{reg_ticket_txid}{extra_suffix}"
    try:
        if not os.path.exists(f"{settings.FILE_STORAGE}/{settings.FILE_STORAGE_FOR_RESULTS_SUFFIX}"):
            os.makedirs(f"{settings.FILE_STORAGE}/{settings.FILE_STORAGE_FOR_RESULTS_SUFFIX}")

        with open(cached_result_file, 'wb') as f:
            f.write(file_bytes)
    except Exception as e:
        logger.error(f"File not saved in the local storage - {e}")
    return cached_result_file


async def search_file_in_local_cache(*, reg_ticket_txid, extra_suffix: str = "") -> bytes:
    cached_result_file = \
        f"{settings.FILE_STORAGE}/{settings.FILE_STORAGE_FOR_RESULTS_SUFFIX}/{reg_ticket_txid}{extra_suffix}"
    try:
        with open(cached_result_file, 'rb') as f:
            return f.read()
    except Exception as e:
        logger.error(f"File not found in the local storage - {e}")


async def search_processed_file(*, db, task_from_db, update_task_in_db_func,
                                task_done, service: wn.WalletNodeService) -> bytes:
    file_bytes = await search_file_in_local_cache(reg_ticket_txid=task_from_db.reg_ticket_txid)
    not_locally_cached = not file_bytes

    if not file_bytes and task_done:
        file_bytes = await wn.get_file_from_pastel(reg_ticket_txid=task_from_db.reg_ticket_txid, wn_service=service)

    if not file_bytes and task_from_db.stored_file_ipfs_link:
        file_bytes = await read_file_from_ipfs(task_from_db.stored_file_ipfs_link)

    if not file_bytes:
        raise PastelAPIException(f"Dupe detection data is not found")

    # cache file in local storage and IPFS
    if not_locally_cached:
        cached_result_file = await store_file_into_local_cache(reg_ticket_txid=task_from_db.reg_ticket_txid,
                                                               file_bytes=file_bytes)
        if cached_result_file and not task_from_db.stored_file_ipfs_link:
            stored_file_ipfs_link = await store_file_to_ipfs(cached_result_file)
            if stored_file_ipfs_link:
                upd = {"stored_file_ipfs_link": stored_file_ipfs_link, "updated_at": datetime.utcnow()}
                update_task_in_db_func(db, db_obj=task_from_db, obj_in=upd)
    return file_bytes


async def search_nft_dd_result(*, db, task_from_db, update_task_in_db_func) -> bytes:
    dd_bytes = await search_file_in_local_cache(reg_ticket_txid=task_from_db.reg_ticket_txid, extra_suffix=".dd")
    not_locally_cached = not dd_bytes

    if not dd_bytes:
        dd_bytes = await wn.get_nft_dd_result_from_pastel(reg_ticket_txid=task_from_db.reg_ticket_txid)

    if not dd_bytes and task_from_db.nft_dd_file_ipfs_link:
        dd_bytes = await read_file_from_ipfs(task_from_db.nft_dd_file_ipfs_link)

    if not dd_bytes:
        raise PastelAPIException(f"Dupe detection data is not found")

    # cache file in local storage and IPFS
    if not_locally_cached:
        cached_dd_file = await store_file_into_local_cache(reg_ticket_txid=task_from_db.reg_ticket_txid,
                                                           file_bytes=dd_bytes,
                                                           extra_suffix=".dd")
        if cached_dd_file and not task_from_db.nft_dd_file_ipfs_link:
            nft_dd_file_ipfs_link = await store_file_to_ipfs(cached_dd_file)
            if nft_dd_file_ipfs_link:
                upd = {"nft_dd_file_ipfs_link": nft_dd_file_ipfs_link, "updated_at": datetime.utcnow()}
                update_task_in_db_func(db, db_obj=task_from_db, obj_in=upd)

    return dd_bytes


async def search_processed_file(*, db, task_from_db, update_task_in_db_func,
                                task_done, service: wn.WalletNodeService) -> bytes:
    file_bytes = await search_file_in_local_cache(reg_ticket_txid=task_from_db.reg_ticket_txid)
    not_locally_cached = not file_bytes

    if not file_bytes and task_done:
        file_bytes = await wn.get_file_from_pastel(reg_ticket_txid=task_from_db.reg_ticket_txid, wn_service=service)

    if not file_bytes and task_from_db.stored_file_ipfs_link:
        file_bytes = await read_file_from_ipfs(task_from_db.stored_file_ipfs_link)

    if not file_bytes:
        raise PastelAPIException(f"Dupe detection data is not found")

    # cache file in local storage and IPFS
    if not_locally_cached:
        cached_result_file = await store_file_into_local_cache(reg_ticket_txid=task_from_db.reg_ticket_txid,
                                                               file_bytes=file_bytes)
        if cached_result_file and not task_from_db.stored_file_ipfs_link:
            stored_file_ipfs_link = await store_file_to_ipfs(cached_result_file)
            if stored_file_ipfs_link:
                upd = {"stored_file_ipfs_link": stored_file_ipfs_link, "updated_at": datetime.utcnow()}
                update_task_in_db_func(db, db_obj=task_from_db, obj_in=upd)
    return file_bytes