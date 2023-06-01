import logging
import os
import pathlib

import aiofiles

from app.core.config import settings


class LocalFile:
    def __init__(self, file_name, content_type, result_id: str):
        if not os.path.exists(settings.FILE_STORAGE):
            os.makedirs(settings.FILE_STORAGE)
        self.name = file_name
        self.type = content_type
        file_extension = pathlib.Path(file_name).suffix
        self.path = f'{settings.FILE_STORAGE}/{result_id}{file_extension}'

    async def save(self, in_data):
        async with aiofiles.open(self.path, 'wb') as out_file:
            while content := await in_data.read():
                await out_file.write(content)

    def read(self):
        return open(self.path, 'rb')


async def store_file_into_local_cache(*, reg_ticket_txid, file_bytes, extra_suffix: str ="") -> str:
    cached_result_file = \
        f"{settings.FILE_STORAGE}/{settings.FILE_STORAGE_FOR_RESULTS_SUFFIX}/{reg_ticket_txid}{extra_suffix}"
    try:
        if not os.path.exists(f"{settings.FILE_STORAGE}/{settings.FILE_STORAGE_FOR_RESULTS_SUFFIX}"):
            os.makedirs(f"{settings.FILE_STORAGE}/{settings.FILE_STORAGE_FOR_RESULTS_SUFFIX}")

        with open(cached_result_file, 'wb') as f:
            f.write(file_bytes)
    except Exception as e:
        logging.error(f"File not saved in the local storage - {e}")
    return cached_result_file

async def search_file_in_local_cache(*, reg_ticket_txid, extra_suffix: str ="") -> bytes:
    cached_result_file = \
        f"{settings.FILE_STORAGE}/{settings.FILE_STORAGE_FOR_RESULTS_SUFFIX}/{reg_ticket_txid}{extra_suffix}"
    try:
        with open(cached_result_file, 'rb') as f:
            return f.read()
    except Exception as e:
        logging.error(f"File not found in the local storage - {e}")
